"""Position recovery across common employer-letter phrasings."""
from __future__ import annotations

import pytest

from app.extract.employment_fields import recover_position_from_text


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "KARIM NASSAR has been employed with our company as Software Engineer "
            "since 01/02/2021. Monthly salary: 1,800.00 USD.",
            "Software Engineer",
        ),
        (
            "Position: Senior Accountant\nEmployee: Rana Haddad\nSince 2019",
            "Senior Accountant",
        ),
        (
            "Job title: Marketing Manager\nLeave from 01/06/2026 to 15/06/2026",
            "Marketing Manager",
        ),
        (
            "Fonction : Analyste financier\nSalaire mensuel : 2000 EUR",
            "Analyste financier",
        ),
        (
            "M. Karim Nassar est employé en qualité de Ingénieur logiciel depuis 2020.",
            "Ingénieur logiciel",
        ),
        (
            "Designation: HR Officer\nMonthly salary USD 1200",
            "HR Officer",
        ),
        (
            "Poste: Chef de projet\nCongé du 01/12/2026 au 10/12/2026",
            "Chef de projet",
        ),
        (
            "She works as a Nurse since 2018 with our hospital.",
            "Nurse",
        ),
    ],
)
def test_recover_position_many_formats(text: str, expected: str) -> None:
    assert recover_position_from_text(text) == expected


def test_recover_position_none_when_absent() -> None:
    assert (
        recover_position_from_text(
            "TO WHOM IT MAY CONCERN\nKarim works with our company since 2020. Salary 1800 USD."
        )
        is None
    )


def test_specimen_employment_letter_pdf_text() -> None:
    text = (
        "This is to certify that KARIM NASSAR has been employed with our company "
        "as Software Engineer\nsince 01/02/2021. Monthly salary: 1,800.00 USD."
    )
    assert recover_position_from_text(text) == "Software Engineer"
