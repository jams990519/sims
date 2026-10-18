"""La hora real de cada lugar, con el horario de verano (Cuba y Miami cambian el 1 de noviembre de 2026)."""

import random
from datetime import datetime, timezone

from simpareja import zonas as Z
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Juego
from test_juego import ADMIN, crear_personaje, Reloj

ANTES = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc).timestamp()  # 12:00 UTC, aún horario de verano
DESPUES = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc).timestamp()


def test_cuba_y_miami_siguen_el_horario_de_verano():
    for lugar in ("cuba", "miami"):
        extras = f'{{"zona": "{lugar}"}}'
        assert f"{Z.local(ANTES, extras, -240):%H:%M}" == "08:00"
        assert f"{Z.local(DESPUES, extras, -240):%H:%M}" == "07:00"  # se ajusta sola
        assert Z.offset(lugar, ANTES) == -240 and Z.offset(lugar, DESPUES) == -300
    assert f"{Z.local(DESPUES, '{\"zona\": \"\"}', -240):%H:%M}" == "08:00"  # hora fija: no cambia
    assert Z.zona_de("{}", -240, "cuba") == "cuba" and Z.zona_de("{}", -300, "cuba") is None
    assert Z.nombre(None, -240) == "UTC−4" and Z.nombre(None, 330) == "UTC+5:30"


def test_elegir_donde_vives():
    reloj = Reloj()
    reloj.t = ANTES
    juego = Juego(DB(":memory:"), Config(token="x", admins=frozenset({ADMIN}), eventos=False, zona_por_defecto="cuba"),
                  reloj=reloj, rng=random.Random(7))
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "🕒 Tu hora local: 08:00 · 🇨🇺 Cuba" in juego.boton(ADMIN, "", "ajustes").pantalla.texto
    res = juego.boton(ADMIN, "", "zonal:miami")
    assert res.alerta == "🕒 Listo: tu hora es 08:00 (🇺🇸 Miami / Florida)"
    assert "· 🇺🇸 Miami / Florida" in res.pantalla.texto
    reloj.t = DESPUES
    j = juego.db.jugador(ADMIN)
    assert juego._hora(j, reloj()) == "07:00"  # pasó el cambio de horario y el Sim sigue la hora real
    juego.boton(ADMIN, "", "continuar")
    res = juego.boton(ADMIN, "", "zona:-240")  # una hora fija
    assert res.alerta == "🕒 Listo: tu hora es 08:00" and "· UTC−4" in res.pantalla.texto
