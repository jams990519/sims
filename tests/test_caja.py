"""Caja de ahorros: se abre cuando la pareja lo decide, no se gasta en facturas y gana un 1 % al mes."""

import json

import pytest

from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, Reloj


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def solo(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    return juego


@pytest.fixture
def pareja(solo):
    aceptar(solo, ANA, invitar(solo, ADMIN, ANA))
    crear_personaje(solo, ANA, "Ana")
    return solo


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def caja(juego):
    return json.loads(hogar(juego).extras).get("caja")


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def con_dinero(juego, cartera=0, cuenta=None):
    j = juego.db.jugador(ADMIN)
    j.cartera = cartera
    juego.db.guardar_jugador(j)
    if cuenta is not None:
        h = hogar(juego)
        h.cuenta = cuenta
        juego.db.guardar_hogar(h)


def test_sin_pareja_se_abre_al_momento(solo):
    res = solo.boton(ADMIN, "", "dinero")
    assert "caja" in datos(res.pantalla) and "Caja de ahorros:" not in res.pantalla.texto
    res = solo.boton(ADMIN, "", "caja")
    assert "no se gasta en facturas" in res.pantalla.texto and "caja:abrir" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "caja:abrir")
    assert "¡Abriste tu caja de ahorros!" in res.pantalla.texto and caja(solo)["saldo"] == 0
    con_dinero(solo, cartera=100, cuenta=1000)
    assert "cajap:c:100" in datos(solo.boton(ADMIN, "", "caja:poner:c").pantalla)
    solo.boton(ADMIN, "", "cajap:c:50")
    solo.boton(ADMIN, "", "cajap:h:500")
    assert caja(solo)["saldo"] == 550 and solo.db.jugador(ADMIN).cartera == 50 and hogar(solo).cuenta == 500
    assert solo.boton(ADMIN, "", "cajap:c:999").alerta == "No hay suficiente dinero."
    texto = solo.boton(ADMIN, "", "dinero").pantalla.texto
    assert "🐷 Caja de ahorros: <b>$550</b>" in texto and "🐷 +$50 🐷 Ahorro" in texto
    res = solo.boton(ADMIN, "", "cajas:100")  # sin pareja se saca al momento
    assert "Sacaste $100" in res.pantalla.texto and caja(solo)["saldo"] == 450 and hogar(solo).cuenta == 600


def test_la_pareja_decide_abrirla(pareja):
    res = pareja.boton(ADMIN, "", "caja:abrir")
    assert "Propuesta enviada" in res.pantalla.texto and caja(pareja) is None
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "caja de ahorros" in aviso.texto and datos(aviso) == ["cajaok", "cajano"]
    assert "Esperando a que" in pareja.boton(ADMIN, "", "caja").pantalla.texto
    assert "cajaok" in datos(pareja.boton(ANA, "", "caja").pantalla)  # Ana también lo ve en la caja
    res = pareja.boton(ANA, "", "cajaok")
    assert "¡Abrieron la caja de ahorros!" in res.pantalla.texto and caja(pareja) == {"saldo": 0, "desde": caja(pareja)["desde"]}
    assert any(a.para == ADMIN and "aceptó" in a.texto for a in res.avisos)


def test_rechazar_y_propuesta_vencida(pareja, reloj):
    pareja.boton(ADMIN, "", "caja:abrir")
    res = pareja.boton(ANA, "", "cajano")
    assert any(a.para == ADMIN and "prefiere no abrir la caja" in a.texto for a in res.avisos)
    assert caja(pareja) is None
    pareja.boton(ADMIN, "", "caja:abrir")
    reloj.avanzar(25 * 60)
    pareja.boton(ANA, "", "continuar")
    assert pareja.boton(ANA, "", "cajaok").alerta == "Esa propuesta ya no está."
    assert caja(pareja) is None


def test_poner_avisa_y_sacar_lo_deciden_los_dos(pareja):
    pareja.boton(ADMIN, "", "caja:abrir")
    pareja.boton(ANA, "", "cajaok")
    con_dinero(pareja, cuenta=1000)
    res = pareja.boton(ADMIN, "", "cajap:h:500")
    assert any(a.para == ANA and "puso $500 en la caja" in a.texto for a in res.avisos)
    res = pareja.boton(ADMIN, "", "cajas:200")
    assert "Le pregunté" in res.pantalla.texto and caja(pareja)["saldo"] == 500  # todavía no se saca
    assert datos(next(a for a in res.avisos if a.para == ANA)) == ["cajaok", "cajano"]
    pareja.boton(ANA, "", "cajano")
    assert caja(pareja)["saldo"] == 500
    pareja.boton(ADMIN, "", "cajas:200")
    res = pareja.boton(ANA, "", "cajaok")
    assert "Sacaron $200" in res.pantalla.texto
    assert caja(pareja)["saldo"] == 300 and hogar(pareja).cuenta == 700


def test_las_facturas_no_la_tocan_y_gana_intereses(solo, reloj):
    solo.boton(ADMIN, "", "caja:abrir")
    con_dinero(solo, cuenta=1000)
    solo.boton(ADMIN, "", "cajap:h:1000")
    assert hogar(solo).cuenta == 0
    ir_al_dia(solo, reloj, ADMIN, 31)
    aviso = next(a for a in solo.tick().avisos if a.para == ADMIN and "Se cobraron" in a.texto)
    assert "La caja de ahorros ganó $10: ahora tiene $1.010" in aviso.texto
    assert caja(solo)["saldo"] == 1010 and hogar(solo).cuenta == 0  # las facturas quedan pendientes, la caja intacta
