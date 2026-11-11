import pyotp


class TotpGenerator:
    def __init__(self, secret: str) -> None:
        self.totp = pyotp.TOTP(secret, digits=6, interval=30)

    def generate(self, step: int) -> str:
        return str(self.totp.generate_otp(step))


def generate_secret() -> str:
    return str(pyotp.random_base32())


def enrollment_uri(secret: str, email: str) -> str:
    return str(pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Acciones UD"))


class TotpProvider:
    def new_secret(self) -> str:
        return generate_secret()

    def uri(self, secret: str, email: str) -> str:
        return enrollment_uri(secret, email)

    def generator(self, secret: str) -> TotpGenerator:
        return TotpGenerator(secret)
