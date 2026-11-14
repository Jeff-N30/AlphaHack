#!/usr/bin/env python3
"""Generate FAKE Lebanese→France visa docs from eval/cases/<case>/case.yaml.

Realistic-looking SPECIMEN documents only. Never real personal data.

  python tools/generate_fake_docs.py
  python tools/generate_fake_docs.py case01_complete --degrade
"""
from __future__ import annotations

import argparse
import random
import re
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
TOOLS = Path(__file__).resolve().parent
WATERMARK = "SPECIMEN — FAKE TEST DATA — ALPHAHACK 2026 · NOT A REAL DOCUMENT"

# macOS + Linux font candidates
SANS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
]
SANS_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "Arial Bold.ttf",
    *SANS,
]
MONO = [
    str(TOOLS / "OCRB.ttf"),
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "Courier New.ttf",
]


# ------------------------------------------------------------------ MRZ
def _val(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    return ord(c) - 55


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
def font(cands, size: int):
    for c in cands:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def as_date(v) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def fmt(v) -> str:
    if isinstance(v, date) or (isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", str(v))):
        try:
            return as_date(v).strftime("%d/%m/%Y")
        except ValueError:
            pass
    if isinstance(v, dict) and {"amount", "currency"} <= v.keys():
        return f"{v['amount']:,.2f} {v['currency']}"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def _wm_pdf(c: canvas.Canvas, W, H):
    c.saveState()
    c.setFillColor(colors.Color(0.75, 0.12, 0.12, alpha=0.12))
    c.setFont("Helvetica-Bold", 22)
    c.translate(W / 2, H / 2)
    c.rotate(32)
    c.drawCentredString(0, 20, "SPECIMEN / FAKE / ALPHAHACK 2026")
    c.drawCentredString(0, -20, "NOT A REAL DOCUMENT")
    c.restoreState()


def _footer(c: canvas.Canvas, W):
    c.setFillColor(colors.Color(0.4, 0.4, 0.4))
    c.setFont("Helvetica", 7)
    c.drawString(18 * mm, 10 * mm, WATERMARK)


def _stamp(c: canvas.Canvas, x, y, label="BANK STAMP"):
    c.saveState()
    c.setStrokeColor(colors.Color(0.05, 0.25, 0.65))
    c.setFillColor(colors.Color(0.05, 0.25, 0.65, alpha=0.15))
    c.setLineWidth(2)
    c.circle(x, y, 16 * mm, fill=1, stroke=1)
    c.setFillColor(colors.Color(0.05, 0.25, 0.65))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x, y + 2 * mm, label)
    c.setFont("Helvetica", 7)
    c.drawCentredString(x, y - 4 * mm, "FAKE")
    c.restoreState()


def _draw_cedar(g: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0, fill=(200, 180, 100)):
    """Simple Lebanese cedar emblem (decorative SPECIMEN)."""
    s = scale
    # trunk
    g.rectangle([cx - int(6 * s), cy + int(8 * s), cx + int(6 * s), cy + int(38 * s)], fill=fill)
    # layered canopy (triangle stack)
    for i, (w, h, dy) in enumerate([(55, 28, -5), (42, 22, -22), (28, 16, -36)]):
        g.polygon(
            [
                (cx, cy + int(dy * s) - int(h * s)),
                (cx - int(w * s), cy + int(dy * s) + int(8 * s)),
                (cx + int(w * s), cy + int(dy * s) + int(8 * s)),
            ],
            fill=fill,
        )


def _draw_epasport_chip(g: ImageDraw.ImageDraw, x: int, y: int, size: int = 56):
    """ISO/IEC biometric passport chip pictogram (rectangle + circles)."""
    g.rounded_rectangle([x, y, x + size, y + int(size * 0.72)], radius=6, outline=(40, 55, 40), width=2)
    cx, cy = x + size // 2, y + int(size * 0.36)
    for r in (18, 12, 6):
        g.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(40, 55, 40), width=2)
    g.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(40, 55, 40))


# ------------------------------------------------------------------ PASSPORT (Lebanese biometric biodata mock)
def render_passport(d: dict, out: Path) -> tuple[str, str]:
    """Mock Lebanese ePassport biodata page (ICAO TD3). SPECIMEN / fake data only."""
    # ~ ID-3 proportions at high res
    W, H = 1575, 1110
    paper = (232, 238, 230)
    green = (8, 58, 38)
    gold = (176, 148, 72)
    ink = (15, 28, 18)
    label_c = (55, 75, 58)

    img = Image.new("RGB", (W, H), paper)
    g = ImageDraw.Draw(img)

    # security underprint (fine waves)
    for i in range(0, H - 210, 7):
        pts = [(x, i + int(4 * __import__("math").sin(x / 28.0 + i / 17.0))) for x in range(0, W, 4)]
        if len(pts) > 1:
            g.line(pts, fill=(210, 220, 208), width=1)
    for i in range(0, W, 14):
        g.line([(i, 0), (i + 55, H - 210)], fill=(218, 226, 216), width=1)

    # top security strip
    g.rectangle([0, 0, W, 108], fill=green)
    g.rectangle([0, 108, W, 114], fill=gold)
    _draw_cedar(g, 70, 48, scale=0.85, fill=gold)
    f_h1 = font(SANS_BOLD, 34)
    f_h2 = font(SANS, 20)
    g.text((130, 22), "REPUBLIC OF LEBANON", font=f_h1, fill=(245, 238, 210))
    g.text((130, 64), "PASSEPORT BIOMETRIQUE  ·  BIOMETRIC PASSPORT", font=f_h2, fill=(220, 205, 150))
    _draw_epasport_chip(g, W - 100, 28, 64)
    g.text((W - 280, 48), "SPECIMEN", font=font(SANS_BOLD, 26), fill=(230, 70, 70))

    # photo (white biometric-style background)
    px0, py0, px1, py1 = 48, 140, 348, 530
    g.rectangle([px0 - 4, py0 - 4, px1 + 4, py1 + 4], outline=green, width=3)
    g.rectangle([px0, py0, px1, py1], fill=(248, 248, 248))
    # soft silhouette (not a real face)
    g.ellipse([120, 190, 276, 370], fill=(168, 172, 168))
    g.polygon([(110, 520), (158, 360), (238, 360), (286, 520)], fill=(150, 154, 150))
    g.text((145, 150), "PHOTO", font=font(SANS, 14), fill=(140, 140, 140))

    # signature under photo
    g.text((48, 545), "Signature / Signature du titulaire", font=font(SANS, 13), fill=label_c)
    g.line([(48, 600), (348, 600)], fill=ink, width=2)
    sig = f"{str(d['given_names'])[:1]}. {str(d['surname']).title()}"
    g.text((60, 568), sig, font=font(SANS, 22), fill=ink)

    # compact ICAO-style field grid (EN/FR labels, Latin values only)
    f_lbl = font(SANS, 13)
    f_val = font(SANS_BOLD, 24)
    f_val_sm = font(SANS_BOLD, 18)

    def field(x: int, y: int, label: str, value: str, w: int = 520) -> None:
        g.text((x, y), label, font=f_lbl, fill=label_c)
        g.text((x, y + 18), value, font=f_val if len(value) < 28 else f_val_sm, fill=ink)
        g.line([(x, y + 50), (x + w, y + 50)], fill=(190, 200, 188), width=1)

    # row 1: type / code / number
    field(390, 140, "1/2 Type / Code", "P / LBN", 200)
    field(620, 140, "3 Passport No. / N° de passeport", str(d["passport_number"]), 400)
    field(390, 210, "4 Surname / Nom", str(d["surname"]), 700)
    field(390, 280, "5 Given names / Prénoms", str(d["given_names"]), 700)
    field(390, 350, "6 Nationality / Nationalité", "LEBANESE / LIBANAISE", 700)

    field(390, 420, "7 Date of birth / Naissance", fmt(d["date_of_birth"]), 280)
    field(720, 420, "8 Sex / Sexe", str(d["sex"]), 180)
    field(940, 420, "9 Place of birth", str(d.get("place_of_issue", "BEIRUT")), 280)

    field(390, 490, "10 Date of issue / Délivrance", fmt(d["issue_date"]), 320)
    field(760, 490, "11 Date of expiry / Expiration", fmt(d["expiry_date"]), 360)

    field(390, 560, "12 Authority / Autorité", "GENERAL SECURITY — BEIRUT (FAKE SPECIMEN)", 750)

    # secondary ghost photo (common on biometric pages) — tiny
    g.rectangle([1280, 140, 1480, 360], outline=(160, 175, 160), width=1)
    g.ellipse([1335, 170, 1425, 270], fill=(200, 205, 200))
    g.rectangle([1325, 265, 1435, 350], fill=(185, 190, 185))
    g.text((1310, 365), "ghost image", font=font(SANS, 11), fill=(150, 150, 150))

    # document number microprint line
    g.text(
        (48, 620),
        f"Document: {d['passport_number']}  ·  ePassport  ·  MOCK DESIGN — NOT ISSUED BY THE STATE",
        font=font(SANS, 12),
        fill=(100, 110, 100),
    )

    # MRZ band (must stay clean for passporteye)
    l1, l2 = td3(
        d["surname"],
        d["given_names"],
        d["passport_number"],
        d.get("nationality", "LBN"),
        as_date(d["date_of_birth"]),
        d["sex"],
        as_date(d["expiry_date"]),
    )
    mrz_top = H - 220
    g.rectangle([0, mrz_top, W, H], fill=(250, 250, 247))
    g.rectangle([0, mrz_top, W, mrz_top + 5], fill=green)
    f_mrz = font(MONO, 44)
    g.text((48, mrz_top + 35), l1, font=f_mrz, fill=(0, 0, 0))
    g.text((48, mrz_top + 110), l2, font=f_mrz, fill=(0, 0, 0))

    # light SPECIMEN overlay (avoid covering MRZ)
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wd.text((980, 640), "SPECIMEN", font=font(SANS_BOLD, 48), fill=(200, 40, 40, 90))
    wd.text((980, 700), "FAKE — ALPHAHACK", font=font(SANS_BOLD, 22), fill=(200, 40, 40, 80))
    img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")
    img.save(out, quality=95)
    return l1, l2


def render_photo(out: Path):
    """35×45 mm style ID photo — grey silhouette, not a real face."""
    img = Image.new("RGB", (413, 531), (245, 245, 248))
    g = ImageDraw.Draw(img)
    g.rectangle([0, 0, 413, 531], outline=(200, 200, 200), width=2)
    g.ellipse([120, 90, 290, 290], fill=(175, 178, 185))
    g.rectangle([90, 280, 320, 520], fill=(155, 158, 165))
    g.text((70, 20), "SPECIMEN ID PHOTO", font=font(SANS_BOLD, 22), fill=(180, 40, 40))
    g.text((95, 500), "NOT A REAL PERSON", font=font(SANS, 14), fill=(120, 120, 120))
    img.save(out)


# ------------------------------------------------------------------ PDF document types
def pdf_application_form(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFillColor(colors.Color(0.0, 0.2, 0.45))
    c.rect(0, H - 28 * mm, W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, H - 14 * mm, "France-Visas — Short-stay (C) application printout")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 20 * mm, "SPECIMEN · TLS Beirut demo · match passport exactly")
    c.setFillColor(colors.black)
    y = H - 40 * mm
    fields = [
        ("France-Visas reference", d.get("france_visas_reference", "")),
        ("Surname", d.get("surname")),
        ("Given names", d.get("given_names")),
        ("Date of birth", fmt(d.get("date_of_birth"))),
        ("Passport number", d.get("passport_number")),
        ("Passport expiry", fmt(d.get("expiry_date"))),
        ("Intended arrival", fmt(d.get("intended_arrival"))),
        ("Intended departure", fmt(d.get("intended_departure"))),
    ]
    c.setFont("Helvetica", 10)
    for lbl, val in fields:
        c.setFillColor(colors.Color(0.3, 0.3, 0.3))
        c.drawString(20 * mm, y, lbl)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(75 * mm, y, str(val))
        c.setFont("Helvetica", 10)
        y -= 9 * mm
    if d.get("signed"):
        c.drawString(20 * mm, 40 * mm, "Applicant signature: __________________  (signed — SPECIMEN)")
        c.drawString(20 * mm, 32 * mm, "Receipt signed in person at TLScontact Beirut (FAKE)")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_flight(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFillColor(colors.Color(0.05, 0.15, 0.35))
    c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(18 * mm, H - 14 * mm, "SPECIMEN AIRLINES — E-TICKET / ITINERARY RECEIPT")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 22 * mm, f"Booking ref: {d.get('booking_reference', '')}   ·   Not a real ticket")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(18 * mm, H - 42 * mm, f"Passenger: {', '.join(d.get('passenger_names') or [])}")
    c.drawString(18 * mm, H - 50 * mm, f"Passport: {d.get('passport_number', '—')}")
    y = H - 65 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(18 * mm, y, "Flight")
    c.drawString(45 * mm, y, "From")
    c.drawString(70 * mm, y, "To")
    c.drawString(95 * mm, y, "Date")
    c.drawString(130 * mm, y, "Country")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    for s in d.get("segments") or []:
        c.drawString(18 * mm, y, str(s.get("flight_number", "")))
        c.drawString(45 * mm, y, s["from_airport"])
        c.drawString(70 * mm, y, s["to_airport"])
        c.drawString(95 * mm, y, fmt(s["departure_date"]))
        c.drawString(130 * mm, y, str(s.get("to_country", "")))
        y -= 8 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(18 * mm, 25 * mm, "Reservation may be unpaid hold — accepted as travel proof for visa file (demo).")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_hotel(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(18 * mm, H - 25 * mm, "BOOKING CONFIRMATION")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.Color(0.4, 0.1, 0.1))
    c.drawString(18 * mm, H - 32 * mm, "SPECIMEN HOTEL VOUCHER — FAKE")
    c.setFillColor(colors.black)
    y = H - 48 * mm
    rows = [
        ("Hotel", d.get("hotel_name")),
        ("City / Country", f"{d.get('city', '')} / {d.get('country', '')}"),
        ("Guest(s)", ", ".join(d.get("guest_names") or [])),
        ("Check-in", fmt(d.get("check_in"))),
        ("Check-out", fmt(d.get("check_out"))),
        ("Confirmation", d.get("confirmation_number")),
        ("Prepaid / free cancel", str(d.get("prepaid_or_free_cancellation"))),
    ]
    for lbl, val in rows:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawString(18 * mm, y, lbl)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(70 * mm, y, str(val)[:70])
        y -= 10 * mm
    # bilingual line for FR/AR edge cases — Latin fields remain source of truth
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, y - 5 * mm, "Hébergement confirmé · Confirmed lodging (translation/demo)")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_insurance(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFillColor(colors.Color(0.0, 0.35, 0.3))
    c.rect(0, H - 28 * mm, W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, H - 16 * mm, "SCHENGEN TRAVEL MEDICAL INSURANCE CERTIFICATE")
    c.setFillColor(colors.black)
    cov = d.get("coverage") or {}
    y = H - 45 * mm
    rows = [
        ("Insurer", d.get("insurer")),
        ("Policy number", d.get("policy_number")),
        ("Insured", d.get("insured_name")),
        ("Date of birth", fmt(d.get("date_of_birth"))),
        ("Passport", d.get("passport_number")),
        ("Coverage", fmt(cov) if isinstance(cov, dict) else cov),
        ("Territory", f"{d.get('territory')} ({d.get('territory_raw', '')})"),
        ("Valid from", fmt(d.get("start_date"))),
        ("Valid until", fmt(d.get("end_date"))),
        ("Covers", ", ".join(d.get("covers") or [])),
    ]
    for lbl, val in rows:
        c.setFont("Helvetica", 9)
        c.drawString(18 * mm, y, lbl)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(65 * mm, y, str(val)[:80])
        y -= 9 * mm
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, y - 5 * mm, "Minimum medical + repatriation EUR 30,000 — Schengen area (SPECIMEN).")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_bank(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, H - 22 * mm, str(d.get("bank_name", "BANK")))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, H - 30 * mm, "ACCOUNT STATEMENT — PERSONAL")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 38 * mm, "SPECIMEN · Fresh/external account usable abroad (demo)")
    y = H - 50 * mm
    meta = [
        ("Account holder", d.get("account_holder")),
        ("Currency", d.get("account_currency")),
        ("Account type", d.get("account_type_raw")),
        ("Period", f"{fmt(d.get('period_start'))} → {fmt(d.get('period_end'))}"),
        ("Issue date", fmt(d.get("issue_date"))),
        ("Opening balance", f"{d.get('opening_balance', 0):,.2f}"),
        ("Closing balance", f"{d.get('closing_balance', 0):,.2f}"),
    ]
    for lbl, val in meta:
        c.setFont("Helvetica", 9)
        c.drawString(18 * mm, y, lbl)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60 * mm, y, str(val)[:70])
        y -= 7 * mm
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, y, "Date")
    c.drawString(45 * mm, y, "Description")
    c.drawString(150 * mm, y, "Amount")
    y -= 6 * mm
    c.setFont("Helvetica", 8)
    for t in sorted(d.get("transactions") or [], key=lambda t: as_date(t["date"])):
        if y < 40 * mm:
            break
        c.drawString(18 * mm, y, fmt(t["date"]))
        c.drawString(45 * mm, y, str(t["description"])[:55])
        c.drawRightString(190 * mm, y, f"{float(t['amount']):,.2f}")
        y -= 5 * mm
    if d.get("has_bank_stamp"):
        _stamp(c, 160 * mm, 32 * mm, "BANK STAMP")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_employment(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, H - 25 * mm, str(d.get("employer_name", "EMPLOYER")))
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 32 * mm, "Beirut, Lebanon · SPECIMEN company letterhead")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(W / 2, H - 50 * mm, "TO WHOM IT MAY CONCERN")
    c.setFont("Helvetica", 10)
    body = (
        f"This is to certify that {d.get('employee_name')} has been employed with our company "
        f"as {d.get('position')} since {fmt(d.get('hire_date'))}. "
        f"Monthly salary: {fmt(d.get('monthly_salary'))}. "
        f"Leave of absence is approved from {fmt(d.get('leave_start'))} to {fmt(d.get('leave_end'))} "
        f"for tourism travel to France / Schengen."
    )
    # simple wrap
    y = H - 70 * mm
    words = body.split()
    line = ""
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, "Helvetica", 10) > 160 * mm:
            c.drawString(20 * mm, y, line)
            y -= 7 * mm
            line = w
        else:
            line = trial
    if line:
        c.drawString(20 * mm, y, line)
        y -= 12 * mm
    c.drawString(20 * mm, y, f"Letter date: {fmt(d.get('letter_date'))}")
    if d.get("signed_and_stamped"):
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(20 * mm, 50 * mm, "HR Manager  ________________  (signed)")
        _stamp(c, 150 * mm, 48 * mm, "COMPANY")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_payslip(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, H - 25 * mm, "PAYSLIP / BULLETIN DE PAIE — SPECIMEN")
    c.setFont("Helvetica", 10)
    y = H - 45 * mm
    for lbl, val in [
        ("Employer", d.get("employer_name")),
        ("Employee", d.get("employee_name")),
        ("Period (YYYY-MM)", d.get("period_month")),
        ("Net pay", fmt(d.get("net_pay"))),
        ("Issue date", fmt(d.get("issue_date"))),
    ]:
        c.drawString(20 * mm, y, f"{lbl}:")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(70 * mm, y, str(val))
        c.setFont("Helvetica", 10)
        y -= 10 * mm
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_cnss(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, H - 30 * mm, "NATIONAL SOCIAL SECURITY FUND (CNSS)")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W / 2, H - 38 * mm, "Registration certificate — SPECIMEN (Lebanon)")
    c.setFont("Helvetica", 10)
    names = ", ".join(d.get("names_found") or [])
    c.drawString(25 * mm, H - 60 * mm, f"Registered person: {names}")
    c.drawString(25 * mm, H - 70 * mm, "Status: Active contributor (FAKE DEMO)")
    c.drawString(25 * mm, H - 80 * mm, "This document is invented for AlphaHack 2026 testing only.")
    _stamp(c, 105 * mm, 50 * mm, "CNSS")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_ekhraj(d: dict, out: Path):
    """Family register extract — EN/FR translation form (TLS requires translation)."""
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, H - 25 * mm, "EXTRACT OF FAMILY REGISTER")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W / 2, H - 33 * mm, "Ekhraj Kaid Aily — CERTIFIED TRANSLATION (EN/FR) — SPECIMEN")
    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, H - 40 * mm, "Original Arabic civil extract translated for TLScontact Beirut filing")
    c.setFont("Helvetica", 10)
    y = H - 58 * mm
    c.drawString(25 * mm, y, f"Head of family: {d.get('head_of_family', '')}")
    y -= 10 * mm
    c.drawString(25 * mm, y, "Members:")
    y -= 8 * mm
    for m in d.get("members") or []:
        c.drawString(35 * mm, y, f"• {m}")
        y -= 7 * mm
    y -= 5 * mm
    c.drawString(25 * mm, y, f"Issue date of extract: {fmt(d.get('issue_date'))}")
    y -= 8 * mm
    c.drawString(25 * mm, y, f"Translated: {d.get('translated', True)} (English/French)")
    y -= 12 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(25 * mm, y, "Translator stamp: Specimen Sworn Translator — Beirut (FAKE)")
    _stamp(c, 150 * mm, 45 * mm, "TRANSL.")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_travel_plan(d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, H - 25 * mm, "TOURISM TRAVEL PLAN / ITINERARY")
    c.setFont("Helvetica", 10)
    c.drawString(18 * mm, H - 40 * mm, str(d.get("summary", "")))
    c.drawString(18 * mm, H - 55 * mm, "Day plan (SPECIMEN): museums, city walks, day trip — France.")
    _footer(c, W)
    c.showPage()
    c.save()


def pdf_generic(doc_type: str, d: dict, out: Path):
    c = canvas.Canvas(str(out), pagesize=A4)
    W, H = A4
    _wm_pdf(c, W, H)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, H - 25 * mm, doc_type.upper().replace("_", " "))
    y = H - 40 * mm
    c.setFont("Helvetica", 9)
    for k, v in d.items():
        if k == "file":
            continue
        if isinstance(v, str) and any("\u0600" <= ch <= "\u06ff" for ch in v):
            continue
        c.drawString(18 * mm, y, f"{k}: {fmt(v)[:90]}")
        y -= 7 * mm
        if y < 20 * mm:
            break
    _footer(c, W)
    c.showPage()
    c.save()


RENDERERS = {
    "application_form": pdf_application_form,
    "flight_booking": pdf_flight,
    "hotel_booking": pdf_hotel,
    "travel_insurance": pdf_insurance,
    "bank_statement": pdf_bank,
    "employment_letter": pdf_employment,
    "payslip": pdf_payslip,
    "cnss_certificate": pdf_cnss,
    "family_register": pdf_ekhraj,
    "travel_plan": pdf_travel_plan,
}


def pdf(doc_type: str, d: dict, out: Path):
    fn = RENDERERS.get(doc_type, pdf_generic)
    if doc_type not in RENDERERS:
        pdf_generic(doc_type, d, out)
    else:
        fn(d, out)


def degrade(src: Path):
    if src.suffix.lower() != ".png":
        return
    im = Image.open(src).convert("RGB").rotate(random.uniform(-3, 3), expand=True, fillcolor=(40, 40, 40))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(src.with_name(src.stem + "_phone.jpg"), quality=55)


def build(case_dir: Path, do_degrade: bool) -> list[str]:
    case = yaml.safe_load((case_dir / "case.yaml").read_text())
    out = case_dir / "docs"
    out.mkdir(exist_ok=True)
    made = []
    for dtype, spec in case["documents"].items():
        for d in spec if isinstance(spec, list) else [spec]:
            p = out / d["file"]
            if dtype == "passport":
                l1, l2 = render_passport(d, p)
                (out / "passport_mrz.txt").write_text(l1 + "\n" + l2 + "\n")
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
    dirs = (
        [CASES / c for c in a.cases]
        if a.cases
        else sorted(p for p in CASES.iterdir() if (p / "case.yaml").exists())
    )
    for d in dirs:
        made = build(d, a.degrade)
        print(f"{d.name}: {len(made)} files -> {d / 'docs'}")
    try:
        from mrz.checker.td3 import TD3CodeChecker

        for d in dirs:
            mrz_path = d / "docs" / "passport_mrz.txt"
            if not mrz_path.exists():
                continue
            txt = mrz_path.read_text().strip()
            ok = bool(TD3CodeChecker(txt))
            print(f"  MRZ {d.name}: {'valid' if ok else 'INVALID'}")
            if not ok:
                sys.exit(1)
    except ImportError:
        print("  (pip install mrz to self-verify MRZ check digits)")


if __name__ == "__main__":
    main()
