"""Zonas horarias reales (versión 0.38). Lógica pura, sin Telegram ni base de datos.

Con una hora fija (por ejemplo, UTC−4) el reloj del Sim se correría una hora cuando cambia el
horario de verano. Por eso cada jugador puede elegir su lugar (Cuba, Miami…) y su Sim sigue la hora
real de allí, con el cambio de horario incluido. Quien eligió "otra hora" sigue con su hora fija.

En `extras` del jugador: "zona" = la clave del lugar, o "" si eligió una hora fija. Sin "zona", se
usa la zona por defecto del servidor (ZONA_POR_DEFECTO) si su hora es la de siempre (UTC−4).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

LUGARES = (
    ("cuba", "🇨🇺 Cuba", "America/Havana"),
    ("miami", "🇺🇸 Miami / Florida", "America/New_York"),
    ("mexico", "🇲🇽 México", "America/Mexico_City"),
    ("colombia", "🇨🇴 Colombia", "America/Bogota"),
    ("venezuela", "🇻🇪 Venezuela", "America/Caracas"),
    ("dominicana", "🇩🇴 Rep. Dominicana", "America/Santo_Domingo"),
    ("argentina", "🇦🇷 Argentina", "America/Argentina/Buenos_Aires"),
    ("espana", "🇪🇸 España", "Europe/Madrid"),
)
POR_CLAVE = {clave: (nombre, tz) for clave, nombre, tz in LUGARES}
OFFSET_DE_SIEMPRE = -240  # UTC−4: la hora con la que empieza cada jugador


@lru_cache(maxsize=512)
def zona_de(extras: str, utc_offset: int, por_defecto: str = "") -> str | None:
    """La clave del lugar cuya hora sigue el jugador, o None si usa una hora fija."""
    try:
        elegida = json.loads(extras or "{}").get("zona")
    except (ValueError, AttributeError):
        elegida = None
    if elegida is not None:
        return elegida if elegida in POR_CLAVE else None
    return por_defecto if por_defecto in POR_CLAVE and utc_offset == OFFSET_DE_SIEMPRE else None


def local(ts: float, extras: str, utc_offset: int, por_defecto: str = "") -> datetime:
    """La fecha y hora local del jugador (sin zona), con el horario de verano de su lugar."""
    zona = zona_de(extras, utc_offset, por_defecto)
    if zona:
        return datetime.fromtimestamp(ts, tz=ZoneInfo(POR_CLAVE[zona][1])).replace(tzinfo=None)
    return datetime.fromtimestamp(ts + utc_offset * 60, tz=timezone.utc).replace(tzinfo=None)


def offset(zona: str, ts: float) -> int:
    """Minutos respecto a UTC que tiene ahora ese lugar."""
    return int(datetime.fromtimestamp(ts, tz=ZoneInfo(POR_CLAVE[zona][1])).utcoffset().total_seconds() // 60)


def nombre(zona: str | None, utc_offset: int) -> str:
    if zona:
        return POR_CLAVE[zona][0]
    signo = "+" if utc_offset >= 0 else "−"
    horas, minutos = divmod(abs(utc_offset), 60)
    return f"UTC{signo}{horas}" + (f":{minutos:02d}" if minutos else "")
