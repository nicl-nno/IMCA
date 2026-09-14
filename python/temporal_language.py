"""Conservative English calendar expressions without a model.

Month/year precision is preserved as intervals. Session timestamps have no
timezone in LoCoMo; calendar arithmetic does not invent one.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTH_PATTERN = "(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + ")"
NUMBERS = {
    word: i
    for i, word in enumerate(
        (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        )
    )
}
NUMBER_PATTERN = r"(?:\d+|" + "|".join(NUMBERS) + ")"


@dataclass(frozen=True)
class TimeSpan:
    start: str
    end: str  # inclusive, unlike the assertion store's half-open validity
    precision: str
    expression: str
    offset: int
    rule: str

    def to_dict(self):
        return asdict(self)


def session_datetime(text: str) -> datetime:
    return datetime.strptime(text, "%I:%M %p on %d %B, %Y")


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(reference: date, amount: int) -> tuple[date, date]:
    position = reference.year * 12 + reference.month - 1 + amount
    year, month = divmod(position, 12)
    return month_bounds(year, month + 1)


def extract_times(text: str, reference: date | None) -> list[TimeSpan]:
    spans: list[TimeSpan] = []
    occupied: list[tuple[int, int]] = []

    def add(match, first, last, precision, rule):
        if any(match.start() < end and match.end() > start for start, end in occupied):
            return
        spans.append(
            TimeSpan(
                first.isoformat(), last.isoformat(), precision, match.group(), match.start(), rule
            )
        )
        occupied.append(match.span())

    # Only explicit years are inferred without a source timestamp.
    patterns = [
        (rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})\s*,?\s*(\d{{4}})\b", (1, 2, 3)),
        (rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(\d{{4}})\b", (2, 1, 3)),
    ]
    for pattern, (day_group, month_group, year_group) in patterns:
        for match in re.finditer(pattern, text, re.I):
            try:
                value = date(
                    int(match[year_group]),
                    MONTHS[match[month_group].lower()],
                    int(match[day_group]),
                )
                add(match, value, value, "day", "explicit_date")
            except ValueError:
                continue
    for match in re.finditer(rf"\b({MONTH_PATTERN})\s*,?\s*(\d{{4}})\b", text, re.I):
        first, last = month_bounds(int(match[2]), MONTHS[match[1].lower()])
        add(match, first, last, "month", "explicit_month")
    for match in re.finditer(r"\b(?:19|20)\d{2}\b", text):
        year = int(match.group())
        add(match, date(year, 1, 1), date(year, 12, 31), "year", "explicit_year")
    if reference is None:
        return sorted(spans, key=lambda item: item.offset)
    for match in re.finditer(r"\b(?:the )?day (before yesterday|after tomorrow)\b", text, re.I):
        offset = -2 if match[1].lower() == "before yesterday" else 2
        value = reference + timedelta(days=offset)
        add(match, value, value, "day", "compound_relative_day")
    for match in re.finditer(r"\b(today|yesterday|tomorrow)\b", text, re.I):
        value = reference + timedelta(
            days={"today": 0, "yesterday": -1, "tomorrow": 1}[match[1].lower()]
        )
        add(match, value, value, "day", "relative_day")
    for match in re.finditer(
        rf"\b({NUMBER_PATTERN})\s+(days?|weeks?|months?|years?)\s+ago\b", text, re.I
    ):
        number_text = match[1].lower()
        number = int(number_text) if number_text.isdigit() else NUMBERS[number_text]
        if number > 200:
            continue
        unit = match[2].lower().rstrip("s")
        if unit == "day":
            first = last = reference - timedelta(days=number)
            precision = "day"
        elif unit == "week":
            # Colloquial weeks-ago is not assumed to name an exact weekday.
            first = reference - timedelta(days=7 * number + 3)
            last = reference - timedelta(days=max(0, 7 * number - 3))
            precision = "approximate_week"
        elif unit == "month":
            first, last = shift_month(reference, -number)
            precision = "month"
        else:
            year = reference.year - number
            first, last, precision = date(year, 1, 1), date(year, 12, 31), "year"
        add(match, first, last, precision, "relative_ago")
    for match in re.finditer(r"\b(last|next|this)\s+(week|month|year)\b", text, re.I):
        direction = {"last": -1, "next": 1, "this": 0}[match[1].lower()]
        unit = match[2].lower()
        if unit == "week":
            first = reference - timedelta(days=reference.weekday()) + timedelta(weeks=direction)
            last, precision = first + timedelta(days=6), "calendar_week_assumption"
        elif unit == "month":
            first, last = shift_month(reference, direction)
            precision = "month"
        else:
            year = reference.year + direction
            first, last, precision = date(year, 1, 1), date(year, 12, 31), "year"
        add(match, first, last, precision, "relative_period")
    return sorted(spans, key=lambda item: item.offset)


def time_tokens(span: TimeSpan) -> str:
    first, last = date.fromisoformat(span.start), date.fromisoformat(span.end)
    if span.precision == "day":
        return f"{first.day} {calendar.month_name[first.month]} {first.year}"
    if span.precision == "month":
        return f"{calendar.month_name[first.month]} {first.year}"
    if span.precision == "year":
        return str(first.year)
    return f"{first.isoformat()} {last.isoformat()}"
