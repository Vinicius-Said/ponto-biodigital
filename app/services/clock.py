from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from flask import current_app


def utc_now():
    """All database datetimes are naive UTC, including on Windows."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def local_time(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(current_app.config["APP_TIMEZONE"]))


def today():
    return local_time(utc_now()).date()


def to_utc(local_value):
    return (
        local_value.replace(tzinfo=ZoneInfo(current_app.config["APP_TIMEZONE"]))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def day_bounds(day):
    return to_utc(datetime.combine(day, time.min)), to_utc(datetime.combine(day + timedelta(days=1), time.min))


def datetime_label(value):
    return local_time(value).strftime("%d/%m/%Y %H:%M:%S") if value else "—"
