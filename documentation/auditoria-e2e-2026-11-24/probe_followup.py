"""Targeted follow-up; localhost HTTPS only, no financial mutations or recovery codes."""

import argparse
import asyncio
import json
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyotp

from acciones_ud.config.settings import Settings


async def run(args):
    if args.base != "https://127.0.0.1:8459":
        raise SystemExit("Only the dedicated loopback audit server is authorized.")
    accounts = json.loads(Path(args.accounts_file).read_text())
    context = ssl.create_default_context(cafile=args.ca)
    rows = []
    async with httpx.AsyncClient(base_url=args.base, verify=context, timeout=30) as client:
        async def call(method, path, case, **kwargs):
            start = time.monotonic()
            response = await client.request(method, path, **kwargs)
            try:
                body = response.json()
            except ValueError:
                body = None
            rows.append({
                "method": method, "path": path, "case": case,
                "params": kwargs.get("params"), "status": response.status_code,
                "code": body.get("code")
                if isinstance(body, dict) and response.status_code >= 400 else None,
                "total": body.get("total") if isinstance(body, dict) else None,
                "elapsed_ms": round((time.monotonic() - start) * 1000),
                "request_id": response.headers.get("x-request-id"),
                "allow_methods": response.headers.get("access-control-allow-methods"),
                "cache_control": response.headers.get("cache-control"),
            })
            return response

        try:
            credentials = accounts["investor"]
            response = await call("POST", "/api/v1/auth/login", "follow-up login", json={
                "email": credentials["email"], "password": credentials["password"],
            })
            assert response.status_code == 200
            response = await call("POST", "/api/v1/auth/mfa/verify", "follow-up TOTP", json={
                "mfa_token": response.json()["mfa_token"],
                "code": pyotp.TOTP(credentials["totp_secret"]).now(),
            })
            assert response.status_code == 200
            await call("GET", "/api/v1/instruments/AAPL/candles", "valid history dates", params={
                "timeframe": "1Day", "start": "2026-11-20", "end": "2026-11-24",
            })
            for path in ("/api/v1/instruments/search", "/api/v1/brokers"):
                await call("GET", path, "SQL-like search literal", params={"q": "' OR 1=1 --"})
            await call("OPTIONS", "/api/v1/users/me", "real allowed-origin PATCH preflight",
                       headers={
                           "Origin": Settings().allowed_origins[0],
                           "Access-Control-Request-Method": "PATCH",
                           "Access-Control-Request-Headers": "content-type",
                       })
            await call("GET", "/api/v1/users/me", "sensitive response cache policy")
            # Close the connection after the deliberate 500; avoid a subsequent
            # request racing Uvicorn's error-triggered keep-alive shutdown.
            await call("GET", "/api/v1/commissions/quote", "extreme decimal fresh connection",
                       params={"symbol": "AAPL", "side": "buy", "qty": "1e999999", "price": "1"},
                       headers={"Connection": "close"})
            for _ in range(30):
                await call("POST", "/api/v1/auth/login", "bounded unknown-user throttling probe",
                           json={
                               "email": "audit-no-such-user@example.com",
                               "password": "AuditWrongPassword123",
                           })
        finally:
            await call("POST", "/api/v1/auth/logout", "close follow-up audit session")
            Path(args.output).write_text(json.dumps({
                "finished_utc": datetime.now(UTC).isoformat(),
                "mode": "real HTTP + shared DB + real providers; bounded nonfinancial probes",
                "requests": rows,
            }, indent=2) + "\n")
    print(json.dumps({"requests": len(rows), "output": args.output}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://127.0.0.1:8459")
    parser.add_argument("--ca", required=True)
    parser.add_argument("--accounts-file", required=True)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
