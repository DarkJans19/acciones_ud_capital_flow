"""Rebuild human-readable endpoint/journey tables from sanitized JSON evidence."""

import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent


def build():
    surface = json.loads((BASE / "attack-surface.json").read_text())
    live = json.loads((BASE / "live-http.json").read_text())
    followup = json.loads((BASE / "live-followup.json").read_text())
    operations = surface["operations"]
    observed = defaultdict(set)
    patterns = []
    for operation in operations:
        path = operation["path"]
        pattern = re.escape(path)
        for parameter in re.findall(r"\{[^}]+\}", path):
            pattern = pattern.replace(re.escape(parameter), "[^/]+")
        patterns.append((operation, re.compile("^" + pattern + "$")))
    patterns.sort(key=lambda pair: (pair[0]["path"].count("{"), -len(pair[0]["path"])))
    for row in [*live["requests"], *followup["requests"]]:
        # Later authenticated logout and edge probes are described separately.
        if row["case"] not in {"anonymous operation", "authenticated GET"}:
            continue
        for operation, pattern in patterns:
            if operation["method"] == row["method"] and pattern.fullmatch(row["path"]):
                observed[(operation["method"], operation["path"], row["actor"])].add(
                    str(row.get("status", row.get("transport_error", "unknown")))
                )
                break
    lines = [
        "# Matriz de endpoints HTTP",
        "",
        f"**{surface['http_operations']} operaciones / {surface['paths']} rutas** de OpenAPI.",
        "Cada operación es un par método+ruta, no un caso funcional completo.",
        "",
        "- Sin cookie / cookie inválida: ASGI aislado, solo rutas protegidas; 401 esperado.",
        "- Anónimo real: HTTPS y configuración real; cuerpos vacíos y UUID ficticios.",
        "- Columnas de cuentas: barrido GET autenticado; no se ejecutan mutaciones",
        "  financieras en la base compartida. `—` significa no ejecutado en ese barrido.",
        "- 403 por rol/premium y 404 por UUID inexistente pueden ser resultados correctos.",
        "- Cinco 422 de candles provienen de parámetros genéricos inválidos; la repetición",
        "  con fechas ISO válidas devolvió 200 (`live-followup.json`).",
        "- El perfil público del broker es público por contrato, no un bypass.",
        "- Esta tabla no demuestra cobertura de todas las ramas ni todos los cuerpos.",
        "",
        "| Método | Ruta | Acceso | Sin cookie | JWT inválido | Anónimo real | "
        "admin | admin2 | broker | investor | broker2 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for operation in operations:
        key = operation["method"], operation["path"]
        cells = [
            key[0], f"`{key[1]}`", "público" if operation["public"] else "sesión",
            str(operation.get("missing_cookie", "—")),
            str(operation.get("invalid_cookie", "—")),
        ]
        for actor in ("anonymous", "admin", "admin2", "broker", "investor", "broker2"):
            cells.append("/".join(sorted(observed[(*key, actor)])) or "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## WebSocket (fuera de OpenAPI HTTP)",
        "",
        "`/ws/v1/market-feed`: suite existente de suscripciones y cierre con streaming",
        "deshabilitado; pruebas adversariales de frames y revocación con autenticación",
        "controlada. No se presenta como un flujo WebSocket live contra Alpaca.",
    ]
    (BASE / "ENDPOINTS.md").write_text("\n".join(lines) + "\n")

    journey = json.loads((BASE / "cross-module-journey.json").read_text())
    lines = [
        "# Recorrido integrado de los siete módulos",
        "",
        "**ASGI + PostgreSQL real; JWT/cookies/MFA/RBAC reales; Alpaca y Stripe simulados.**",
        "Los usuarios y recursos son sintéticos. No hay overrides de `get_current_user`.",
        "El administrador y catálogo inicial se preparan en SQL; el resto se opera por HTTP.",
        "Las rutas de esta tabla llevan el prefijo `/api/v1`.",
        "",
        f"Solicitudes: **{len(journey['requests'])}**. "
        f"Resultados inesperados: **{sum(not r['passed'] for r in journey['requests'])}**.",
        "",
        "| # | Actor | Método | Ruta | Esperado | Real | Código de error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(journey["requests"], start=1):
        lines.append(
            f"| {index} | {row['actor']} | {row['method']} | `{row['path']}` | "
            f"{row['expected']} | {row['actual']} | {row['code'] or '—'} |"
        )
    (BASE / "RECORRIDO.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    build()
