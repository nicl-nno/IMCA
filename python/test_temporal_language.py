from datetime import date

from temporal_language import extract_times, session_datetime


def test_relative_dates_preserve_calendar_precision_and_rollover():
    anchor = date(2024, 1, 6)
    spans = extract_times("yesterday; last month; two years ago; next month", anchor)
    assert [(s.start, s.end) for s in spans] == [
        ("2024-01-05", "2024-01-05"),
        ("2023-12-01", "2023-12-31"),
        ("2022-01-01", "2022-12-31"),
        ("2024-02-01", "2024-02-29"),
    ]
    assert session_datetime("1:32 pm on 6 January, 2024").hour == 13


def test_explicit_dates_do_not_duplicate_month_or_year_matches():
    spans = extract_times("19 January, 2023 and February 2024", None)
    assert len(spans) == 2
    assert spans[0].precision == "day"
    assert spans[1].end == "2024-02-29"
    assert extract_times("recently and someday", date(2024, 1, 1)) == []
    assert extract_times("yesterday", None) == []


def test_compound_relative_days_are_not_shortened_to_wrong_dates():
    spans = extract_times("the day before yesterday and the day after tomorrow", date(2024, 1, 1))
    assert [(s.start, s.precision) for s in spans] == [("2023-12-30", "day"), ("2024-01-03", "day")]
