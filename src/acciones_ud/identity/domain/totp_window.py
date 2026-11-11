import hmac
import re
from datetime import datetime

from acciones_ud.identity.domain.ports import TotpGenerator


def match(generator: TotpGenerator, code: str, t: datetime, last_step: int | None) -> int | None:
    if not re.fullmatch(r"[0-9]{6}", code):
        return None
    step = int(t.timestamp()) // 30
    for candidate in (step - 1, step, step + 1):
        if candidate < 0:
            continue
        if (last_step is None or candidate > last_step) and hmac.compare_digest(
            generator.generate(candidate), code
        ):
            return candidate
    return None
