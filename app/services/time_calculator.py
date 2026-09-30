from datetime import datetime, timedelta


def calculate_worked_time(records):
    """Calcula tempo trabalhado a partir da sequência de registros.

    A primeira versão mantém uma lógica simples para o MVP:
    ENTRADA -> INTERVALO_SAIDA -> INTERVALO_RETORNO -> SAIDA
    """
    entry = None
    interval_start = None
    interval_end = None
    exit_time = None

    for record in sorted(records, key=lambda item: item.recorded_at):
        if record.type == "ENTRADA":
            entry = record.recorded_at
        elif record.type == "INTERVALO_SAIDA":
            interval_start = record.recorded_at
        elif record.type == "INTERVALO_RETORNO":
            interval_end = record.recorded_at
        elif record.type == "SAIDA":
            exit_time = record.recorded_at

    if not entry or not exit_time:
        return timedelta(0)

    total = exit_time - entry

    if interval_start and interval_end:
        total -= interval_end - interval_start

    return total


def format_duration(value):
    seconds = int(value.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"
