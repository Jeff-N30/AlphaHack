"""Passport MRZ: passporteye OCR + ICAO 9303 check digits (mrz lib).

AI does not decide validity — checksums do. OCR confusions (O/0, I/1) are
resolved only when a candidate makes every ICAO hash validate.
"""
from __future__ import annotations

import itertools
import logging
import re
import warnings
from datetime import date
from pathlib import Path
from typing import Optional

from app.models import MRZ, PassportExtraction

logger = logging.getLogger(__name__)

# TD3 line-2 layout (ICAO 9303)
_DOC_NUM = slice(0, 9)
_DOB = slice(13, 19)
_SEX = 20
_EXPIRY = slice(21, 27)
_PERSONAL = slice(28, 42)
_HASH_IDXS = (9, 19, 27, 42, 43)


def _yy_to_date(yy_mm_dd: str, *, kind: str, today: date | None = None) -> date:
    """Convert YYMMDD using the project century rules."""
    if len(yy_mm_dd) != 6 or not yy_mm_dd.isdigit():
        raise ValueError(f"invalid MRZ date: {yy_mm_dd!r}")
    yy, mm, dd = int(yy_mm_dd[:2]), int(yy_mm_dd[2:4]), int(yy_mm_dd[4:6])
    today = today or date.today()
    if kind == "expiry":
        century = 2000
    else:  # DOB
        century = 1900 if yy > (today.year % 100) else 2000
    return date(century + yy, mm, dd)


def _normalize_line(raw: str) -> str:
    s = re.sub(r"[^A-Z0-9<]", "", raw.upper().replace(" ", ""))
    if len(s) < 30:
        return s.ljust(44, "<")[:44]
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
    """Extract surname / given names from TD3 line 1."""
    body = line1[5:44] if len(line1) >= 5 else line1
    if "<<" in body:
        sur, _, rest = body.partition("<<")
        given = rest.split("<")[0]
    else:
        parts = [p for p in body.split("<") if p]
        sur = parts[0] if parts else ""
        given = parts[1] if len(parts) > 1 else ""
    return sur.replace("<", " ").strip(), given.replace("<", " ").strip()


def _given_candidates(names: str) -> list[str]:
    """OCR often appends a trailing K onto the given name (MOHAMADK).

    Strip a single trailing K first. Do not strip S — GEORGES is a real name.
    """
    toks = [t for t in re.split(r"\s+", (names or "").strip()) if t]
    toks = [t for t in toks if not re.fullmatch(r"[SKE<]+", t)]
    if not toks:
        return []
    base = toks[0]
    if len(base) > 3 and base.endswith("K"):
        return [base[:-1], base]
    return [base]


def _normalize_personal_zone(line2: str) -> str:
    """Replace OCR junk in the optional-data zone with fillers."""
    chars = list(_normalize_line(line2))
    for i in range(_PERSONAL.start, 43):
        if chars[i] in "KSE":
            chars[i] = "<"
    return "".join(chars)


def _ocr_variants(line2: str) -> list[str]:
    """Bounded O/0 I/1 swaps on identity fields + optional final-hash digits."""
    base = _normalize_personal_zone(line2)
    idxs = [
        i
        for i, c in enumerate(base)
        if c in "O0I1" and i < _PERSONAL.start
    ][:10]
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

    # If still needed, try alternate final check digit (common truncation)
    expanded: list[str] = []
    for cand in out:
        expanded.append(cand)
        if cand[43] == "<":
            for d in "0123456789":
                expanded.append(cand[:43] + d)
    # de-dupe preserve order
    final: list[str] = []
    seen2: set[str] = set()
    for s in expanded:
        if s not in seen2:
            seen2.add(s)
            final.append(s)
    return final


def _failed_checks_from_report(checker) -> list[str]:
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
    l1, l2 = _normalize_line(lines[0]), _normalize_line(lines[1])
    code = f"{l1}\n{l2}"

    from mrz.checker.td3 import TD3CodeChecker

    try:
        checker = TD3CodeChecker(code, check_expiry=False, compute_warnings=False)
    except Exception as exc:  # length / charset
        surname, given = _parse_names_from_line1(l1)
        return MRZ(
            line1=l1,
            line2=l2,
            surname=surname,
            given_names=given,
            passport_number=l2[_DOC_NUM].replace("<", ""),
            nationality=l2[10:13].replace("<", ""),
            date_of_birth=_yy_to_date(l2[_DOB], kind="dob", today=today)
            if l2[_DOB].isdigit()
            else date(1900, 1, 1),
            sex=l2[_SEX] if l2[_SEX] in "MF<" else "<",  # type: ignore[arg-type]
            expiry_date=_yy_to_date(l2[_EXPIRY], kind="expiry", today=today)
            if l2[_EXPIRY].isdigit()
            else date(2000, 1, 1),
            checksums_valid=False,
            failed_checks=[f"parse_error:{exc}"],
        )

    # Force hash + field evaluation into the report
    valid = bool(checker)
    failed = _failed_checks_from_report(checker)
    fields = checker.fields()

    surname = (fields.surname or "") if fields.surname not in (None, "None") else ""
    given = (fields.name or "") if fields.name not in (None, "None") else ""
    if not surname and not given:
        surname, given = _parse_names_from_line1(l1)

    sex_raw = (fields.sex or l2[_SEX] or "<")[:1]
    sex: str = sex_raw if sex_raw in ("M", "F", "<") else "<"

    dob_s = fields.birth_date or l2[_DOB]
    exp_s = fields.expiry_date or l2[_EXPIRY]
    number = (fields.document_number or l2[_DOC_NUM]).replace("<", "")
    nat = (fields.nationality or l2[10:13]).replace("<", "")

    return MRZ(
        line1=l1,
        line2=l2,
        surname=surname.replace("<", " ").strip(),
        given_names=given.replace("<", " ").strip(),
        passport_number=number,
        nationality=nat,
        date_of_birth=_yy_to_date(dob_s, kind="dob", today=today),
        sex=sex,  # type: ignore[arg-type]
        expiry_date=_yy_to_date(exp_s, kind="expiry", today=today),
        checksums_valid=valid,
        failed_checks=failed,
    )


def _best_parse(candidates: list[tuple[str, str]], *, today: date | None = None) -> Optional[MRZ]:
    """Return the first checksum-valid parse, else the partial with fewest failures."""
    best: MRZ | None = None
    best_score = 10_000
    for l1, l2 in candidates:
        mrz = parse_td3([l1, l2], today=today)
        if mrz.checksums_valid:
            return mrz
        score = len(mrz.failed_checks)
        if score < best_score:
            best_score = score
            best = mrz
    return best


def _candidates_from_passporteye_dict(data: dict) -> list[tuple[str, str]]:
    raw = data.get("raw_text") or ""
    split = _split_mrz_text(raw)
    line2 = None
    if split:
        line2 = split[1]
    # Prefer a dedicated line-2 extraction (line-1 from PE is often truncated)
    for ln in raw.upper().splitlines():
        s = re.sub(r"[^A-Z0-9<]", "", ln.replace(" ", ""))
        if len(s) >= 40 and not s.startswith("P"):
            line2 = _normalize_line(s)
            break
    if not line2 and split:
        line2 = split[1]
    if not line2:
        return []

    nat = (data.get("nationality") or data.get("country") or "LBN").replace("<", "")[:3]
    surname = (data.get("surname") or "").replace("<", " ").strip()
    givens = _given_candidates(data.get("names") or "")
    if split:
        sur_r, giv_r = _parse_names_from_line1(split[0])
        if sur_r and sur_r not in (surname,):
            surname = surname or sur_r
        if giv_r:
            for g in _given_candidates(giv_r):
                if g not in givens:
                    givens.append(g)

    cands: list[tuple[str, str]] = []
    for given in givens or [""]:
        l1 = _rebuild_line1(surname, given, nat)
        for l2 in _ocr_variants(line2):
            cands.append((l1, l2))
    if split:
        for l2 in _ocr_variants(line2):
            cands.append((split[0], l2))
    return cands


def read_mrz_image(path: str | Path) -> Optional[tuple[str, str]]:
    """OCR the MRZ from a passport image via passporteye. Returns raw lines or None."""
    path = Path(path)
    if not path.exists():
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            from passporteye import read_mrz
            from PIL import Image, ImageOps
        except ImportError:
            logger.warning("passporteye/Pillow not available")
            return None

        attempts: list = []

        def consider(img_path: Path) -> None:
            try:
                result = read_mrz(str(img_path))
            except Exception as exc:
                logger.debug("passporteye failed on %s: %s", img_path, exc)
                return
            if result is None:
                return
            data = result.to_dict() if hasattr(result, "to_dict") else {}
            raw = data.get("raw_text")
            if raw:
                split = _split_mrz_text(raw)
                if split:
                    attempts.append(split)
            # Also keep PE structured rebuild candidates via side channel
            attempts.append(("__pe__", data))  # type: ignore[arg-type]

        consider(path)

        try:
            img = Image.open(path).convert("RGB")
            w, h = img.size
            band = img.crop((10, int(h * 0.76), w - 10, h - 8))
            gray = ImageOps.autocontrast(ImageOps.grayscale(band))
            up = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
            tmp = path.parent / f".{path.stem}_mrz_band.png"
            try:
                up.save(tmp)
                consider(tmp)
            finally:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("MRZ band preprocess failed: %s", exc)

    # Prefer a PE dict payload for rebuild; else first text split
    for item in attempts:
        if item and item[0] == "__pe__":
            data = item[1]  # type: ignore[index]
            cands = _candidates_from_passporteye_dict(data)  # type: ignore[arg-type]
            parsed = _best_parse(cands)
            if parsed and parsed.checksums_valid:
                return parsed.line1, parsed.line2
            if parsed:
                return parsed.line1, parsed.line2
    for item in attempts:
        if item and item[0] != "__pe__":
            return item[0], item[1]  # type: ignore[return-value]
    return None


def best_mrz(
    image_path: str | Path | None,
    llm_lines: list[str] | None = None,
    *,
    today: date | None = None,
) -> Optional[MRZ]:
    """Try passporteye first, then LLM-transcribed lines. Prefer checksum-valid."""
    candidates: list[tuple[str, str]] = []

    if image_path is not None:
        raw = read_mrz_image(image_path)
        if raw:
            # Expand OCR variants around whatever we got
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    from passporteye import read_mrz
                    from PIL import Image, ImageOps

                    img = Image.open(image_path).convert("RGB")
                    w, h = img.size
                    band = ImageOps.autocontrast(
                        ImageOps.grayscale(img.crop((10, int(h * 0.76), w - 10, h - 8)))
                    )
                    up = band.resize((band.width * 2, band.height * 2), Image.Resampling.LANCZOS)
                    tmp = Path(image_path).parent / f".{Path(image_path).stem}_mrz_band2.png"
                    up.save(tmp)
                    pe = read_mrz(str(tmp))
                    tmp.unlink(missing_ok=True)
                    if pe is not None:
                        candidates.extend(_candidates_from_passporteye_dict(pe.to_dict()))
                except Exception:
                    pass
            for l2 in _ocr_variants(raw[1]):
                candidates.append((raw[0], l2))
                # rebuild line1 from parsed names if possible
                sur, giv = _parse_names_from_line1(raw[0])
                if sur:
                    for g in _given_candidates(giv) or [giv]:
                        candidates.append((_rebuild_line1(sur, g, "LBN"), l2))

    if llm_lines and len(llm_lines) >= 2:
        l1, l2 = _normalize_line(llm_lines[0]), _normalize_line(llm_lines[1])
        candidates.append((l1, l2))
        for v in _ocr_variants(l2):
            candidates.append((l1, v))

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
        ("passport_number", mrz.passport_number.replace("<", ""), passport.passport_number.replace("<", "")),
        ("nationality", mrz.nationality, passport.nationality),
        ("date_of_birth", mrz.date_of_birth.isoformat(), passport.date_of_birth.isoformat()),
        ("expiry_date", mrz.expiry_date.isoformat(), passport.expiry_date.isoformat()),
        ("sex", mrz.sex if mrz.sex != "<" else "", "X" if passport.sex == "X" else passport.sex),
    ]
    for field, a, b in pairs:
        if field == "sex":
            # MRZ '<' vs VIZ 'X' both mean unspecified — treat as match if either empty-like
            if a and b and a != b and not ({a, b} <= {"", "<", "X"}):
                mismatched.append(field)
            continue
        if a != b:
            mismatched.append(field)
    return mismatched
