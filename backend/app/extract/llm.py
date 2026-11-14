"""Single gateway for every LLM call: schema out, CostLine, cache, DEMO_OFFLINE.

LLMs may only fill Extraction / ClassifiedPage models. Never PASS/FAIL.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings
from app.models import CostLine

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_COST_LOG: list[CostLine] = []


def reset_cost_log() -> None:
    _COST_LOG.clear()


def cost_log() -> list[CostLine]:
    return list(_COST_LOG)


def _cache_dir(settings: Settings) -> Path:
    d = settings.data_dir / "llm_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(
    *,
    content: bytes | str,
    model: str,
    prompt_version: str,
    schema_name: str,
) -> str:
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()
    blob = f"{h}|{model}|{prompt_version}|{schema_name}"
    return hashlib.sha256(blob.encode()).hexdigest()


def _cache_path(settings: Settings, key: str) -> Path:
    return _cache_dir(settings) / f"{key}.json"


def _price_usd(settings: Settings, model: str, inp: int, out: int) -> float:
    provider = settings.extract_provider.lower()
    if provider in {"ollama", "llama", "llama3.2"}:
        return 0.0
    m = model.lower()
    if "haiku" in m:
        pin, pout = settings.price_claude_haiku_5_5_in, settings.price_claude_haiku_5_5_out
    elif "claude" in m or "sonnet" in m:
        pin, pout = settings.price_claude_sonnet_5_5_in, settings.price_claude_sonnet_5_5_out
    elif "gemini" in m:
        pin, pout = settings.price_gemini_3_8_flash_in, settings.price_gemini_3_8_flash_out
    else:
        return 0.0
    return (inp * pin + out * pout) / 1_000_000


def _parse_json_model(raw: str, schema: type[T]) -> T:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return schema.model_validate_json(text)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def _call_ollama(system: str, user: str, schema: type[T], settings: Settings) -> tuple[T, int, int]:
    """Local Llama via Ollama — JSON object matching the Pydantic schema."""
    import httpx

    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    payload = {
        "model": settings.extract_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
        "messages": [
            {
                "role": "system",
                "content": (
                    f"{system}\n\nRespond with ONE JSON object only, matching this schema:\n{schema_json}"
                ),
            },
            {"role": "user", "content": user},
        ],
    }
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    with httpx.Client(timeout=settings.llm_timeout_s) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    content = (data.get("message") or {}).get("content") or ""
    # Ollama may report eval counts
    inp = int(data.get("prompt_eval_count") or 0)
    out = int(data.get("eval_count") or 0)
    return _parse_json_model(content, schema), inp, out


def _record_cost(step: str, model: str, inp: int, out: int, settings: Settings) -> CostLine:
    line = CostLine(
        step=step,
        model=model,
        input_tokens=inp,
        output_tokens=out,
        usd=_price_usd(settings, model, inp, out),
    )
    _COST_LOG.append(line)
    return line


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def _call_gemini(system: str, user: str, schema: type[T], settings: Settings) -> tuple[T, int, int]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.0,
    )
    resp = client.models.generate_content(
        model=settings.extract_model,
        contents=user,
        config=config,
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    inp = int(getattr(usage, "prompt_token_count", 0) or 0)
    out = int(getattr(usage, "candidates_token_count", 0) or 0)
    return schema.model_validate_json(text), inp, out


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def _call_anthropic(system: str, user: str, schema: type[T], settings: Settings) -> tuple[T, int, int]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    tool = {
        "name": "extract_fields",
        "description": f"Fill {schema.__name__} from the document text. Fields only, no verdicts.",
        "input_schema": schema.model_json_schema(),
    }
    msg = client.messages.create(
        model=settings.extract_model,
        max_tokens=4096,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": "extract_fields"},
        messages=[{"role": "user", "content": user}],
    )
    inp = int(msg.usage.input_tokens)
    out = int(msg.usage.output_tokens)
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_fields":
            return schema.model_validate(block.input), inp, out
    raise RuntimeError("anthropic extract: no tool_use block")


def extract_structured(
    *,
    schema: type[T],
    system: str,
    user: str,
    step: str,
    content_for_cache: bytes | str,
    offline_fixture: T | None = None,
    settings: Settings | None = None,
) -> T:
    """Return a validated Pydantic model. Uses cache; DEMO_OFFLINE uses fixture if miss."""
    settings = settings or get_settings()
    model = settings.extract_model
    key = cache_key(
        content=content_for_cache,
        model=model,
        prompt_version=settings.prompt_version,
        schema_name=schema.__name__,
    )
    path = _cache_path(settings, key)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        _record_cost(step, model, 0, 0, settings)  # cache hit — zero tokens
        return schema.model_validate(data["result"])

    if settings.demo_offline:
        if offline_fixture is None:
            raise RuntimeError(
                f"DEMO_OFFLINE=1 and no cache for {schema.__name__}; provide offline_fixture"
            )
        path.write_text(
            json.dumps(
                {"result": offline_fixture.model_dump(mode="json"), "source": "offline_fixture"},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        _record_cost(step, f"{model}+offline", 0, 0, settings)
        return offline_fixture

    provider = settings.extract_provider.lower()
    if provider in {"ollama", "llama", "llama3.2"}:
        result, inp, out = _call_ollama(system, user, schema, settings)
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        result, inp, out = _call_anthropic(system, user, schema, settings)
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY missing (or set DEMO_OFFLINE=1 / use ollama)")
        result, inp, out = _call_gemini(system, user, schema, settings)
    else:
        raise RuntimeError(f"unknown EXTRACT_PROVIDER={provider!r} (use ollama|gemini|anthropic)")

    _record_cost(step, model, inp, out, settings)
    path.write_text(
        json.dumps({"result": result.model_dump(mode="json"), "source": "live"}, indent=2, default=str),
        encoding="utf-8",
    )
    return result
