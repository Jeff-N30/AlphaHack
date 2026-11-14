"""Single gateway for every LLM call: schema out, CostLine, cache, DEMO_OFFLINE.

LLMs may only fill Extraction / ClassifiedPage models. Never PASS/FAIL.
VisaRef demo: Ollama llama3.2 only.
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


def _record_cost(step: str, model: str, inp: int, out: int, settings: Settings) -> CostLine:
    # Local Ollama — $0
    line = CostLine(
        step=step,
        model=model,
        input_tokens=inp,
        output_tokens=out,
        usd=0.0,
    )
    _COST_LOG.append(line)
    return line


def _strip_schema_patterns(node: object) -> object:
    if isinstance(node, dict):
        return {
            k: _strip_schema_patterns(v)
            for k, v in node.items()
            if k != "pattern"
        }
    if isinstance(node, list):
        return [_strip_schema_patterns(x) for x in node]
    return node


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

    # Strip JSON-Schema "pattern" — some Ollama/llama3.2 builds crash the runner on it.
    raw_schema = schema.model_json_schema()
    ollama_schema = _strip_schema_patterns(raw_schema)
    schema_json = json.dumps(ollama_schema, indent=2)
    payload = {
        "model": settings.extract_model,
        "stream": False,
        "format": ollama_schema,
        "options": {"temperature": 0.0},
        "messages": [
            {
                "role": "system",
                "content": (
                    f"{system}\n\nReturn field values only as ONE JSON object. "
                    f"Do not return the schema, its title, or its descriptions.\n"
                    f"Required output schema:\n{schema_json}"
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
    inp = int(data.get("prompt_eval_count") or 0)
    out = int(data.get("eval_count") or 0)
    return _parse_json_model(content, schema), inp, out


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
        _record_cost(step, model, 0, 0, settings)
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
    if provider not in {"ollama", "llama", "llama3.2"}:
        raise RuntimeError(
            f"EXTRACT_PROVIDER={provider!r} is not supported — use ollama / llama3.2 only"
        )

    result, inp, out = _call_ollama(system, user, schema, settings)
    _record_cost(step, model, inp, out, settings)
    path.write_text(
        json.dumps({"result": result.model_dump(mode="json"), "source": "live"}, indent=2, default=str),
        encoding="utf-8",
    )
    return result
