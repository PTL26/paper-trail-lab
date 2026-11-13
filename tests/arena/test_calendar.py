"""NYSE trading days for the test window (holidays and half days 2026-2027)."""

from datetime import date, datetime, timezone

from arena.calendar import is_trading_day, next_session, session_close_utc, session_open_utc


def test_weekends_and_holidays():
    assert is_trading_day(date(2026, 11, 30))
    assert not is_trading_day(date(2026, 11, 28))                 # Saturday
    assert not is_trading_day(date(2026, 11, 26))                 # Thanksgiving
    assert not is_trading_day(date(2026, 12, 25))                 # Christmas
    assert not is_trading_day(date(2027, 1, 1))
    assert not is_trading_day(date(2027, 1, 18))                  # MLK
    assert not is_trading_day(date(2027, 2, 15))                  # Presidents' Day
    assert not is_trading_day(date(2027, 3, 26))                  # Good Friday
    assert is_trading_day(date(2026, 11, 11))                     # Veterans Day: open


def test_next_session_skips_holidays():
    assert next_session(date(2026, 11, 25)) == date(2026, 11, 27)
    assert next_session(date(2026, 12, 24)) == date(2026, 12, 28)
    assert next_session(date(2026, 12, 31)) == date(2027, 1, 4)


def test_half_day_closes_at_13_new_york():
    assert session_close_utc(date(2026, 11, 27)) == datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)
    assert session_close_utc(date(2026, 11, 30)) == datetime(2026, 11, 30, 21, 0, tzinfo=timezone.utc)
    assert session_open_utc(date(2026, 11, 30)) == datetime(2026, 11, 30, 14, 30, tzinfo=timezone.utc)


def test_out_of_range_years_are_refused():
    import pytest
    with pytest.raises(ValueError):
        is_trading_day(date(2028, 3, 1))


def test_rest_of_2027_from_the_nyse_page():
    for d in (date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24)):
        assert not is_trading_day(d)
    assert session_close_utc(date(2027, 11, 26)) == datetime(2027, 11, 26, 18, 0, tzinfo=timezone.utc)


def test_sixty_sessions_from_the_first_scored_day():
    from arena.calendar import sessions_between
    s = sessions_between(date(2026, 11, 30), date(2027, 3, 31))
    assert len(s[:60]) == 60 and s[0] == date(2026, 11, 30)
