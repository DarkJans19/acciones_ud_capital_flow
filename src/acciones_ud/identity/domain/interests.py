from acciones_ud.shared.domain.errors import AppError, ErrorCode


def normalize_interests(values: list[str], known: list[str]) -> list[str]:
    canonical = {value.lower(): value for value in known}
    if not 1 <= len(values) <= 20 or any(
        not 1 <= len(v) <= 50 or v.lower() not in canonical for v in values
    ):
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: interests")
    return list(dict.fromkeys(canonical[v.lower()] for v in values))
