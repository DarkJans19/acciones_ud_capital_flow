from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2()
        self._dummy = self._hasher.hash("dummy-credential-not-used-for-login")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, encoded: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(password, self._dummy)
