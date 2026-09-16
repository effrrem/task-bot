from __future__ import annotations

import re
from datetime import datetime, timedelta


DATE_WORDS = {"сегодня": 0, "завтра": 1, "послезавтра": 2}


def _is_deadline_token(tok: str) -> bool:
    t = tok.lower()
    if re.fullmatch(r"\d{1,2}[.:]\d{2}([./]\d{2,4})?", t):
        return True
    if re.fullmatch(r"\d{1,2}[./]\d{1,2}([./]\d{2,4})?", t):
        return True
    if t in ("до", "в", "к", "к", "сегодня", "завтра", "послезавтра"):
        return True
    if re.fullmatch(r"минут\w*|час\w*|день|дня|дней|мин\.?", t):
        return True
    return False


def _parse_date_part(a: int, b: int, c: str | None, now: datetime) -> datetime | None:
    """Try to interpret token as a date DD.MM(.YYYY)."""
    if c:
        y = int(c)
        if y < 100:
            y += 2000
        try:
            return datetime(y, b, a, 0, 0)
        except ValueError:
            return None
    if 1 <= b <= 12 and 1 <= a <= 31:
        try:
            return datetime(now.year, b, a, 0, 0)
        except ValueError:
            return None
    return None


def _parse_time_part(a: int, b: int) -> tuple[int, int] | None:
    if 0 <= a <= 23 and 0 <= b <= 59:
        return (a, b)
    return None


def parse_deadline(text: str) -> datetime | None:
    now = datetime.now()
    low = text.lower()

    m = re.search(
        r"через\s+(\d+)\s*(минут\w*|час\w*|мин\.?|день|дня|дней)", low
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("мин") or unit.startswith("час"):
            if unit.startswith("час"):
                return now + timedelta(hours=n)
            return now + timedelta(minutes=n)
        if unit.startswith("день") or unit.startswith("дня") or unit.startswith("дней"):
            return now + timedelta(days=n)

    delta_days = None
    for word, offset in DATE_WORDS.items():
        if word in low:
            delta_days = offset

    tokens = re.findall(r"\b(\d{1,2})[.:](\d{2})(?:[./](\d{2,4}))?\b", low)

    date = None
    explicit_date = False
    time_h, time_m = None, None

    for a_s, b_s, c_s in tokens:
        a, b = int(a_s), int(b_s)

        date_candidate = _parse_date_part(a, b, c_s, now)
        time_candidate = _parse_time_part(a, b)

        if date_candidate is not None and time_candidate is None:
            date = date_candidate
            explicit_date = True
        elif time_candidate is not None and date_candidate is None:
            time_h, time_m = time_candidate
        elif date_candidate is not None and time_candidate is not None:
            if c_s:
                date = date_candidate
                explicit_date = True
            else:
                if time_h is None:
                    date = date_candidate
                    explicit_date = True
                else:
                    time_h, time_m = time_candidate
        elif time_candidate is not None:
            time_h, time_m = time_candidate

    if date is None and time_h is None and delta_days is None:
        return None

    if date is None:
        if delta_days is not None:
            date = (now + timedelta(days=delta_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = date.replace(
        hour=time_h if time_h is not None else 9,
        minute=time_m if time_m is not None else 0,
        second=0,
        microsecond=0,
    )

    if time_h is not None and not explicit_date and delta_days is None and result <= now:
        result += timedelta(days=1)

    return result


def split_task_and_deadline(text: str) -> tuple[str, datetime | None]:
    deadline = parse_deadline(text)
    if deadline is None:
        return text.strip() or "Задача", None

    cleaned = re.sub(
        r"через\s+\d+\s*(минут\w*|час\w*|мин\.?|день|дня|дней|минуту)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"[,\s]+", cleaned)
    keep = [p for p in parts if not _is_deadline_token(p.lower())]
    result = " ".join(keep).strip(" ,-.:;")

    return (result or "Задача"), deadline


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")