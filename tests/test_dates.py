from datetime import date

import pytest

from gtask.dates import from_api, parse_due, to_api
from gtask.errors import UsageError

TODAY = date(2026, 9, 29)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-10-05", date(2026, 10, 5)),
        ("today", TODAY),
        ("Tomorrow", date(2026, 9, 30)),
        ("+3d", date(2026, 10, 2)),
        ("+0d", TODAY),
        ("  today ", TODAY),
    ],
)
def test_parse_due(text, expected):
    assert parse_due(text, today=TODAY) == expected


@pytest.mark.parametrize("text", ["2026-13-45", "nextweek", "+3", "3d", "", "2026/10/05"])
def test_parse_due_rejects_garbage(text):
    with pytest.raises(UsageError) as exc:
        parse_due(text, today=TODAY)
    assert "YYYY-MM-DD" in exc.value.message


def test_parse_due_defaults_to_real_today():
    assert parse_due("today") == date.today()  # noqa: DTZ011 - parse_due('today') deliberately uses the local date


def test_to_api():
    assert to_api(date(2026, 10, 5)) == "2026-10-05T00:00:00.000Z"


def test_from_api():
    assert from_api("2026-10-05T00:00:00.000Z") == "2026-10-05"
    assert from_api(None) == ""
    assert from_api("") == ""
