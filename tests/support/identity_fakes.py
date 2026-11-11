from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

from acciones_ud.identity.domain.auth_ports import AuthWork, Record
from acciones_ud.identity.domain.mfa import Challenge


class FakeAuthRepository:
    def __init__(self, user: Record) -> None:
        self.user = user
        self.challenges: dict[bytes, Challenge] = {}
        self.codes: dict[UUID, Record] = {}
        self.sessions: dict[UUID, Record] = {}
        self.refreshes: dict[bytes, Record] = {}
        self.events: list[Record] = []

    async def find_user(self, email: str) -> Record | None:
        return self.user if email == self.user["email_normalized"] else None

    async def lock_user(self, user_id: UUID) -> Record:
        assert user_id == self.user["id"]
        return self.user

    async def update_user(self, user_id: UUID, changes: Record) -> None:
        self.user.update(changes)

    async def create_challenge(self, user_id: UUID, digest: bytes, expires: datetime) -> None:
        self.challenges[digest] = Challenge(uuid4(), user_id, expires)

    async def lock_challenge(self, digest: bytes) -> Challenge | None:
        return self.challenges.get(digest)

    async def save_challenge(self, challenge: Challenge) -> None:
        pass

    async def audit(
        self, user_id: UUID | None, kind: str, result: str, method: str | None, ip: str, agent: str
    ) -> None:
        self.events.append({"user_id": user_id, "kind": kind, "result": result, "method": method})

    async def recovery_hashes(self, user_id: UUID) -> list[tuple[UUID, str]]:
        return [
            (key, row["hash"])
            for key, row in self.codes.items()
            if row["used_at"] is None and row["invalidated_at"] is None
        ]

    async def consume_code(self, code_id: UUID, now: datetime) -> bool:
        row = self.codes[code_id]
        if row["used_at"] is not None or row["invalidated_at"] is not None:
            return False
        row["used_at"] = now
        return True

    async def replace_codes(self, user_id: UUID, hashes: list[str], now: datetime) -> None:
        for row in self.codes.values():
            row["invalidated_at"] = now
        self.codes.update(
            {
                uuid4(): {"hash": encoded, "used_at": None, "invalidated_at": None}
                for encoded in hashes
            }
        )

    async def create_session(
        self, user_id: UUID, digest: bytes, now: datetime, expires: datetime, ip: str, agent: str
    ) -> UUID:
        sid = uuid4()
        self.sessions[sid] = {
            "id": sid,
            "user_id": user_id,
            "last_used_at": now,
            "created_at": now,
            "revoked_at": None,
            "ip_address": ip,
            "user_agent": agent[:512],
        }
        self.refreshes[digest] = {"sid": sid, "expires": expires, "rotated": False}
        return sid

    async def rotate(
        self, digest: bytes, new_digest: bytes, now: datetime, expires: datetime
    ) -> tuple[UUID, UUID] | None:
        row = self.refreshes.get(digest)
        if row is None:
            return None
        session = self.sessions[row["sid"]]
        if row["rotated"] or now >= row["expires"] or session["revoked_at"]:
            session["revoked_at"] = now
            return None
        row["rotated"] = True
        session["last_used_at"] = now
        self.refreshes[new_digest] = {"sid": row["sid"], "expires": expires, "rotated": False}
        return session["user_id"], row["sid"]

    async def list_sessions(self, user_id: UUID, now: datetime) -> list[Record]:
        return sorted(
            [
                r
                for r in self.sessions.values()
                if r["user_id"] == user_id and r["revoked_at"] is None
            ],
            key=lambda r: r["last_used_at"],
            reverse=True,
        )

    async def revoke(self, user_id: UUID, session_id: UUID, now: datetime) -> bool:
        session = self.sessions.get(session_id)
        if session is None or session["user_id"] != user_id or session["revoked_at"] is not None:
            return False
        session["revoked_at"] = now
        return True

    async def revoke_others(self, user_id: UUID, session_id: UUID, now: datetime) -> int:
        count = 0
        for row in self.sessions.values():
            if row["user_id"] == user_id and row["id"] != session_id and row["revoked_at"] is None:
                row["revoked_at"] = now
                count += 1
        return count


class FakeAuthWorkFactory:
    def __init__(self, repository: FakeAuthRepository) -> None:
        self.repository = repository

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AuthWork]:
        snapshot = deepcopy(self.repository.__dict__)
        repo = self.repository

        class Work:
            auth = repo

        try:
            yield Work()
        except BaseException:
            self.repository.__dict__.update(snapshot)
            raise
