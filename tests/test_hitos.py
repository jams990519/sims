"""Actualización 2, parte 12: hitos de pareja."""

import json

import pytest

from simpareja import hitos_juego as H
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, Reloj


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def pareja(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    return juego


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def extras(juego):
    return json.loads(hogar(juego).extras)


def test_la_seccion_de_hitos(pareja):
    assert "hitos" in str(pareja.boton(ADMIN, "", "mpar").pantalla.botones)
    texto = pareja.boton(ADMIN, "", "hitos").pantalla.texto
    for hito in H.HITOS:
        assert hito.nombre in texto
    assert "Llevan 0 de 8" in texto and "⬜ 🌹 Primera cita" in texto


def test_primera_cita_se_completa_sola_y_se_celebra(pareja, reloj):
    res = pareja.boton(ANA, "", "aj:cine")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ADMIN, "", si)
    reloj.avanzar(3 * 60)
    pareja.tick()
    assert "primera_cita" in extras(pareja)["hitos"]
    assert "primera_cita" not in extras(pareja).get("hitos_celebrados", {})  # no están conectados
    pareja.boton(ADMIN, "", "continuar")
    assert "¡logrado! Se celebra cuando estén los dos" in pareja.boton(ADMIN, "", "hitos").pantalla.texto
    pareja.boton(ANA, "", "continuar")
    avisos = [a for a in pareja.tick().avisos if "HITO DE PAREJA" in a.texto]
    assert {a.para for a in avisos} == {ADMIN, ANA} and "🌹 <b>Primera cita</b>" in avisos[0].texto
    assert pareja._relacion(pareja.db.jugador(ADMIN)) == 60
    assert not [a for a in pareja.tick().avisos if "HITO" in a.texto]  # una sola vez
    assert "✅ 🌹 <b>Primera cita</b>" in pareja.boton(ADMIN, "", "hitos").pantalla.texto
    assert "🏆 <b>Hitos</b>" in pareja.boton(ADMIN, "", "album").pantalla.texto


def test_primer_mes(pareja, reloj):
    ir_al_dia(pareja, reloj, ADMIN, 31)
    avisos = [a for a in pareja.tick().avisos if "HITO" in a.texto]
    assert avisos and "📅 <b>Primer mes</b>" in avisos[0].texto and "+15" in avisos[0].texto


def test_mudanza_y_casa_propia(pareja):
    h = hogar(pareja)
    h.cuenta = 20000
    pareja.db.guardar_hogar(h)
    pareja.boton(ANA, "", "mudanza:apartamento:si")
    pareja.boton(ADMIN, "", "mudok:apartamento")
    pareja.boton(ANA, "", "mudanza:propia:si")
    pareja.boton(ADMIN, "", "mudok:propia")
    avisos = [a for a in pareja.tick().avisos if "HITO" in a.texto and a.para == ADMIN]
    assert len(avisos) == 2 and "Mudanza" in avisos[0].texto and "Casa propia" in avisos[1].texto
    assert pareja._relacion(pareja.db.jugador(ANA)) == 50 + 10 + 20
