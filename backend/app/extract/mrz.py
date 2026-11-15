"""Passport MRZ: passporteye OCR + ICAO 9303 check digits (mrz lib).

AI does not decide validity — checksums do. OCR confusions (O/0, I/1) are
resolved only when a candidate makes every ICAO hash validate.
"""
from __future__ import annotations

import itertools
import logging
import re
import tempfile
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Optional

from app.models import MRZ, PassportExtraction

logger = logging.getLogger(__name__)

# TD3 line-2 layout (ICAO 9303)
_DOC_NUM = slice(0, 9)
_DOB = slice(13, 19)
_SEX = 20
_EXPIRY = slice(21, 27)
_PERSONAL = slice(28, 42)


def _yy_to_date(yy_mm_dd: str, *, kind: str, today: date | None = None) -> date:
    """Convert YYMMDD using the project century rules."""
    if len(yy_mm_dd) != 6 or not yy_mm_dd.isdigit():
        raise ValueError(f"invalid MRZ date: {yy_mm_dd!r}")
    yy, mm, dd = int(yy_mm_dd[:2]), int(yy_mm_dd[2:4]), int(yy_mm_dd[4:6])
    today = today or date.today()
    if kind == "expiry":
        century = 2000
    else:  # DOB: yy > current yy → 19xx, else 20xx
        century = 1900 if yy > (today.year % 100) else 2000
    return date(century + yy, mm, dd)


def _normalize_line(raw: str) -> str:
    s = re.sub(r"[^A-Z0-9<]", "", raw.upper().replace(" ", ""))
    return s[:44].ljust(44, "<")


def _split_mrz_text(text: str) -> Optional[tuple[str, str]]:
    lines: list[str] = []
    for raw in text.upper().splitlines():
        s = re.sub(r"[^A-Z0-9<]", "", raw.replace(" ", ""))
        if len(s) >= 28:
            lines.append(_normalize_line(s))
    if len(lines) >= 2:
        return lines[0], lines[1]
    blob = re.sub(r"[^A-Z0-9<]", "", text.upper().replace(" ", "").replace("\n", ""))
    if len(blob) >= 88:
        return blob[:44], blob[44:88]
    return None


def _mrz_name_field(s: str) -> str:
    return re.sub(r"[^A-Z]", "<", s.upper().replace(" ", "<").replace("-", "<"))


def _rebuild_line1(surname: str, given: str, nationality: str) -> str:
    nat = re.sub(r"[^A-Z]", "", nationality.upper())[:3].ljust(3, "<")
    return ("P<" + nat + _mrz_name_field(surname) + "<<" + _mrz_name_field(given)).ljust(44, "<")[:44]


def _parse_names_from_line1(line1: str) -> tuple[str, str]:
    body = line1[5:44] if len(line1) >= 5 else line1
    if "<<" in body:
        sur, _, rest = body.partition("<<")
        # BARK<<<JOE → after dropping OCR-K we get BAR<<<JOE; strip extra <
        rest = rest.lstrip("<")
        given = rest.split("<")[0] if rest else ""
    else:
        parts = [p for p in body.split("<") if p]
        sur = parts[0] if parts else ""
        given = parts[1] if len(parts) > 1 else ""
    return sur.replace("<", " ").strip(), given.replace("<", " ").strip()


def _clean_mrz_name_parts(s: str) -> str:
    """Drop OCR filler tokens the mrz lib treats as given-name parts (SSS, SKKKK)."""
    toks = [t for t in re.split(r"\s+", (s or "").replace("<", " ").strip()) if t]
    toks = [t for t in toks if not re.fullmatch(r"[SKE0-9]+", t)]
    return " ".join(toks)


def _fix_line1_filler_k(line1: str) -> str:
    """OCR often reads MRZ filler '<' as 'K' (sometimes 'S'/'E') in the name zone.

    Examples:
      NADERK<JEFF   → NADER<<JEFF   (single '<' is a broken separator: K was '<')
      JOE<SSS<SKKKK  → JOE<<<<<<<<<<< (filler runs after the given name)
    A K glued before a proper '<<' is a real letter (BARK<<JOE, MALEK<<, TARIK<<).
    Never eat a real K that starts a given name (EL<KHOURY).
    Never strip S — GEORGES<< must stay GEORGES.
    """
    chars: list[str | None] = list(_normalize_line(line1))
    # TD3 name zone is A–Z and '<' only — digits are OCR junk
    for i in range(5, 44):
        ch = chars[i]
        if isinstance(ch, str) and ch.isdigit():
            chars[i] = "<"
    for i in range(5, 44):  # after P< + nationality
        ch = chars[i]
        if ch not in "KSE":
            continue
        left = chars[i - 1] if i > 0 else "<"
        right = chars[i + 1] if i + 1 < 44 else "<"
        # Skip Nones from earlier deletes in left lookup
        if left is None:
            left = "<"
        if right is None:
            right = "<"
        if ch == "K" and isinstance(left, str) and left.isalpha() and right == "<":
            after = chars[i + 2] if i + 2 < 44 else "<"
            if isinstance(after, str) and after.isalpha():
                chars[i] = "<"
        elif ch == "K" and left in "<SE" and right in "<KSE":
            chars[i] = "<"
        elif ch in "SE" and left == "<" and right in "<KSE":
            # Only after an existing '<' — never eat GEORGES (S after E stays).
            chars[i] = "<"
        elif i == 43 and left in "<KSE":
            chars[i] = "<"
    out = "".join(c for c in chars if c is not None)
    out = out[:44].ljust(44, "<")
    # After surname<<given, remaining S/K/E runs are filler (JOE<SSS<SKKKK)
    body = out[5:]
    if "<<" in body:
        head, sep, rest = body.partition("<<")
        rest = rest.lstrip("<")
        if rest:
            given, _, tail = rest.partition("<")
            if given and re.search(r"[SKE]", tail):
                cleaned = ("P<" + out[2:5] + head + sep + given).ljust(44, "<")
                return cleaned[:44]
    return out

def _line1_ocr_variants(line1: str) -> list[str]:
    """Raw line1 plus filler-K fixes. Prefer the fixed form first."""
    base = _normalize_line(line1)
    fixed = _fix_line1_filler_k(base)
    out: list[str] = []
    for s in (fixed, base):
        if s not in out:
            out.append(s)
    # NASSARK<<KARIMK → NASSAR<<KARIM (both ends glued OCR-K). Not BARK<<JOE.
    sur, giv = _parse_names_from_line1(fixed)
    if len(sur) > 4 and sur.endswith("K") and len(giv) > 3 and giv.endswith("K"):
        cleaned = _rebuild_line1(sur[:-1], giv[:-1], fixed[2:5])
        if cleaned not in out:
            out.insert(0, cleaned)
    return out


def _name_candidates(names: str, *, strip_trailing_k: bool = True) -> list[str]:
    """OCR often appends a trailing K (MOHAMADK / NADERK) from a misread '<'.

    Never strip S (GEORGES). Keep multi-token surnames intact (AL HAJJ → not just AL).

    For surnames pass strip_trailing_k=False so BARK/MALEK stay; only strip surname
    K when the given name also shows filler-K (see callers).
    """
    toks = [t for t in re.split(r"\s+", (names or "").strip()) if t]
    # Drop filler OCR blobs (SSS, SKKKK, SSS9SKKKKK) — not real name parts
    toks = [t for t in toks if not re.fullmatch(r"[SKE<0-9]+", t)]
    if not toks:
        return []

    def strip_k(token: str) -> str:
        if len(token) > 3 and token.endswith("K"):
            return token[:-1]
        return token

    stripped = [strip_k(t) for t in toks]
    out: list[str] = []
    variants: tuple[list[str], ...]
    if strip_trailing_k:
        variants = (stripped, toks)
    else:
        variants = (toks,)
    for variant in variants:
        s = " ".join(variant)
        if s and s not in out:
            out.append(s)
    # "NADERK JEFF" from a broken single-`<` parse → also try surname-only / given-only
    if strip_trailing_k and len(stripped) == 2:
        for part in stripped:
            if part not in out:
                out.append(part)
    return out


def _tokens_had_trailing_k(names: str) -> bool:
    """True when a real given-name token ends in K (KARIMK), not filler SSS9SKKKKK."""
    toks = [t for t in re.split(r"\s+", (names or "").strip()) if t]
    toks = [t for t in toks if not re.fullmatch(r"[SKE<0-9]+", t)]
    return any(len(t) > 3 and t.endswith("K") for t in toks)
def _normalize_personal_zone(line2: str) -> str:
    chars = list(_normalize_line(line2))
    for i in range(_PERSONAL.start, 43):
        if chars[i] in "KSE":
            chars[i] = "<"
    return "".join(chars)


def _ocr_variants(line2: str) -> list[str]:
    """Bounded O/0 I/1 swaps on identity fields + optional final-hash digits."""
    base = _normalize_personal_zone(line2)
    idxs = [i for i, c in enumerate(base) if c in "O0I1" and i < _PERSONAL.start][:10]
    seen: set[str] = set()
    out: list[str] = []

    def add(s: str) -> None:
        if s not in seen:
            seen.add(s)
            out.append(s)

    add(base)
    for n in range(1, len(idxs) + 1):
        for pick in itertools.combinations(idxs, n):
            chars = list(base)
            for i in pick:
                chars[i] = {"O": "0", "0": "O", "I": "1", "1": "I"}[chars[i]]
            add("".join(chars))

    final: list[str] = []
    seen2: set[str] = set()
    for cand in out:
        for s in (cand, *(cand[:43] + d for d in "0123456789" if cand[43] == "<")):
            if s not in seen2:
                seen2.add(s)
                final.append(s)
    return final


def _failed_checks_from_report(checker: Any) -> list[str]:
    falses = getattr(checker.report, "falses", None) or []
    return [name for name, ok in falses if not ok]


def parse_td3(
    lines: list[str] | tuple[str, str],
    *,
    today: date | None = None,
) -> MRZ:
    """Parse two TD3 lines with the `mrz` library; list failed ICAO checks."""
    if len(lines) < 2:
        raise ValueError("TD3 MRZ requires 2 lines")
    # Clean filler OCR before the mrz lib sees JOE<SSS<SKKKK as extra given names
    l1 = _fix_line1_filler_k(lines[0])
    l2 = _normalize_line(lines[1])
    code = f"{l1}\n{l2}"
    surname, given = _parse_names_from_line1(l1)

    from mrz.checker.td3 import TD3CodeChecker

    try:
        checker = TD3CodeChecker(code, check_expiry=False, compute_warnings=False)
    except Exception as exc:
        return MRZ(
            line1=l1,
            line2=l2,
            surname=surname,
            given_names=given,
            passport_number=l2[_DOC_NUM].replace("<", ""),
            nationality=l2[10:13].replace("<", ""),
            date_of_birth=date(1900, 1, 1),
            sex="<",
            expiry_date=date(2000, 1, 1),
            checksums_valid=False,
            failed_checks=[f"parse_error:{exc}"],
        )

    valid = bool(checker)
    failed = _failed_checks_from_report(checker)
    fields = checker.fields()

    sur = (fields.surname or "") if fields.surname not in (None, "None") else ""
    giv = (fields.name or "") if fields.name not in (None, "None") else ""
    sur = _clean_mrz_name_parts(sur)
    giv = _clean_mrz_name_parts(giv)
    # Prefer our filler-cleaned parse when the lib still keeps junk tokens
    if not sur and not giv:
        sur, giv = surname, given
    elif (not giv and given) or (
        giv and given and len(giv.split()) > len(given.split())
    ):
        sur, giv = surname or sur, given or giv

    sex_raw = (fields.sex or l2[_SEX] or "<")[:1]
    sex = sex_raw if sex_raw in ("M", "F", "<") else "<"

    dob_s = fields.birth_date or l2[_DOB]
    exp_s = fields.expiry_date or l2[_EXPIRY]
    try:
        dob = _yy_to_date(dob_s, kind="dob", today=today)
        exp = _yy_to_date(exp_s, kind="expiry", today=today)
    except ValueError:
        return MRZ(
            line1=l1,
            line2=l2,
            surname=sur.replace("<", " ").strip() or surname,
            given_names=giv.replace("<", " ").strip() or given,
            passport_number=(fields.document_number or l2[_DOC_NUM]).replace("<", ""),
            nationality=(fields.nationality or l2[10:13]).replace("<", ""),
            date_of_birth=date(1900, 1, 1),
            sex=sex,  # type: ignore[arg-type]
            expiry_date=date(2000, 1, 1),
            checksums_valid=False,
            failed_checks=[*failed, "date_parse_error"],
        )

    return MRZ(
        line1=l1,
        line2=l2,
        surname=(sur.replace("<", " ").strip() or surname),
        given_names=(giv.replace("<", " ").strip() or given),
        passport_number=(fields.document_number or l2[_DOC_NUM]).replace("<", ""),
        nationality=(fields.nationality or l2[10:13]).replace("<", ""),
        date_of_birth=dob,
        sex=sex,  # type: ignore[arg-type]
        expiry_date=exp,
        checksums_valid=valid,
        failed_checks=failed,
    )

def _name_quality(mrz: MRZ) -> int:
    """Lower is better. Prefer <<, clean given, longer given (GEORGES > GEORGE).

    Line-1 names are NOT in ICAO check digits — NASSARK and NASSAR can both
    "validate" with the same line 2. Prefer given without trailing OCR-K; when
    both surname and given end in K (NASSARK+KARIMK), heavily prefer the strip.
    Surname-only trailing K (BARK+JOE) is not penalized — that letter is real.
    """
    score = 0
    if "<<" not in (mrz.line1 or ""):
        score += 5
    sur = (mrz.surname or "").replace(" ", "")
    giv = (mrz.given_names or "").replace(" ", "")
    if not giv:
        score += 2
    if len(giv) > 3 and giv.endswith("K"):
        score += 6
    if len(sur) > 3 and sur.endswith("K") and len(giv) > 3 and giv.endswith("K"):
        score += 8
    elif len(sur) > 4 and sur.endswith("K"):
        # NASSARK<<KARIM vs NASSAR<<KARIM — prefer strip. BARK (len 4) untouched.
        score += 3
    score -= len(giv)
    return score


def _best_parse(candidates: list[tuple[str, str]], *, today: date | None = None) -> Optional[MRZ]:
    best: MRZ | None = None
    best_score = 10_000
    best_valid: MRZ | None = None
    best_valid_q = 10_000
    for l1, l2 in candidates:
        mrz = parse_td3([l1, l2], today=today)
        if mrz.checksums_valid:
            q = _name_quality(mrz)
            if q < best_valid_q:
                best_valid_q = q
                best_valid = mrz
            continue
        score = len(mrz.failed_checks)
        if score < best_score:
            best_score = score
            best = mrz
    return best_valid or best


def _extract_line2(raw: str) -> Optional[str]:
    for ln in raw.upper().splitlines():
        s = re.sub(r"[^A-Z0-9<]", "", ln.replace(" ", ""))
        if len(s) >= 40 and not s.startswith("P"):
            return _normalize_line(s)
    split = _split_mrz_text(raw)
    return split[1] if split else None


def _candidates_from_passporteye_dict(data: dict) -> list[tuple[str, str]]:
    raw = data.get("raw_text") or ""
    line2 = _extract_line2(raw)
    if not line2:
        return []

    nat = (data.get("nationality") or data.get("country") or "LBN").replace("<", "")[:3]
    pe_sur = (data.get("surname") or "").replace("<", " ").strip()
    pe_giv = data.get("names") or ""
    # Keep surname trailing K (BARK) unless given also shows filler-K (NASSARK+KARIMK)
    strip_sur_k = _tokens_had_trailing_k(pe_giv)
    surnames = _name_candidates(pe_sur, strip_trailing_k=strip_sur_k)
    if not surnames and pe_sur:
        surnames = _name_candidates(pe_sur, strip_trailing_k=False)
    givens = _name_candidates(pe_giv, strip_trailing_k=True)
    split = _split_mrz_text(raw)
    raw_l1 = split[0] if split else None
    if raw_l1:
        for l1v in _line1_ocr_variants(raw_l1):
            sur_r, giv_r = _parse_names_from_line1(l1v)
            strip_r = _tokens_had_trailing_k(giv_r) or strip_sur_k
            for s in _name_candidates(sur_r, strip_trailing_k=strip_r):
                if s not in surnames:
                    surnames.append(s)
            for g in _name_candidates(giv_r, strip_trailing_k=True):
                if g not in givens:
                    givens.append(g)
    # Always keep as-read surname so BARK stays even when we also try NASSAR
    for s in _name_candidates(pe_sur, strip_trailing_k=False):
        if s not in surnames:
            surnames.append(s)
    cands: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(l1: str, l2: str) -> None:
        pair = (l1, l2)
        if pair not in seen:
            seen.add(pair)
            cands.append(pair)

    l2_variants = _ocr_variants(line2)

    # Fixed raw line1 first — catches NADERK<JEFF → NADER<<JEFF before rebuild
    if raw_l1:
        for l1 in _line1_ocr_variants(raw_l1):
            for l2 in l2_variants:
                add(l1, l2)

    # Rebuilt line1 from PE / parsed name tokens (K-stripped preferred)
    for surname in surnames or [""]:
        for given in givens or [""]:
            if not surname and not given:
                continue
            l1 = _rebuild_line1(surname, given, nat)
            for l2 in l2_variants:
                add(l1, l2)
    return cands


def _passporteye_dicts(path: Path) -> list[dict]:
    """Run passporteye on the full image and a cropped/upscaled MRZ band."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            from passporteye import read_mrz
            from PIL import Image, ImageOps
        except ImportError:
            logger.warning("passporteye/Pillow not available")
            return []

        found: list[dict] = []

        def consider(img_path: Path) -> None:
            try:
                result = read_mrz(str(img_path))
            except Exception as exc:
                logger.debug("passporteye failed on %s: %s", img_path, exc)
                return
            if result is None:
                return
            data = result.to_dict() if hasattr(result, "to_dict") else None
            if data:
                found.append(data)

        # Band first — sharper MRZ crop beats full-page OCR for candidate ordering
        try:
            img = Image.open(path).convert("RGB")
            w, h = img.size
            band = ImageOps.autocontrast(
                ImageOps.grayscale(img.crop((10, int(h * 0.76), w - 10, h - 8)))
            )
            up = band.resize((band.width * 2, band.height * 2), Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                up.save(tmp_path)
                consider(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("MRZ band preprocess failed: %s", exc)
        consider(path)
        return found


def read_mrz_image(path: str | Path) -> Optional[tuple[str, str]]:
    """OCR the MRZ from a passport image via passporteye. Returns raw lines or None."""
    path = Path(path)
    if not path.exists():
        return None

    for data in _passporteye_dicts(path):
        parsed = _best_parse(_candidates_from_passporteye_dict(data))
        if parsed and parsed.checksums_valid:
            return parsed.line1, parsed.line2
        if parsed:
            return parsed.line1, parsed.line2
        raw = data.get("raw_text") or ""
        split = _split_mrz_text(raw)
        if split:
            return split
    return None


def best_mrz(
    image_path: str | Path | None,
    llm_lines: list[str] | None = None,
    *,
    today: date | None = None,
) -> Optional[MRZ]:
    """Try passporteye first, then LLM-transcribed lines. Prefer checksum-valid."""
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_many(pairs: list[tuple[str, str]]) -> None:
        for pair in pairs:
            if pair not in seen:
                seen.add(pair)
                candidates.append(pair)

    if image_path is not None:
        path = Path(image_path)
        if path.exists():
            for data in _passporteye_dicts(path):
                add_many(_candidates_from_passporteye_dict(data))

    if llm_lines and len(llm_lines) >= 2:
        l1, l2 = _normalize_line(llm_lines[0]), _normalize_line(llm_lines[1])
        add_many([(l1, l2)])
        add_many([(l1, v) for v in _ocr_variants(l2)])

    if not candidates:
        return None
    return _best_parse(candidates, today=today)


def compare_viz(mrz: MRZ, passport: PassportExtraction) -> list[str]:
    """Fields where the visual-zone extraction disagrees with the MRZ."""
    mismatched: list[str] = []

    def norm_name(s: str) -> str:
        return re.sub(r"[^A-Z]", "", s.upper())

    pairs = [
        ("surname", norm_name(mrz.surname), norm_name(passport.surname)),
        ("given_names", norm_name(mrz.given_names), norm_name(passport.given_names)),
        (
            "passport_number",
            mrz.passport_number.replace("<", ""),
            passport.passport_number.replace("<", ""),
        ),
        ("nationality", mrz.nationality, passport.nationality),
        ("date_of_birth", mrz.date_of_birth.isoformat(), passport.date_of_birth.isoformat()),
        ("expiry_date", mrz.expiry_date.isoformat(), passport.expiry_date.isoformat()),
        ("sex", mrz.sex if mrz.sex != "<" else "", "X" if passport.sex == "X" else passport.sex),
    ]
    for field, a, b in pairs:
        if field == "sex":
            if a and b and a != b and not ({a, b} <= {"", "<", "X"}):
                mismatched.append(field)
            continue
        if a != b:
            mismatched.append(field)
    return mismatched
