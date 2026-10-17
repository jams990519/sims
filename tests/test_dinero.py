"""Parte 5: casa, dinero y gastos."""

import json

import pytest

from simpareja import dinero as D
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, poner, Reloj


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


def hogar(juego, uid=ADMIN):
    return juego._hogar(juego.db.jugador(uid).sala_id)


def sin_imprevistos(monkeypatch):
    monkeypatch.setattr(D, "imprevisto", lambda rng: None)


def test_empiezan_con_3000_y_compran_la_casita(solo):
    h = hogar(solo)
    assert h.casa == "casita" and h.cuenta == 1500
    texto = solo.boton(ADMIN, "", "dinero").pantalla.texto
    assert "Cuenta compartida: <b>$1.500</b>" in texto and "Tu cartera: <b>$0</b>" in texto
    assert "+$3.000 💵 Ahorros iniciales" in texto and "−$1.500 🔑 Entrada de la Casita" in texto
    assert "se cobran en 30 días" in texto
    casa = solo.boton(ADMIN, "", "casa").pantalla.texto
    assert "Casita" in casa and "🔑 Hipoteca: $700 al mes" in casa and "💡 Luz: ✅ funciona" in casa


def test_la_pareja_comparte_la_cuenta(pareja):
    assert hogar(pareja, ANA).sala_id == hogar(pareja, ADMIN).sala_id
    assert hogar(pareja, ANA).cuenta == 1500


def test_comer_cuesta_segun_la_comida(solo, reloj):
    poner(solo, ADMIN, hambre=20)
    assert "💵 $6" in solo.boton(ADMIN, "", "a:domicilio").pantalla.texto  # a domicilio cuesta el doble
    solo.boton(ADMIN, "", "as:domicilio")
    assert hogar(solo).cuenta == 1494
    assert "−$6 🛵 Pedido a domicilio (desayuno) (Luis)" in solo.boton(ADMIN, "", "dinero").pantalla.texto


def test_comer_juntos_cuesta_por_dos(pareja):
    poner(pareja, ANA, hambre=20)
    res = pareja.boton(ANA, "", "aj:domicilio")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ADMIN, "", si)
    assert hogar(pareja).cuenta == 1488


def test_sin_dinero_no_se_come_pero_paga_la_cartera(solo):
    h = hogar(solo)
    h.cuenta = 1
    solo.db.guardar_hogar(h)
    poner(solo, ADMIN, hambre=20)
    res = solo.boton(ADMIN, "", "as:domicilio")
    assert "No alcanza el dinero ($6)" in res.alerta
    j = solo.db.jugador(ADMIN)
    j.cartera = 10
    solo.db.guardar_jugador(j)
    res = solo.boton(ADMIN, "", "as:domicilio")
    assert res.alerta is None and solo.db.jugador(ADMIN).cartera == 4


def test_pasar_dinero_entre_cartera_y_compartida(solo):
    res = solo.boton(ADMIN, "", "mover:ret")
    assert "mv:ret:500" in str(res.pantalla.botones)
    res = solo.boton(ADMIN, "", "mv:ret:500")
    assert "Pasaste $500 a tu cartera" in res.pantalla.texto
    assert solo.db.jugador(ADMIN).cartera == 500 and hogar(solo).cuenta == 1000
    solo.boton(ADMIN, "", "mv:dep:100")
    assert solo.db.jugador(ADMIN).cartera == 400 and hogar(solo).cuenta == 1100
    assert solo.boton(ADMIN, "", "mv:dep:9999").alerta == "No hay suficiente dinero."


def test_el_uso_sube_la_luz_y_el_agua(solo, reloj):
    poner(solo, ADMIN, higiene=10)
    solo.boton(ADMIN, "", "as:ducha")
    reloj.avanzar(16)
    solo.boton(ADMIN, "", "sim")
    solo.boton(ADMIN, "", "as:tele")
    consumo = json.loads(hogar(solo).consumo)
    assert consumo == {"agua": 0.6, "luz": 0.3}


def test_cobro_mensual_de_las_facturas(solo, reloj, monkeypatch):
    sin_imprevistos(monkeypatch)
    h = hogar(solo)
    h.cuenta = 2000
    h.consumo = json.dumps({"luz": 12.4, "agua": 6})
    solo.db.guardar_hogar(h)
    ir_al_dia(solo, reloj, ADMIN, 31)
    res = solo.tick()
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    total = 700 + 102 + 46 + 50 + 30
    assert f"Se cobraron las facturas del mes</b>: {D.dinero(total)}" in aviso.texto
    h = hogar(solo)
    assert h.cuenta == 2000 - total and h.consumo == "{}" and h.proximo_cobro == 61
    assert not solo.tick().avisos  # no se cobra dos veces


def test_si_no_alcanza_hay_recargo_y_corte(solo, reloj, monkeypatch):
    sin_imprevistos(monkeypatch)
    h = hogar(solo)
    h.cuenta = 780  # alcanza para la hipoteca y el agua, no para la luz
    solo.db.guardar_hogar(h)
    ir_al_dia(solo, reloj, ADMIN, 31)
    aviso = next(a for a in solo.tick().avisos if a.para == ADMIN)
    assert "No alcanzó para 💡 Luz: ahora deben $99" in aviso.texto and "no hay tele" in aviso.texto
    h = hogar(solo)
    # se paga lo que alcanza en orden: hipoteca, (luz no), agua, (internet no), gas
    assert D.servicios_cortados(json.loads(h.pendientes)) == {"luz", "internet"}
    assert "Les cortaron la luz" in solo.boton(ADMIN, "", "a:tele").alerta
    assert "Servicio cortado" in solo.boton(ADMIN, "", "sim").pantalla.texto
    # pagan la luz con la cartera
    j = solo.db.jugador(ADMIN)
    j.cartera = 200
    solo.db.guardar_jugador(j)
    res = solo.boton(ADMIN, "", "facturas")
    luz = next(d for fila in res.pantalla.botones for t, d in fila if "Luz" in t)
    res = solo.boton(ADMIN, "", luz)
    assert "Ya volvió el servicio" in res.pantalla.texto
    assert solo.db.jugador(ADMIN).cartera == 101
    assert solo.boton(ADMIN, "", "a:tele").alerta is None


def test_imprevistos(solo, reloj, monkeypatch):
    monkeypatch.setattr(D, "imprevisto", lambda rng: ("🔧 Se rompió la lavadora", 200))
    ir_al_dia(solo, reloj, ADMIN, 2)
    aviso = next(a for a in solo.tick().avisos if a.para == ADMIN)
    assert "Se rompió la lavadora: $200" in aviso.texto
    assert hogar(solo).cuenta == 1300


def test_dinero_formato():
    assert D.dinero(3000) == "$3.000"
    assert D.dinero(-1500) == "−$1.500"
    assert D.total_mes({}) == 910
