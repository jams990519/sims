"""Actualización 2, parte 12: el primer viaje en pareja."""

import json

import pytest

from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


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


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def reservar(juego, destino="playa", dia=None):
    hoy = juego._hoy(juego.db.jugador(ADMIN))
    res = juego.boton(ADMIN, "", f"viaje:{destino}:{dia or hoy}")
    juego.boton(ANA, "", "viajeok")
    return res


def test_proponer_y_aceptar(pareja):
    assert "viaje" in datos(pareja.boton(ADMIN, "", "mpar").pantalla)
    res = pareja.boton(ADMIN, "", "viaje")
    assert "viaje:playa" in datos(res.pantalla) and "$2.000" in str(res.pantalla.botones)
    hoy = pareja._hoy(pareja.db.jugador(ADMIN))
    res = pareja.boton(ADMIN, "", "viaje:playa")
    assert ("Hoy", f"viaje:playa:{hoy}") in res.pantalla.botones[0] and "no trabajan" in res.pantalla.texto
    res = pareja.boton(ADMIN, "", f"viaje:playa:{hoy + 1}")
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "la playa · 2 días, del martes 2 al miércoles 3 · $800" in aviso.texto and datos(aviso) == ["viajeok", "viajeno"]
    res = pareja.boton(ANA, "", "viajeok")
    assert "¡Viaje reservado!" in res.pantalla.texto and hogar(pareja).cuenta == 2100 - 800
    assert any(a.para == ADMIN and "aceptó el viaje" in a.texto for a in res.avisos)


def test_durante_el_viaje(pareja, reloj):
    poner(pareja, ADMIN, **LLENO)
    pareja.boton(ADMIN, "", "tomar:recepcion")
    reservar(pareja)
    avisos = [a for a in pareja.tick().avisos if "Se van de viaje" in a.texto]
    assert {a.para for a in avisos} == {ADMIN, ANA}
    assert pareja.db.jugador(ANA).lugar == "fuera:viaje"
    assert "Están de viaje" in pareja.boton(ADMIN, "", "as:tele").alerta
    assert "de viaje" in pareja.boton(ADMIN, "", "trabajar:8:sin").alerta
    assert "✈️ de viaje" in pareja.boton(ADMIN, "", "plano").pantalla.texto
    poner(pareja, ADMIN, hambre=50)
    reloj.avanzar(3)
    pareja.boton(ADMIN, "", "sim")
    reloj.avanzar(3)
    pareja.boton(ADMIN, "", "sim")
    assert nec(pareja, ADMIN)["hambre"] == pytest.approx(50, abs=0.01)  # de viaje no bajan


def test_al_volver(pareja, reloj):
    reservar(pareja)
    pareja.tick()
    poner(pareja, ANA, diversion=20, energia=20)
    ir_al_dia(pareja, reloj, ADMIN, 3)  # el viaje era hoy y mañana
    avisos = pareja.tick().avisos
    assert any(a.para == ANA and "Volvieron del viaje" in a.texto for a in avisos)
    assert any(a.para == ANA and "HITO DE PAREJA" in a.texto and "Primer viaje" in a.texto for a in avisos)
    ana = pareja.db.jugador(ANA)
    assert ana.lugar == "salon" and nec(pareja, ANA)["diversion"] == 100 and nec(pareja, ANA)["energia"] == ana.energia_max
    ex = json.loads(hogar(pareja).extras)
    assert ex["viajes"] == 1 and "viaje" not in ex
    assert "Viaje a la playa (2 días)" in pareja.boton(ADMIN, "", "album").pantalla.texto
    assert pareja.boton(ADMIN, "", "as:tele").alerta is None


def test_decir_que_no_y_sin_dinero(pareja):
    hoy = pareja._hoy(pareja.db.jugador(ADMIN))
    pareja.boton(ADMIN, "", f"viaje:paris:{hoy}")
    res = pareja.boton(ANA, "", "viajeno")
    assert any(a.para == ADMIN and "para otro momento" in a.texto for a in res.avisos)
    h = hogar(pareja)
    h.cuenta = 100
    pareja.db.guardar_hogar(h)
    pareja.boton(ADMIN, "", f"viaje:paris:{hoy}")
    assert "No alcanza: el viaje cuesta $2.000" in pareja.boton(ANA, "", "viajeok").alerta
