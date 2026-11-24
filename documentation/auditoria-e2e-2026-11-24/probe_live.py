"""Bounded, read-oriented live audit. Secrets come ONLY from an external JSON file.

Run from repository root using uv run python .../probe_live.py --help.
No registration, trading, transfers, permission changes or recovery consumption.
Successful response bodies and cookie/token values are never saved.
"""

import argparse
import asyncio
import json
import re
import ssl
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pyotp


def schema_value(schema, document, name):
    if "$ref" in schema:
        schema = document["components"]["schemas"][schema["$ref"].split("/")[-1]]
    if "anyOf" in schema:
        schema = next(s for s in schema["anyOf"] if s.get("type") != "null")
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if schema.get("format") == "date":
        return "2026-11-01" if name in {"from", "start"} else "2026-11-24"
    if schema.get("format") == "date-time":
        return "2026-11-01T00:00:00Z" if name in {"from", "start"} else "2026-11-24T23:59:59Z"
    if schema.get("format") == "uuid":
        return "00000000-0000-0000-0000-000000000001"
    if schema.get("type") == "integer":
        return max(1, schema.get("minimum", 1))
    return {
        "symbol": "AAPL", "side": "buy", "qty": "1", "price": "100",
        "timeframe": "1Day", "period": "1M", "q": "AAPL",
        "start": "2026-11-01", "end": "2026-11-24",
    }.get(name, "NASDAQ")


async def run(args):
    parsed = urlsplit(args.base)
    if parsed.scheme != "https" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("This runner is restricted to local HTTPS.")
    context = ssl.create_default_context(cafile=args.ca)
    accounts = json.loads(Path(args.accounts_file).read_text()) if args.accounts_file else {}
    started = datetime.now(UTC).isoformat()
    rows, checks = [], []
    clients = {}
    semaphore = asyncio.Semaphore(3)

    async def request(actor, method, path, label, **kwargs):
        client = clients[actor]
        begin = time.monotonic()
        async with semaphore:
            try:
                response = await client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                rows.append({
                    "actor": actor, "method": method, "path": path, "case": label,
                    "transport_error": type(exc).__name__,
                })
                return None
        try:
            body = response.json()
        except ValueError:
            body = None
        rows.append({
            "actor": actor, "method": method, "path": path, "case": label,
            "params": kwargs.get("params"),
            "status": response.status_code,
            "code": body.get("code")
            if isinstance(body, dict) and response.status_code >= 400 else None,
            "message": body.get("message") if isinstance(body, dict) else None,
            "response_fields": sorted(body) if isinstance(body, dict) else None,
            "item_count": len(body) if isinstance(body, list) else (
                len(body["items"]) if isinstance(body, dict)
                and isinstance(body.get("items"), list) else None
            ),
            "request_id": response.headers.get("x-request-id"),
            "elapsed_including_queue_ms": round((time.monotonic() - begin) * 1000),
        })
        return response

    def save(document):
        payload = {
            "started_utc": started, "finished_utc": datetime.now(UTC).isoformat(),
            "base": args.base,
            "mode": "real HTTP; shared data read-oriented; no mocks",
            "operations_in_openapi": sum(len(v) for v in document.get("paths", {}).values()),
            "http_requests": len(rows),
            "statuses": dict(Counter(str(r.get("status", "transport")) for r in rows)),
            "checks": checks, "requests": rows,
        }
        Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    document = {}
    try:
        for actor in ["anonymous", *accounts]:
            clients[actor] = httpx.AsyncClient(
                base_url=args.base, verify=context, timeout=30,
                headers={"User-Agent": "AccionesUD-authorized-security-audit/2026-11-24"},
                follow_redirects=False,
            )
        await request("anonymous", "GET", "/health", "health")
        response = await request("anonymous", "GET", "/openapi.json", "inventory")
        if response is None or response.status_code != 200:
            return
        document = response.json()
        identifiers = {"id": "00000000-0000-0000-0000-000000000001"}

        def concrete(path):
            return re.sub(
                r"\{([^}]+)\}",
                lambda m: identifiers.get(m[1], {
                    "symbol": "AAPL", "code": "NASDAQ", "market_code": "NASDAQ",
                    "scope": "default", "role": "investor",
                    "permission_code": "account:manage",
                }.get(m[1], identifiers["id"])),
                path,
            )

        # Every operation: no valid session, no valid mutation body.
        await asyncio.gather(*(
            request("anonymous", method.upper(), concrete(path), "anonymous operation", json={})
            for path, methods in document["paths"].items()
            for method in methods
        ))
        for actor, credentials in accounts.items():
            response = await request(
                actor, "POST", "/api/v1/auth/login", "password login",
                json={"email": credentials["email"], "password": credentials["password"]},
            )
            if response is None or response.status_code != 200:
                checks.append({"case": actor + " login", "passed": False})
                continue
            challenge = response.json()
            response = await request(
                actor, "POST", "/api/v1/auth/mfa/verify", "TOTP login",
                json={"mfa_token": challenge["mfa_token"],
                      "code": pyotp.TOTP(credentials["totp_secret"]).now()},
            )
            authenticated = response is not None and response.status_code == 200
            checks.append({"case": actor + " MFA", "passed": authenticated})
            if authenticated:
                identifiers[actor + "_id"] = response.json()["user"]["user_id"]
                cookie_meta = [
                    {"name": c.name, "secure": c.secure, "path": c.path,
                     "httponly": c.has_nonstandard_attr("HttpOnly")}
                    for c in clients[actor].cookies.jar
                ]
                checks.append({"case": actor + " cookie attributes", "cookies": cookie_meta})
        identifiers["user_id"] = identifiers.get("investor_id", identifiers["id"])
        identifiers["client_id"] = identifiers["user_id"]
        identifiers["investor_id"] = identifiers["user_id"]
        identifiers["broker_id"] = identifiers.get("broker_id", identifiers["id"])

        async def get_operation(actor, path, operation):
            params = {
                p["name"]: schema_value(p["schema"], document, p["name"])
                for p in operation.get("parameters", [])
                if p["in"] == "query" and p.get("required")
            }
            await request(actor, "GET", concrete(path), "authenticated GET", params=params)

        for actor in accounts:
            if not clients[actor].cookies.get("access_token"):
                continue
            await asyncio.gather(*(
                get_operation(actor, path, methods["get"])
                for path, methods in document["paths"].items() if "get" in methods
            ))

        if "investor" in clients and clients["investor"].cookies.get("access_token"):
            for qty in ["1e100", "1e999999", "NaN", "-1", "0"]:
                await request(
                    "investor", "GET", "/api/v1/commissions/quote", "numeric edge",
                    params={"symbol": "AAPL", "side": "buy", "qty": qty, "price": "1"},
                )
            for qty in ["0", "-1", "NaN", "0.0000000001", "1"]:
                await request(
                    "investor", "POST", "/api/v1/orders/preview", "nonmutating order preview",
                    json={"symbol": "AAPL", "side": "buy", "qty": qty},
                )

        for body in [
            {"email": "", "password": "AuditWrong123"},
            {"email": "not-an-email", "password": "AuditWrong123"},
            {"email": "a" * 255 + "@example.com", "password": "AuditWrong123"},
            {"email": "audit-no-such-user@example.com", "password": ""},
        ]:
            await request(
                "anonymous", "POST", "/api/v1/auth/login", "invalid login shape", json=body
            )
        for actor in accounts:
            await request(actor, "POST", "/api/v1/auth/logout", "close audit session")
            response = await request(actor, "GET", "/api/v1/users/me", "logout invalidates HTTP")
            checks.append({
                "case": actor + " logout invalidates HTTP",
                "passed": response is not None and response.status_code == 401,
            })
    finally:
        save(document)
        for client in clients.values():
            await client.aclose()
    print(json.dumps({
        "output": args.output, "requests": len(rows),
        "server_errors": sum(r.get("status", 0) >= 500 for r in rows),
        "failed_checks": sum(c.get("passed") is False for c in checks),
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://127.0.0.1:8459")
    parser.add_argument("--ca", required=True, help="Local test certificate, verified as a CA")
    parser.add_argument("--accounts-file", help="External JSON; never commit it")
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
