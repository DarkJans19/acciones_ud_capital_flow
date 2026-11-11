import re
import secrets
import string
from collections.abc import Iterable

from acciones_ud.identity.domain.ports import PasswordHasher


def generate_set() -> list[str]:
    codes: set[str] = set()
    while len(codes) < 10:
        codes.add(
            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        )
    return sorted(codes)


def normalize(raw: str) -> str:
    return raw.strip().upper()


def is_well_formed(code: str) -> bool:
    return re.fullmatch(r"[A-Z0-9]{10}", code) is not None


def hash_set(codes: Iterable[str], hasher: PasswordHasher) -> list[str]:
    return [hasher.hash(code) for code in codes]
