EVENT_TYPES = (
    "market_open",
    "market_close",
    "proposals",
    "approval_requests",
    "price_changes",
    "execution_confirmations",
    "daily_summary",
)
CHANNELS = ("in_app", "email", "sms", "telegram")


def default_preferences() -> list[dict[str, object]]:
    return [
        {"event_type": event, "channel": channel, "enabled": channel == "in_app"}
        for event in EVENT_TYPES
        for channel in CHANNELS
    ]


def validate_patch(patch: list[dict[str, object]], has_phone: bool, has_telegram: bool) -> None:
    from acciones_ud.shared.domain.errors import AppError, ErrorCode

    seen: set[tuple[object, object]] = set()
    if not 1 <= len(patch) <= 28:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: preferences")
    for entry in patch:
        event, channel, enabled = (
            entry.get("event_type"),
            entry.get("channel"),
            entry.get("enabled"),
        )
        if (
            not isinstance(event, str)
            or not isinstance(channel, str)
            or event not in EVENT_TYPES
            or channel not in CHANNELS
            or type(enabled) is not bool
            or (channel == "in_app" and not enabled)
            or (event, channel) in seen
        ):
            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: preferences")
        seen.add((event, channel))
        if enabled and (
            (channel == "sms" and not has_phone) or (channel == "telegram" and not has_telegram)
        ):
            raise AppError(
                422,
                ErrorCode.CHANNEL_NOT_AVAILABLE,
                "Channel is unavailable.",
                {"channel": channel},
            )


def merge(
    stored: list[dict[str, object]], patch: list[dict[str, object]]
) -> list[dict[str, object]]:
    values = {(str(e["event_type"]), str(e["channel"])): dict(e) for e in stored}
    for entry in patch:
        values[(str(entry["event_type"]), str(entry["channel"]))] = dict(entry)
    return list(values.values())
