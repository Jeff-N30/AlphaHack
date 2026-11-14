#!/usr/bin/env python3
"""Generate FAKE applicant documents from eval/cases/<case>/case.yaml.

  python tools/generate_fake_docs.py                 # all cases
  python tools/generate_fake_docs.py case04_name_mismatch --degrade   # + phone-photo style copies

Output: eval/cases/<case>/docs/  (passport.png with valid ICAO 9303 TD3 MRZ, PDFs for the rest)
Every page has a SPECIMEN / FAKE watermark. Never put real personal data in case.yaml.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "cases"
MONO = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf", "Courier New.ttf", "cour.ttf"]
SANS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf", "Arial.ttf", "arial.ttf"]
WATERMARK = "SPECIMEN - FAKE TEST DATA - ALPHAHACK 2026"


# ------------------------------------------------------------------ MRZ (ICAO 9303)
def _val(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    return ord(c) - 55  # A=10


def check_digit(s: str) -> str:
    w = (7, 3, 1)
    return str(sum(_val(c) * w[i % 3] for i, c in enumerate(s)) % 10)


def _f(s: str) -> str:
    return "".join(ch if ch.isalnum() else "<" for ch in s.upper().replace("-", " ").replace(" ", "<"))


def td3(surname, given, number, nat, dob: date, sex, exp: date, personal="") -> tuple[str, str]:
    l1 = ("P<" + nat + _f(surname) + "<<" + _f(given)).ljust(44, "<")[:44]
    num = _f(number).ljust(9, "<")[:9]
    d, e = dob.strftime("%y%m%d"), exp.strftime("%y%m%d")
    pers = _f(personal).ljust(14, "<")[:14]
    pcd = check_digit(pers) if personal else "<"
    part = num + check_digit(num) + nat + d + check_digit(d) + sex + e + check_digit(e) + pers + pcd
    comp = num + check_digit(num) + d + check_digit(d) + e + check_digit(e) + pers + pcd
    l2 = part + check_digit(comp)
    assert len(l1) == 44 and len(l2) == 44, (l1, l2)
    return l1, l2


# ------------------------------------------------------------------ helpers
def font(cands, size):
    for c in cands:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fmt(v):
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, dict) and {"amount", "currency"} <= v.keys():
        return f"{v['amount']:,.2f} {v['currency']}"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


# ------------------------------------------------------------------ passport PNG
def render_passport(d: dict, out: Path) -> tuple[str, str]:
    W, H = 1250, 880
    img = Image.new("RGB", (W, H), (236, 241, 232))
    g = ImageDraw.Draw(img)
    f_lbl, f_val, f_big = font(SANS, 20), font(SANS, 28), font(SANS, 34)
    g.rectangle([0, 0, W, 90], fill=(20, 90, 60))
    g.text((30, 25), "REPUBLIC OF LEBANON  -  PASSPORT  (SPECIMEN)", font=f_big, fill="white")
    g.rectangle([40, 130, 340, 520], fill=(200, 205, 200), outline=(90, 90, 90), width=3)
    g.text((110, 310), "PHOTO", font=f_big, fill=(120, 120, 120))
    fields = [
        ("Type / Code / Passport No.", f"P   LBN   {d['passport_number']}"),
        ("Surname", d["surname"]), ("Given names", d["given_names"]),
        ("Nationality", "LEBANESE"), ("Date of birth", fmt(d["date_of_birth"])), ("Sex", d["sex"]),
        ("Place of issue", d.get("place_of_issue", "BEIRUT")),
        ("Date of issue", fmt(d["issue_date"])), ("Date of expiry", fmt(d["expiry_date"])),
    ]
    y = 120
    for lbl, val in fields:
        g.text((380, y), lbl, font=f_lbl, fill=(80, 80, 80))
        g.text((380, y + 22), str(val), font=f_val, fill="black")
        y += 62
    l1, l2 = td3(d["surname"], d["given_names"], d["passport_number"], d.get("nationality", "LBN"),
                 d["date_of_birth"], d["sex"], d["expiry_date"])
    g.rectangle([0, H - 170, W, H], fill=(250, 250, 250))
    f_mrz = font(MONO, 40)  # OCR-B is better for passporteye/tesseract; drop OCRB.ttf next to this script if you have it
    for p in (Path(__file__).parent / "OCRB.ttf",):
        if p.exists():
            f_mrz = ImageFont.truetype(str(p), 40)
    g.text((30, H - 150), l1, font=f_mrz, fill="black")
    g.text((30, H - 85), l2, font=f_mrz, fill="black")
    # watermark
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)  # kept clear of the data fields so it does not hurt OCR
    for i, line in enumerate(("SPECIMEN", "FAKE TEST DATA", "ALPHAHACK 2026")):
        wd.text((860, 200 + i * 60), line, font=font(SANS, 40), fill=(200, 30, 30, 110))
    img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")
    img.save(out)
    return l1, l2


def render_photo(out: Path):
    img = Image.new("RGB", (413, 531), "white")  # 35x45mm @300dpi
    g = ImageDraw.Draw(img)
    g.ellipse([120, 90, 290, 300], fill=(190, 190, 190))
    g.rectangle([80, 320, 330, 531], fill=(170, 170, 170))
    g.text((95, 20), "SPECIMEN PHOTO", font=font(SANS, 28), fill=(200, 30, 30))
    img.save(out)


# ------------------------------------------------------------------ generic PDFs
TITLES = {
    "application_form": "France-Visas - Short-stay visa application (printout) - SPECIMEN",
    "flight_booking": "E-TICKET ITINERARY RECEIPT - SPECIMEN AIRLINES",
    "hotel_booking": "BOOKING CONFIRMATION",
    "travel_insurance": "SCHENGEN TRAVEL INSURANCE CERTIFICATE",
    "bank_statement": "ACCOUNT STATEMENT",
    "employment_letter": "TO WHOM IT MAY CONCERN - EMPLOYMENT CERTIFICATE",
    "payslip": "PAYSLIP",
    "cnss_certificate": "NATIONAL SOCIAL SECURITY FUND (CNSS) - REGISTRATION CERTIFICATE",
    "family_register": "EXTRACT OF FAMILY REGISTER (EKHRAJ KAID AILY) - TRANSLATION",
    "travel_plan": "TRAVEL PLAN",
}
SKIP = {"file", "transactions", "segments", "has_bank_stamp", "signed_and_stamped", "signed", "translated"}  # visual cues, not printed text


def pdf(doc_type: str, d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    c.saveState(); c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.18)); c.setFont("Helvetica-Bold", 30)
    c.translate(W / 2, H / 2); c.rotate(35); c.drawCentredString(0, 0, WATERMARK); c.restoreState()
    c.setFont("Helvetica-Bold", 14); c.drawString(20 * mm, H - 25 * mm, TITLES.get(doc_type, doc_type.upper()))
    c.setFont("Helvetica", 10); y = H - 40 * mm
    for k, v in d.items():
        if k in SKIP:
            continue
        if isinstance(v, str) and any("\u0600" <= ch <= "\u06ff" for ch in v):
            continue  # Arabic shaping needs arabic-reshaper + python-bidi; skipped in PDFs
        c.drawString(20 * mm, y, f"{k.replace('_', ' ').title()}:"); c.drawString(75 * mm, y, fmt(v)); y -= 7 * mm
    if "segments" in d:
        y -= 4 * mm; c.setFont("Helvetica-Bold", 10); c.drawString(20 * mm, y, "Flight   From  To   Date"); y -= 6 * mm
        c.setFont("Helvetica", 10)
        for s in d["segments"]:
            c.drawString(20 * mm, y, f"{s.get('flight_number', ''):8} {s['from_airport']}   {s['to_airport']}  {fmt(s['departure_date'])}"); y -= 6 * mm
    if "transactions" in d:
        y -= 4 * mm; c.setFont("Helvetica-Bold", 10); c.drawString(20 * mm, y, "Date        Description                                   Amount"); y -= 6 * mm
        c.setFont("Helvetica", 10)
        for t in sorted(d["transactions"], key=lambda t: t["date"]):
            c.drawString(20 * mm, y, f"{fmt(t['date'])}  {t['description'][:42]:44} {t['amount']:>10,.2f}"); y -= 5.5 * mm
    if d.get("signed") or d.get("signed_and_stamped"):
        c.setFont("Helvetica-Oblique", 12); c.drawString(20 * mm, 45 * mm, "Signature: ~~~~~~~~ (fake)")
    if d.get("has_bank_stamp") or d.get("signed_and_stamped"):
        c.setStrokeColor(colors.blue); c.setFillColor(colors.blue); c.circle(160 * mm, 40 * mm, 18 * mm)
        c.setFont("Helvetica-Bold", 9); c.drawCentredString(160 * mm, 40 * mm, "STAMP (FAKE)")
    c.showPage(); c.save()


def degrade(src: Path):
    """Phone-photo style copy: slight rotation, blur, JPEG. For robustness tests (scale to 20 cases)."""
    if src.suffix.lower() != ".png":
        return
    im = Image.open(src).convert("RGB").rotate(random.uniform(-3, 3), expand=True, fillcolor=(40, 40, 40))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(src.with_name(src.stem + "_phone.jpg"), quality=55)


# ------------------------------------------------------------------ main
def build(case_dir: Path, do_degrade: bool) -> list[str]:
    case = yaml.safe_load((case_dir / "case.yaml").read_text())
    out = case_dir / "docs"; out.mkdir(exist_ok=True)
    made = []
    for dtype, spec in case["documents"].items():
        for d in (spec if isinstance(spec, list) else [spec]):
            p = out / d["file"]
            if dtype == "passport":
                l1, l2 = render_passport(d, p)
                (out / "passport_mrz.txt").write_text(l1 + "\n" + l2 + "\n")  # ground truth for MRZ tests
            elif dtype == "photo":
                render_photo(p)
            else:
                pdf(dtype, d, p)
            made.append(p.name)
            if do_degrade:
                degrade(p)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--degrade", action="store_true")
    a = ap.parse_args()
    dirs = [CASES / c for c in a.cases] if a.cases else sorted(p for p in CASES.iterdir() if (p / "case.yaml").exists())
    for d in dirs:
        made = build(d, a.degrade)
        print(f"{d.name}: {len(made)} files -> {d / 'docs'}")
    # self-check MRZ with an independent implementation
    try:
        from mrz.checker.td3 import TD3CodeChecker
        for d in dirs:
            txt = (d / "docs" / "passport_mrz.txt").read_text().strip()
            ok = bool(TD3CodeChecker(txt))
            print(f"  MRZ {d.name}: {'valid' if ok else 'INVALID'}")
            if not ok:
                sys.exit(1)
    except ImportError:
        print("  (pip install mrz to self-verify MRZ check digits)")


if __name__ == "__main__":
    main()
