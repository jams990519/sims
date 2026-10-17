"""Actualización 2, parte 12: compromiso y boda."""

import json

import pytest

from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, poner, Reloj

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


def extras(juego):
    return json.loads(hogar(juego).extras)


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def listos_para_comprometerse(juego):
    for uid in (ADMIN, ANA):
        juego._cambiar_relacion(juego.db.jugador(uid), 35, "prueba")
    h = hogar(juego)
    juego._lograr_hito(h, "viaje")
    j = juego.db.jugador(ADMIN)
    j.cartera = 1000
    juego.db.guardar_jugador(j)


def comprometerse(juego):
    listos_para_comprometerse(juego)
    juego.boton(ADMIN, "", "compa:sencillo")
    juego.boton(ADMIN, "", "comppe")
    juego.boton(ANA, "", "compsi")


def test_requisitos_del_compromiso(pareja):
    texto = pareja.boton(ADMIN, "", "comp").pantalla.texto
    assert "❌ Tu medidor por encima del 80 % (ahora 50 %)" in texto and "❌ Haber hecho su primer viaje" in texto
    assert "comppe" not in datos(pareja.boton(ADMIN, "", "comp").pantalla)
    assert pareja.boton(ADMIN, "", "comppe").alerta == "Todavía no se cumplen los requisitos."


def test_anillo_en_secreto_y_pedida(pareja):
    listos_para_comprometerse(pareja)
    res = pareja.boton(ADMIN, "", "compa")
    assert "compa:ensueno" in datos(res.pantalla)
    res = pareja.boton(ADMIN, "", "compa:sencillo")
    assert not res.avisos and pareja.db.jugador(ADMIN).cartera == 500  # Ana no se entera
    assert "🤫 Una compra secreta" in pareja.boton(ANA, "", "dinero").pantalla.texto
    res = pareja.boton(ADMIN, "", "comppe")
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "¿Quieres casarte conmigo?" in aviso.texto and datos(aviso) == ["compsi", "compno"]
    res = pareja.boton(ANA, "", "compsi")
    assert "¡Están comprometidos!" in res.pantalla.texto
    assert any(a.para == ADMIN and "dijo que SÍ" in a.texto for a in res.avisos)
    assert "compromiso" in extras(pareja)["hitos"]
    assert "💍 Comprometidos" in pareja.boton(ADMIN, "", "sala").pantalla.texto


def test_si_dice_que_no_se_conserva_el_anillo(pareja):
    listos_para_comprometerse(pareja)
    pareja.boton(ADMIN, "", "compa:brillante")
    pareja.boton(ADMIN, "", "comppe")
    res = pareja.boton(ANA, "", "compno")
    assert any(a.para == ADMIN and "Guardas el anillo" in a.texto for a in res.avisos)
    assert extras(pareja)["anillos"][str(ADMIN)] == "brillante" and "compromiso" not in extras(pareja)
    assert "comppe" in datos(pareja.boton(ADMIN, "", "comp").pantalla)  # puede volver a pedirlo sin comprar otro


def test_planear_la_boda_y_casarse(pareja, reloj):
    comprometerse(pareja)
    h = hogar(pareja)
    h.cuenta = 10000
    pareja.db.guardar_hogar(h)
    res = pareja.boton(ADMIN, "", "bodap")
    assert "bodap:playa" in datos(res.pantalla)
    pareja.boton(ADMIN, "", "bodap:jardin")
    pareja.boton(ADMIN, "", "bodap:jardin:familia")
    res = pareja.boton(ADMIN, "", "bodap:jardin:familia:cena")
    assert "Total: $5.300" in res.pantalla.texto and "bodap:jardin:familia:cena:3" in datos(res.pantalla)
    res = pareja.boton(ADMIN, "", "bodap:jardin:familia:cena:3")
    assert any(a.para == ANA and "plan de la boda" in a.texto for a in res.avisos)
    res = pareja.boton(ANA, "", "bodaok")
    assert "¡Boda reservada!" in res.pantalla.texto and hogar(pareja).cuenta == 10000 - 5300
    ir_al_dia(pareja, reloj, ADMIN, 4)
    assert any("¡Hoy es su boda!" in a.texto for a in pareja.tick().avisos)
    res = pareja.boton(ADMIN, "", "bodasi")
    assert any(a.para == ANA and "Sí, acepto" in a.texto for a in res.avisos)
    res = pareja.boton(ANA, "", "bodasi")
    assert "¡Se casaron!" in res.pantalla.texto
    assert "💒 Casados" in pareja.boton(ADMIN, "", "sala").pantalla.texto
    assert any("HITO" in a.texto and "Boda" in a.texto for a in pareja.tick().avisos)
    assert "viaje" in datos(pareja.boton(ADMIN, "", "boda").pantalla)  # luna de miel


def test_unir_el_dinero(pareja, reloj):
    comprometerse(pareja)
    ex = extras(pareja)
    ex["casados"] = reloj()
    h = hogar(pareja)
    h.extras = json.dumps(ex)
    pareja.db.guardar_hogar(h)
    j = pareja.db.jugador(ANA)
    j.cartera = 300
    pareja.db.guardar_jugador(j)
    antes = hogar(pareja).cuenta
    res = pareja.boton(ADMIN, "", "unir")
    assert any(a.para == ANA and "unir el dinero" in a.texto for a in res.avisos)
    res = pareja.boton(ANA, "", "unirok")
    assert "¡Unieron el dinero!" in res.pantalla.texto
    assert hogar(pareja).cuenta == antes + 300 + 500 and pareja.db.jugador(ADMIN).cartera == 0
    pareja.boton(ANA, "", "tomar:recepcion")
    poner(pareja, ANA, **LLENO)
    pareja.boton(ANA, "", "trabajar:8:sin")
    antes = hogar(pareja).cuenta
    reloj.avanzar(8 * 60 + 1)
    pareja.tick()
    assert hogar(pareja).cuenta == antes + 88 and pareja.db.jugador(ANA).cartera == 0


def test_si_no_se_casan_ese_dia_se_pospone(pareja, reloj):
    comprometerse(pareja)
    h = hogar(pareja)
    h.cuenta = 10000
    pareja.db.guardar_hogar(h)
    pareja.boton(ADMIN, "", "bodap:juzgado:solos:pastel:3")
    pareja.boton(ANA, "", "bodaok")
    ir_al_dia(pareja, reloj, ADMIN, 5)
    assert any("se movió" in a.texto for a in pareja.tick().avisos)
    assert extras(pareja)["boda"]["dia"] == pareja._hoy(pareja.db.jugador(ADMIN)) + 7
