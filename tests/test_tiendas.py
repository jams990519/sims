"""Actualización 2, parte 13: objetos que hay que comprar y tiendas que crecen."""

import json

import pytest

from simpareja import objetos as O
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import dar_objetos, nec, nuevo_juego, poner, Reloj


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


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def test_objetos_incluidos_y_los_que_faltan(solo):
    assert "objetos" in datos(solo.boton(ADMIN, "", "mcasa").pantalla)
    texto = solo.boton(ADMIN, "", "objetos").pantalla.texto
    assert "Incluidos con la casa: 🛏️ cama, 🔥 estufa, 🧊 nevera, 🚿 ducha, 📱 móvil básico" in texto
    for nombre in ("Televisión · $300", "Lavadora · $350", "Sofá · $400", "Móvil mejor · $200", "Cámara · $250",
                   "Aro de luz · $60", "Micrófono · $80"):
        assert nombre in texto


def test_sin_tele_no_hay_tele_y_se_compra(pareja):
    res = pareja.boton(ADMIN, "", "as:tele")
    assert "No tienen televisión: cómprenla en la tienda de electrónica ($300)" in res.alerta
    assert "tienda:electronica" in datos(pareja.boton(ADMIN, "", "mlug").pantalla)
    res = pareja.boton(ADMIN, "", "tienda:electronica")
    assert "comprar:tv" in datos(res.pantalla) and "comprar:consola" not in datos(res.pantalla)  # aún no la sacan
    res = pareja.boton(ADMIN, "", "comprar:tv")
    assert "¡Compraron 📺 televisión!" in res.pantalla.texto and hogar(pareja).cuenta == 2100 - 300
    assert any(a.para == ANA and "compró 📺 televisión" in a.texto for a in res.avisos)
    assert pareja.boton(ADMIN, "", "comprar:tv").alerta == "Eso no se puede comprar ahora."
    assert pareja.boton(ADMIN, "", "as:tele").alerta is None
    assert "tele" in pareja.boton(ADMIN, "", "plano").pantalla.texto.split("<pre>")[1]


def test_sin_lavadora_se_paga_la_lavanderia(solo):
    h = hogar(solo)
    h.ropa_sucia = 20
    solo.db.guardar_hogar(h)
    assert "💵 $8" in solo.boton(ADMIN, "", "a:lavar").pantalla.texto
    solo.boton(ADMIN, "", "as:lavar")
    assert hogar(solo).cuenta == 2100 - 8
    solo.boton(ADMIN, "", "parar")
    dar_objetos(solo, ADMIN, "lavadora")
    assert "💵" not in solo.boton(ADMIN, "", "a:lavar").pantalla.texto


def test_sofa_y_movil_rinden_mas(solo):
    dar_objetos(solo, ADMIN, "tv", "sofa", "movil")
    assert "+19 🎉 diversión, +3 💬 social" in solo.boton(ADMIN, "", "a:tele").pantalla.texto  # 15 × 1,25
    assert O.aplicar_bonos("redes", {"diversion": 10, "social": 5}, {"movil", "sofa"}) == {"diversion": 18.8, "social": 7.5}
    assert O.aplicar_bonos("ducha", {"higiene": 60}, {"bano"}) == {"higiene": 70}


def test_la_decoracion_y_la_cama(solo, reloj):
    dar_objetos(solo, ADMIN, "plantas", "cuadros")
    poner(solo, ADMIN, diversion=100)
    reloj.avanzar(60)
    solo.boton(ADMIN, "", "continuar")
    assert solo._multiplicadores(solo.db.jugador(ADMIN))["diversion"] == pytest.approx(0.8)
    assert O.aplicar_bonos("dormir", {"energia": 100}, {"cama"}) == {"energia": 115.0}


def test_las_tiendas_crecen_con_los_hitos(pareja):
    assert "comprar:plantas" not in datos(pareja.boton(ADMIN, "", "tienda:muebles").pantalla)
    h = hogar(pareja)
    ex = json.loads(h.extras)
    ex["hitos_celebrados"] = {"primera_cita": 1}
    h.extras = json.dumps(ex)
    pareja.db.guardar_hogar(h)
    assert "comprar:plantas" in datos(pareja.boton(ADMIN, "", "tienda:muebles").pantalla)
    assert "comprar:consola" in datos(pareja.boton(ADMIN, "", "tienda:electronica").pantalla)
    assert "comprar:banera" not in datos(pareja.boton(ADMIN, "", "tienda:muebles").pantalla)


def test_consola(solo, reloj):
    poner(solo, ADMIN, diversion=10)
    assert "No tienen consola" in solo.boton(ADMIN, "", "as:consola").alerta
    dar_objetos(solo, ADMIN, "consola")
    solo.boton(ADMIN, "", "as:consola")
    reloj.avanzar(61)
    solo.boton(ADMIN, "", "sim")
    assert nec(solo, ADMIN)["diversion"] == pytest.approx(10 + 20 - 5, abs=0.5)


def test_remodelar_solo_en_casa_propia(solo):
    assert "comprar:pintar" not in str(solo.boton(ADMIN, "", "tienda:reforma").pantalla.botones)
    assert solo.boton(ADMIN, "", "comprar:pintar").alerta == "Eso no se puede comprar ahora."
    h = hogar(solo)
    h.cuenta = 20000
    solo.db.guardar_hogar(h)
    solo.boton(ADMIN, "", "mudanza:propia:si")
    res = solo.boton(ADMIN, "", "comprar:pintar")
    assert "¡Compraron 🎨 pintar y decorar!" in res.pantalla.texto
    poner(solo, ADMIN, higiene=10)
    solo.boton(ADMIN, "", "as:ducha")
    assert json.loads(hogar(solo).zonas)["bano"] == 4  # ensucia la mitad (8 / 2)
