from datetime import timedelta
from app.models.time_record import RECORD_TYPES
from app.services.clock import local_time, utc_now
from app.services.validation import DomainError


def duration_seconds(start, end):
    return max(0, int((end - start).total_seconds()))


def clock_minutes(value):
    return value.hour * 60 + value.minute


def expected_seconds(schedule, day, holidays):
    if schedule is None:
        return None
    if day.weekday() == 6 or day in holidays:
        return 0
    if day.weekday() == 5:
        return (clock_minutes(schedule.saturday_end) - clock_minutes(schedule.saturday_start)) * 60
    return (clock_minutes(schedule.end_time) - clock_minutes(schedule.start_time) - schedule.interval_minutes) * 60


def sequence_for(schedule, day, holidays, records=()):
    if any(r.type in ("INTERVALO_SAIDA", "INTERVALO_RETORNO") for r in records):
        return RECORD_TYPES
    expected = expected_seconds(schedule, day, holidays)
    if day.weekday() < 5 and expected and schedule.interval_minutes > 0:
        return RECORD_TYPES
    return ("ENTRADA", "SAIDA")


def validate_records(records, sequence, day):
    ranks = {value: index for index, value in enumerate(sequence)}
    ordered = sorted(records, key=lambda r: ranks.get(r.type, 99))
    if len({r.type for r in ordered}) != len(ordered) or any(r.type not in ranks for r in ordered):
        raise DomainError("Há marcação duplicada ou incompatível com a jornada.")
    previous = None
    for record in ordered:
        if local_time(record.effective_at).date() != day:
            raise DomainError("O horário deve pertencer à mesma data da marcação.")
        if previous is not None and record.effective_at <= previous:
            raise DomainError("Os horários devem respeitar a sequência de entrada, intervalo, retorno e saída.")
        previous = record.effective_at
    return ordered


def calculate_worked_time(records, sequence=RECORD_TYPES, as_of=None):
    by_type = {record.type: record.effective_at for record in records}
    pairs = (
        [("ENTRADA", "SAIDA")]
        if len(sequence) == 2
        else [("ENTRADA", "INTERVALO_SAIDA"), ("INTERVALO_RETORNO", "SAIDA")]
    )
    total = 0
    for start_type, end_type in pairs:
        start, end = by_type.get(start_type), by_type.get(end_type)
        if start and end:
            total += duration_seconds(start, end)
        elif start and as_of and "SAIDA" not in by_type:
            # Only an open contiguous work segment can produce a live estimate.
            if start_type == "ENTRADA" or "INTERVALO_SAIDA" in by_type:
                total += duration_seconds(start, as_of)
    return timedelta(seconds=total)


def format_duration(value, signed=False):
    if value is None:
        return "—"
    seconds = int(value.total_seconds()) if isinstance(value, timedelta) else int(value)
    prefix = "−" if seconds < 0 else ("+" if signed and seconds > 0 else "")
    hours, remainder = divmod(abs(seconds), 3600)
    return f"{prefix}{hours:02d}:{remainder // 60:02d}"


def daily_summary(day, schedule, records, holidays, current_day, live=False):
    sequence = sequence_for(schedule, day, holidays, records)
    invalid = False
    try:
        ordered = validate_records(records, sequence, day)
    except DomainError:
        ordered, invalid = list(records), True
    present = {record.type for record in records}
    contiguous = [r.type for r in ordered] == list(sequence[: len(ordered)])
    complete = not invalid and present == set(sequence)
    expected = expected_seconds(schedule, day, holidays)
    worked = int(
        calculate_worked_time(
            records, sequence, utc_now() if live and day == current_day and contiguous and not invalid else None
        ).total_seconds()
    )
    difference = None
    if invalid:
        status = "Inconsistente"
    elif complete:
        status = "Concluído"
        difference = worked - expected if expected is not None else None
    elif records:
        status = "Em andamento" if day == current_day and contiguous else "Incompleto"
    elif expected is None:
        status = "Sem jornada"
    elif expected == 0:
        status, difference = "Folga", 0
    elif day < current_day:
        status, difference = "Sem registro", -expected
    else:
        status = "Não iniciado" if day == current_day else "Previsto"
    next_type = (
        sequence[len(ordered)] if schedule and contiguous and not invalid and len(ordered) < len(sequence) else None
    )
    start_time = (
        schedule.saturday_start if schedule and day.weekday() == 5 else (schedule.start_time if schedule else None)
    )
    late = (
        max(0, (clock_minutes(local_time(ordered[0].effective_at).time()) - clock_minutes(start_time)))
        if ordered and ordered[0].type == "ENTRADA" and expected and start_time
        else 0
    )
    return {
        "day": day,
        "schedule": schedule,
        "records": ordered,
        "by_type": {r.type: r for r in records},
        "worked": worked,
        "expected": expected,
        "difference": difference,
        "status": status,
        "next_type": next_type,
        "sequence": sequence,
        "complete": complete,
        "late_minutes": late,
    }
