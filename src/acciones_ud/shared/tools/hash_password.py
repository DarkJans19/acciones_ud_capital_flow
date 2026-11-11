"""Generate INITIAL_ADMIN_PASSWORD_HASH without exposing the supplied password."""

from getpass import getpass

from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.domain.validation import valid_password


def main() -> None:
    password = getpass("Password: ")
    if not valid_password(password):
        raise SystemExit("Password must have 8-128 characters, a letter and a digit.")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
