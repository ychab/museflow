from datetime import timedelta


def format_duration(duration: timedelta) -> str:
    """A short human duration: `8.4s`, `4m09s`, `1h02m`."""
    seconds = duration.total_seconds()
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"
