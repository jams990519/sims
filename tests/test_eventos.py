"""Actualización 2, parte 9: eventos sorpresa (buenos, malos y de pareja), uno o dos por semana."""

import json
import random

import pytest

from simpareja import cocina as C
from simpareja import eventos as E
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import dar_objetos, nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def pareja(reloj):
    juego = nuevo_juego(reloj, eventos=True)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    return juego


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def extras(juego):
    return json.loads(hogar(juego).extras)


def forzar(juego, monkeypatch, clave):
    """El próximo tick lanza este evento."""
    monkeypatch.setattr(E, "elegir", lambda rng, en_pareja, con_trabajo, con_videos=False: E.POR_CLAVE[clave])
    h = hogar(juego)
    ex = json.loads(h.extras)
    ex["eventos"] = {"proximo": juego.reloj() - 1}
    h.extras = json.dumps(ex)
    juego.db.guardar_hogar(h)
    return [a for a in juego.tick().avisos if "Evento sorpresa" in a.texto]


def datos(aviso):
    return [d for fila in aviso.botones for _, d in fila]


def test_uno_o_dos_por_semana(pareja, reloj):
    pareja.tick()
    proximo = extras(pareja)["eventos"]["proximo"]
    assert 3 * E.DIA <= proximo - reloj() <= 5 * E.DIA
    assert all(E.elegir(random.Random(s), False, False).pareja is False for s in range(50))
    assert all(E.elegir(random.Random(s), True, False).clave != "bono" for s in range(50))


def test_sin_jugar_no_se_acumulan(pareja, reloj, monkeypatch):
    pareja.tick()
    reloj.avanzar(4 * 24 * 60)
    monkeypatch.setattr(E, "elegir", lambda *a: pytest.fail("no debía haber evento"))
    pareja.tick()
    assert extras(pareja)["eventos"]["proximo"] > reloj()


def test_bono_en_el_trabajo(pareja, monkeypatch):
    pareja.boton(ANA, "", "tomar:foto")
    avisos = forzar(pareja, monkeypatch, "bono")
    assert {a.para for a in avisos} == {ADMIN, ANA}
    assert "Bono en el trabajo" in avisos[0].texto and "Ana" in avisos[0].texto
    assert 100 <= pareja.db.jugador(ANA).cartera <= 200


def test_oferta_en_el_super(pareja, monkeypatch):
    forzar(pareja, monkeypatch, "oferta")
    texto = pareja.boton(ADMIN, "", "a:super").pantalla.texto
    assert "mitad de precio" in texto
    assert "Pollo $2.50" in str(pareja.boton(ADMIN, "", "a:super").pantalla.botones)
    assert "súper está a mitad de precio" in pareja.boton(ADMIN, "", "menu").pantalla.texto
    assert C.precio("pollo", True, oferta=True) == 2.5


def test_regalo_sorpresa(pareja, monkeypatch):
    poner(pareja, ADMIN, diversion=10, social=10)
    poner(pareja, ANA, diversion=10, social=10)
    forzar(pareja, monkeypatch, "regalo")
    subidas = [n for n in (nec(pareja, ADMIN), nec(pareja, ANA)) if n["diversion"] > 25]
    assert len(subidas) == 1 and subidas[0]["social"] == pytest.approx(20, abs=0.5)


def test_averia_bloquea_hasta_que_la_arreglan(pareja, monkeypatch):
    monkeypatch.setattr(random.Random, "choice", lambda self, s: "ducha" if "ducha" in s else list(s)[0])
    avisos = forzar(pareja, monkeypatch, "averia")
    assert "se rompió la ducha" in avisos[0].texto and "arreglar:ducha" in datos(avisos[0])
    poner(pareja, ADMIN, higiene=10)
    assert "Se rompió la ducha" in pareja.boton(ADMIN, "", "as:ducha").alerta
    casa = pareja.boton(ADMIN, "", "casa").pantalla
    assert "Averías" in casa.texto and "arreglar:ducha" in str(casa.botones)
    costo = extras(pareja)["averias"]["ducha"]
    res = pareja.boton(ADMIN, "", "arreglar:ducha")
    assert "¡Arreglaron la ducha!" in res.pantalla.texto
    assert hogar(pareja).cuenta == 2100 - costo and not extras(pareja)["averias"]
    assert pareja.boton(ADMIN, "", "as:ducha").alerta is None


def test_resfriado_no_trabaja(pareja, monkeypatch):
    monkeypatch.setattr(random.Random, "choice", lambda self, s: s[0])
    monkeypatch.setattr(random.Random, "randint", lambda self, a, b: a)
    poner(pareja, ADMIN, **LLENO)
    avisos = forzar(pareja, monkeypatch, "resfriado")
    assert "Resfriado" in avisos[0].texto and "no trabaja hoy" in avisos[0].texto
    assert nec(pareja, ADMIN)["energia"] == pytest.approx(70, abs=0.5)
    pareja.boton(ADMIN, "", "tomar:recepcion")
    assert "resfriado" in pareja.boton(ADMIN, "", "trabajar:8:sin").alerta
    assert "🤒 Estás" in pareja.boton(ADMIN, "", "menu").pantalla.texto  # resfriado, resfriada o con resfriado


def test_apagon_y_vuelve_la_luz(pareja, reloj, monkeypatch):
    monkeypatch.setattr(random.Random, "randint", lambda self, a, b: a)
    dar_objetos(pareja, ADMIN, "tv")
    forzar(pareja, monkeypatch, "apagon")
    assert "Hay un apagón" in pareja.boton(ADMIN, "", "as:tele").alerta
    reloj.avanzar(31)  # apagón de 30 min
    pareja.boton(ADMIN, "", "continuar")
    assert any("Volvió la luz" in a.texto for a in pareja.tick().avisos)
    assert pareja.boton(ADMIN, "", "as:tele").alerta is None


def test_multa_o_gasto_inesperado(pareja, monkeypatch):
    monkeypatch.setattr(random.Random, "randint", lambda self, a, b: 80)
    avisos = forzar(pareja, monkeypatch, "multa")
    assert "Gasto inesperado" in avisos[0].texto and "$80" in avisos[0].texto
    assert hogar(pareja).cuenta == 2100 - 80
    h = hogar(pareja)
    h.cuenta = 10
    pareja.db.guardar_hogar(h)
    avisos = forzar(pareja, monkeypatch, "multa")
    assert "queda pendiente" in avisos[0].texto
    assert json.loads(hogar(pareja).pendientes)[0]["monto"] == 80


def test_dia_de_lluvia(pareja, monkeypatch):
    avisos = forzar(pareja, monkeypatch, "lluvia")
    assert "🌧️ <b>Lluvia</b>: durante 2 horas" in avisos[0].texto
    assert "llueve" in pareja.boton(ADMIN, "", "as:parque").alerta


def test_visita_familiar(pareja, monkeypatch):
    poner(pareja, ADMIN, **LLENO)
    poner(pareja, ANA, social=50)
    forzar(pareja, monkeypatch, "visita")
    assert "Visita familiar: falta 🧹 limpiar la sala y 🍳 cocinar" in pareja.boton(ADMIN, "", "menu").pantalla.texto
    h = hogar(pareja)
    pareja._evento_limpio(h, "salon")
    pareja._evento_cocinado(hogar(pareja), {"receta": "pasta", "cocineros": [ADMIN]})
    avisos = pareja.tick().avisos
    assert any("La visita fue un éxito" in a.texto for a in avisos)
    assert nec(pareja, ANA)["social"] == pytest.approx(60, abs=0.5)
    assert "visita" not in extras(pareja)


def test_visita_que_no_se_atiende(pareja, reloj, monkeypatch):
    forzar(pareja, monkeypatch, "visita")
    reloj.avanzar(24 * 60 + 1)
    pareja.boton(ADMIN, "", "continuar")
    assert any("cara rara" in a.texto for a in pareja.tick().avisos)


def test_antojo_cumplido_sube_la_relacion(pareja, monkeypatch):
    monkeypatch.setattr(random.Random, "choice", lambda self, s: list(s)[1] if len(s) == 2 else list(s)[0])
    avisos = forzar(pareja, monkeypatch, "antojo")
    antojo = extras(pareja)["antojo"]
    assert antojo["de"] == ANA and "se le antoja" in avisos[0].texto
    receta = antojo["receta"]
    h = hogar(pareja)
    h.despensa = json.dumps({i: 10 for i in C.RECETAS[receta].ingredientes})
    pareja.db.guardar_hogar(h)
    pareja.boton(ADMIN, "", f"coc:{receta}:1")  # Luis se lo prepara
    reloj = pareja.reloj
    for _, minutos in C.RECETAS[receta].pasos:
        reloj.avanzar(minutos)
        pareja.boton(ADMIN, "", "coc:sig")
    avisos = pareja.tick().avisos
    assert any("le preparó su antojo" in a.texto for a in avisos)
    assert pareja._relacion(pareja.db.jugador(ANA)) == 55


def test_pregunta_de_pareja(pareja, monkeypatch):
    avisos = forzar(pareja, monkeypatch, "pregunta")
    assert all("Pregunta de pareja" in a.texto for a in avisos) and datos(avisos[0]) == ["pregr"]
    assert pareja._pregunta(hogar(pareja)) is not None


def test_sin_pareja_solo_eventos_propios(reloj, monkeypatch):
    juego = nuevo_juego(reloj, eventos=True)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    vistos = set()
    for semilla in range(40):
        juego.rng = random.Random(semilla)
        h = juego._hogar(juego.db.jugador(ADMIN).sala_id)
        ex = json.loads(h.extras)
        ex["eventos"] = {"proximo": 0}
        h.extras = json.dumps(ex)
        juego.db.guardar_hogar(h)
        for a in juego.tick().avisos:
            if "Evento sorpresa" in a.texto:
                vistos.add(a.texto.split("<b>")[2].split("</b>")[0])
    assert vistos and not vistos & {"Lluvia", "Visita familiar", "Antojo", "Pregunta de pareja", "Bono en el trabajo"}
