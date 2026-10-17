"""Actualización 2, parte 3: casa en renta, meta de ahorro, mudanza y casa propia."""

import json

import pytest

from simpareja import dinero as D
from simpareja.db import Hogar
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


def poner_cuenta(juego, monto):
    h = hogar(juego)
    h.cuenta = monto
    juego.db.guardar_hogar(h)


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def test_meta_de_ahorro_en_la_cuenta_compartida(solo):
    texto = solo.boton(ADMIN, "", "dinero").pantalla.texto
    assert "🎯 Meta «nuestra casa»: 🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜ $2.100 de $15.000 · faltan $12.900" in texto
    assert "🚚 Para mudarse al apartamento grande: $3.900 ahorrados · faltan $1.800" in texto


def test_sin_ahorro_no_se_mudan(solo):
    res = solo.boton(ADMIN, "", "mudanza")
    assert "Viven en: 🏡 Casita en renta · renta $900/mes" in res.pantalla.texto
    assert "Depósito $1.300 + camión $150 − su depósito de $900 = $550" in res.pantalla.texto
    assert "🔒 Mudarnos al apartamento grande" in str(res.pantalla.botones)
    res = solo.boton(ADMIN, "", "mudanza:apartamento")
    assert res.alerta == "Todavía faltan $1.800 en la cuenta compartida."
    assert hogar(solo).casa == "casita"


def test_mudarse_sin_pareja(solo):
    poner_cuenta(solo, 4000)
    res = solo.boton(ADMIN, "", "mudanza:apartamento")
    assert "¿Confirmar?" in res.pantalla.texto and "mudanza:apartamento:si" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "mudanza:apartamento:si")
    assert "¡Se mudaron al apartamento grande!" in res.pantalla.texto and "cuarto extra 🧸" in res.pantalla.texto
    h = hogar(solo)
    assert h.casa == "apartamento" and h.cuenta == 4000 + 900 - 1300 - 150
    assert json.loads(h.extras)["deposito"] == 1300 and "mudanza" in json.loads(h.extras)["hitos"]
    assert "🔑 Renta: $1.300 al mes" in res.pantalla.texto and "🧸 Cuarto extra" in res.pantalla.texto
    assert "ir:extra" in datos(solo.boton(ADMIN, "", "moverse").pantalla)
    texto = solo.boton(ADMIN, "", "dinero").pantalla.texto
    assert "↩️ Depósito devuelto" in texto and "🚚 Camión de mudanza" in texto


def test_la_renta_nueva_se_cobra_con_las_facturas(solo, reloj, monkeypatch):
    monkeypatch.setattr(D, "imprevisto", lambda rng: None)
    poner_cuenta(solo, 4000)
    solo.boton(ADMIN, "", "mudanza:apartamento:si")
    assert "🔑 Renta: $1.300" in solo.boton(ADMIN, "", "facturas").pantalla.texto
    ir_al_dia(solo, reloj, ADMIN, 31)
    aviso = next(a for a in solo.tick().avisos if a.para == ADMIN)
    assert f"Se cobraron las facturas del mes</b>: {D.dinero(1300 + 90 + 40 + 50 + 30)}" in aviso.texto


def test_en_pareja_aceptan_los_dos(pareja):
    poner_cuenta(pareja, 4000)
    res = pareja.boton(ANA, "", "mudanza:apartamento")
    assert "Luis</b> también tiene que aceptar" in res.pantalla.texto
    res = pareja.boton(ANA, "", "mudanza:apartamento:si")
    assert "Propuesta enviada" in res.pantalla.texto and hogar(pareja).casa == "casita"
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert "propone mudarse al apartamento grande" in aviso.texto
    assert datos(aviso) == ["mudok:apartamento", "mudno"]
    assert pareja.boton(ANA, "", "mudok:apartamento").alerta == "Esa propuesta de mudanza ya no está."
    res = pareja.boton(ADMIN, "", "mudok:apartamento")
    assert "¡Se mudaron al apartamento grande!" in res.pantalla.texto
    assert any(a.para == ANA and "aceptó" in a.texto for a in res.avisos)
    assert hogar(pareja).casa == "apartamento"


def test_la_pareja_puede_decir_que_no(pareja, reloj):
    poner_cuenta(pareja, 4000)
    pareja.boton(ANA, "", "mudanza:apartamento:si")
    res = pareja.boton(ADMIN, "", "mudno")
    assert any(a.para == ANA and "prefiere no mudarse" in a.texto for a in res.avisos)
    assert pareja.boton(ADMIN, "", "mudok:apartamento").alerta == "Esa propuesta de mudanza ya no está."
    pareja.boton(ANA, "", "mudanza:apartamento:si")
    reloj.avanzar(25 * 60)  # la propuesta dura un día
    pareja.boton(ADMIN, "", "continuar")
    assert pareja.boton(ADMIN, "", "mudok:apartamento").alerta == "Esa propuesta de mudanza ya no está."
    assert hogar(pareja).casa == "casita"


def test_comprar_nuestra_casa(solo):
    poner_cuenta(solo, 16000)
    assert "✅ ¡ya alcanza!" in solo.boton(ADMIN, "", "dinero").pantalla.texto
    res = solo.boton(ADMIN, "", "mudanza:propia")
    assert "Entrada $15.000 + camión $150 − su depósito de $900 = $14.250" in res.pantalla.texto
    res = solo.boton(ADMIN, "", "mudanza:propia:si")
    assert "¡Compraron «nuestra casa»!" in res.pantalla.texto
    h = hogar(solo)
    assert h.casa == "propia" and h.cuenta == 16000 - 14250
    assert "🏦 Hipoteca: $1.200 al mes · ¡la casa es suya!" in res.pantalla.texto
    assert "🏠 ¡Viven en su propia casa!" in solo.boton(ADMIN, "", "dinero").pantalla.texto
    assert "Esta casa es suya" in solo.boton(ADMIN, "", "mudanza").pantalla.texto
    assert "mudanza:apartamento" not in datos(solo.boton(ADMIN, "", "mudanza").pantalla)
    assert "🏦 Hipoteca: $1.200" in solo.boton(ADMIN, "", "facturas").pantalla.texto
    assert "Esta casa es suya: pueden pintarla" in solo.boton(ADMIN, "", "remodelar").pantalla.texto


def test_remodelar_solo_en_casa_propia(solo):
    texto = solo.boton(ADMIN, "", "remodelar").pantalla.texto
    assert "🔒 Solo se puede remodelar una casa propia" in texto and "solo se ponen muebles" in texto


def test_mudarse_a_algo_mas_barato(solo):
    poner_cuenta(solo, 4000)
    solo.boton(ADMIN, "", "mudanza:apartamento:si")
    solo.boton(ADMIN, "", "ir:extra")
    assert solo.db.jugador(ADMIN).lugar == "extra"
    res = solo.boton(ADMIN, "", "mudanza:casita")
    assert "les sobran $250" in res.pantalla.texto
    solo.boton(ADMIN, "", "mudanza:casita:si")
    assert hogar(solo).casa == "casita" and hogar(solo).cuenta == 3450 + 250
    assert solo.db.jugador(ADMIN).lugar == "salon"  # el cuarto extra ya no existe
    assert "ir:extra" not in datos(solo.boton(ADMIN, "", "moverse").pantalla)
    assert solo.boton(ADMIN, "", "a:limpiar:extra").pantalla.texto.startswith("🧹 <b>¿Qué zona")


def test_partidas_de_antes_pasan_a_renta(solo):
    sala = solo.db.jugador(ADMIN).sala_id
    hoy = solo._dia_hogar(sala)
    viejo = Hogar(sala, json.dumps({"salon": 0}), casa="casita", cuenta=1500, dia_hogar=hoy, proximo_cobro=hoy + 20)
    solo.db.guardar_hogar(viejo)
    h = solo._hogar(sala)
    assert h.cuenta == 2100 and json.loads(h.extras)["deposito"] == 900
    assert solo._hogar(sala).cuenta == 2100  # solo una vez
    assert "↩️ La casita ahora es de renta" in solo.boton(ADMIN, "", "dinero").pantalla.texto
