from datetime import timedelta
from uuid import UUID

from acciones_ud.identity.domain.auth_ports import (
    AuthWorkFactory,
    Record,
    TokenGenerator,
    TotpProvider,
)
from acciones_ud.identity.domain.ports import AccessTokenCodec, PasswordHasher, SecretCipher
from acciones_ud.identity.domain.recovery_codes import generate_set, hash_set
from acciones_ud.identity.domain.totp_window import match
from acciones_ud.identity.domain.validation import normalize_email
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class AuthService:
    def __init__(
        self,
        uow: AuthWorkFactory,
        hasher: PasswordHasher,
        cipher: SecretCipher,
        codec: AccessTokenCodec,
        tokens: TokenGenerator,
        totp: TotpProvider,
        clock: Clock,
        refresh_ttl: int,
    ) -> None:
        self.uow, self.hasher, self.cipher, self.codec = uow, hasher, cipher, codec
        self.tokens, self.totp, self.clock, self.refresh_ttl = tokens, totp, clock, refresh_ttl

    async def login(self, email: str, password: str, ip: str, agent: str) -> Record:
        now = self.clock.now()
        result: Record | None = None
        async with self.uow() as work:
            repo = work.auth
            user = await repo.find_user(normalize_email(email))
            if user is None:
                self.hasher.verify_dummy(password)
                await repo.audit(None, "login", "unknown_email", None, ip, agent)
            elif not self.hasher.verify(password, user["password_hash"]):
                await repo.audit(user["id"], "login", "wrong_password", None, ip, agent)
            else:
                # Serialize pending enrollment initialization across simultaneous logins.
                user = await repo.lock_user(user["id"])
                enrollment = None
                if not user["totp_confirmed_at"]:
                    if not user["totp_secret_enc"]:
                        secret = self.totp.new_secret()
                        user["totp_secret_enc"] = self.cipher.encrypt(secret)
                        await repo.update_user(
                            user["id"], {"totp_secret_enc": user["totp_secret_enc"]}
                        )
                    secret = self.cipher.decrypt(user["totp_secret_enc"])
                    enrollment = {
                        "secret": secret,
                        "otpauth_uri": self.totp.uri(secret, user["email"]),
                    }
                token = self.tokens.new()
                expires = now + timedelta(seconds=300)
                await repo.create_challenge(user["id"], self.tokens.digest(token), expires)
                await repo.audit(user["id"], "login", "success", None, ip, agent)
                result = {
                    "mfa_token": token,
                    "mfa_expires_at": expires,
                    "totp_enrollment": enrollment,
                }
        if result is None:
            raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "Invalid credentials.")
        return result

    async def verify(
        self, mfa_token: str, code: str | None, recovery_code: str | None, ip: str, agent: str
    ) -> Record:
        now = self.clock.now()
        method = "recovery_code" if recovery_code is not None else "totp"
        result: Record | None = None
        async with self.uow() as work:
            repo = work.auth
            challenge = await repo.lock_challenge(self.tokens.digest(mfa_token))
            if challenge is None or not challenge.usable(now):
                reason = "invalid_challenge"
                if challenge and now >= challenge.expires_at:
                    reason = "expired_challenge"
                elif challenge and challenge.failed_attempts >= 5:
                    reason = "attempt_limit_exceeded"
                await repo.audit(
                    challenge.user_id if challenge else None,
                    "mfa_verify",
                    reason,
                    method,
                    ip,
                    agent,
                )
            else:
                # User lock also prevents TOTP reuse across different challenges and serializes
                # recovery consumption with regeneration (challenge locks alone cannot do this).
                user = await repo.lock_user(challenge.user_id)
                accepted = False
                issued = None
                remaining = None
                reason = "invalid_recovery_code" if recovery_code else "invalid_totp"
                if recovery_code is not None and user["totp_confirmed_at"]:
                    for code_id, encoded in await repo.recovery_hashes(user["id"]):
                        if self.hasher.verify(recovery_code, encoded):
                            accepted = await repo.consume_code(code_id, now)
                            break
                    if accepted:
                        remaining = len(await repo.recovery_hashes(user["id"]))
                elif code is not None and user["totp_secret_enc"]:
                    generator = self.totp.generator(self.cipher.decrypt(user["totp_secret_enc"]))
                    step = match(generator, code, now, user["totp_last_step"])
                    accepted = step is not None
                    if accepted:
                        changes: Record = {"totp_last_step": step}
                        if not user["totp_confirmed_at"]:
                            changes["totp_confirmed_at"] = now
                            issued = generate_set()
                            await repo.replace_codes(user["id"], hash_set(issued, self.hasher), now)
                        await repo.update_user(user["id"], changes)
                    elif match(generator, code, now, None) is not None:
                        reason = "replayed_totp"
                if accepted:
                    challenge.succeed(now)
                    refresh = self.tokens.new()
                    sid = await repo.create_session(
                        user["id"],
                        self.tokens.digest(refresh),
                        now,
                        now + timedelta(seconds=self.refresh_ttl),
                        ip,
                        agent,
                    )
                    result = {
                        "user": {
                            "user_id": user["id"],
                            "email": user["email"],
                            "account_status": user["account_status"],
                        },
                        "recovery_codes": issued,
                        "recovery_codes_remaining": remaining,
                        "access": self.codec.encode(user["id"], sid),
                        "refresh": refresh,
                    }
                    reason = "success"
                else:
                    challenge.fail(now)
                await repo.save_challenge(challenge)
                await repo.audit(user["id"], "mfa_verify", reason, method, ip, agent)
        # Raise only after commit: failed attempts and the audit event must survive the 401.
        if result is None:
            raise AppError(401, ErrorCode.MFA_FAILED, "MFA verification failed.")
        return result

    async def regenerate(self, user_id: UUID) -> list[str]:
        async with self.uow() as work:
            user = await work.auth.lock_user(user_id)
            if not user["totp_confirmed_at"]:
                raise AppError(409, ErrorCode.MFA_NOT_ENROLLED, "MFA enrollment required.")
            codes = generate_set()
            await work.auth.replace_codes(user_id, hash_set(codes, self.hasher), self.clock.now())
        return codes
