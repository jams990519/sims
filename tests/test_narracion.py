"""Narración de las acciones: mensajitos mientras dura cada acción (el restaurante primero)."""

import pytest

from simpareja import narracion as N
from simpareja import vida as V
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, poner, Reloj

LLENO = dict(hambre=40, energia=100, higiene=100, diversion=50, social=50)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def solo(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    poner(juego, ADMIN, **LLENO)
    return juego


@pytest.fixture
def pareja(solo):
    aceptar(solo, ANA, invitar(solo, ADMIN, ANA))
    crear_personaje(solo, ANA, "Ana")
    poner(solo, ANA, **LLENO)
    return solo


def datos(aviso):
    return [d for fila in aviso.botones for _, d in fila]


def hasta(juego, reloj, minuto, inicio):
    """Avanza hasta `minuto` desde que empezó la acción y devuelve los mensajitos de narración."""
    reloj.t = inicio + minuto * 60
    return [a for a in juego.tick().avisos if a.silencio or "rplato:" in str(a.botones) or "rpostre:" in str(a.botones)]


def test_etapas():
    assert N.siguiente(N.RESTAURANTE, 0, 0.01) is None
    assert N.siguiente(N.RESTAURANTE, 0, 0.05) == 0
    assert N.siguiente(N.RESTAURANTE, 1, 0.05) is None
    assert N.siguiente(N.RESTAURANTE, 1, 0.5) == 4  # se juntaron varias: solo la última


def test_una_cena_en_el_restaurante(solo, reloj):
    inicio = reloj()
    solo.boton(ADMIN, "", "as:restaurante")  # 25 min
    (aviso,) = hasta(solo, reloj, 1, inicio)
    assert "🚗 Llegas a <b>" in aviso.texto and aviso.silencio and not aviso.botones
    assert "El mesero te recibe" in hasta(solo, reloj, 3, inicio)[0].texto
    assert hasta(solo, reloj, 3.5, inicio) == []  # nada nuevo todavía
    (carta,) = hasta(solo, reloj, 5, inicio)
    assert "Te presentan la carta" in carta.texto and "rplato:pasta" in datos(carta) and not carta.silencio
    res = solo.boton(ADMIN, "", "rplato:pasta")
    assert "Pediste 🍝 <b>pasta a la boloñesa</b>" in res.pantalla.texto
    assert solo.boton(ADMIN, "", "rplato:pizza").alerta == "Ya pediste pasta a la boloñesa."
    assert "preparan tu 🍝 pasta a la boloñesa" in hasta(solo, reloj, 8.5, inicio)[0].texto
    assert "¡Llega tu 🍝 pasta" in hasta(solo, reloj, 11.5, inicio)[0].texto
    (postre,) = hasta(solo, reloj, 20.6, inicio)
    assert "postre" in postre.texto and datos(postre) == ["rpostre:si", "rpostre:no"]
    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    antes = h.cuenta
    assert "¡Delicioso!" in solo.boton(ADMIN, "", "rpostre:si").pantalla.texto
    assert solo._hogar(h.sala_id).cuenta == antes - N.POSTRE
    assert solo.boton(ADMIN, "", "rpostre:no").alerta == "Eso ya está decidido."
    assert "Pides la cuenta" in hasta(solo, reloj, 24, inicio)[0].texto
    hasta(solo, reloj, 26, inicio)  # termina
    assert solo.boton(ADMIN, "", "rplato:pasta").alerta == "Ya no estás en el restaurante."


def test_si_no_eliges_te_recomiendan_lo_de_la_casa(solo, reloj):
    inicio = reloj()
    solo.boton(ADMIN, "", "as:restaurante")
    hasta(solo, reloj, 5, inicio)
    (aviso,) = hasta(solo, reloj, 8.5, inicio)
    assert "te recomendó lo de la casa" in aviso.texto and "🍖 cerdo asado con congrí" in aviso.texto


def test_en_cita_cada_uno_elige_su_plato(pareja, reloj):
    inicio = reloj()
    res = pareja.boton(ADMIN, "", "aj:restaurante")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ANA, "", si)  # cita: 25 min × 0,7 ≈ 18 min
    avisos = hasta(pareja, reloj, 1, inicio)
    assert {a.para for a in avisos} == {ADMIN, ANA} and all("Llegan juntos" in a.texto for a in avisos)
    assert avisos[0].texto == avisos[1].texto  # el mismo restaurante para los dos
    hasta(pareja, reloj, 3.5, inicio)
    pareja.boton(ADMIN, "", "rplato:pescado")
    pareja.boton(ANA, "", "rplato:pizza")
    avisos = {a.para: a.texto for a in hasta(pareja, reloj, 6, inicio)}
    assert "pescado" in avisos[ADMIN] and "pizza" in avisos[ANA] and "conversan" in avisos[ADMIN]


def test_otras_acciones_tambien_cuentan_lo_que_pasa(solo, reloj):
    from test_vida import dar_objetos

    dar_objetos(solo, ADMIN, "tv")
    inicio = reloj()
    solo.boton(ADMIN, "", "as:tele")  # 15 min
    assert "Enciendes la tele" in hasta(solo, reloj, 2, inicio)[0].texto
    assert "Anuncios" in hasta(solo, reloj, 8, inicio)[0].texto
    assert set(N.ETAPAS) <= set(V.ACCIONES)  # cada narración es de una acción que existe


def test_cocinando_explica_lo_que_hace(solo, reloj):
    import json

    from simpareja import cocina as C

    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    h.despensa = json.dumps({i: 10 for i in C.RECETAS["huevos"].ingredientes})
    solo.db.guardar_hogar(h)
    inicio = reloj()
    solo.boton(ADMIN, "", "coc:huevos:1")  # batir (1 min, sin mensajito) → cocinar (2 min) → tostar
    assert hasta(solo, reloj, 0.8, inicio) == []
    reloj.t = inicio + 60
    solo.boton(ADMIN, "", "coc:sig")
    (aviso,) = hasta(solo, reloj, 2.05, inicio)
    assert "chisporrotean" in aviso.texto and aviso.silencio
    assert hasta(solo, reloj, 2.5, inicio) == []  # una sola vez por paso


def test_se_pueden_apagar(solo, reloj):
    from test_vida import dar_objetos

    assert "Mensajitos de lo que va pasando en cada acción: <b>Sí</b>" in solo.boton(ADMIN, "", "ajustes").pantalla.texto
    assert "<b>No</b>" in solo.boton(ADMIN, "", "narr").pantalla.texto.split("Mensajitos")[1]
    dar_objetos(solo, ADMIN, "tv")
    inicio = reloj()
    solo.boton(ADMIN, "", "as:tele")
    assert hasta(solo, reloj, 8, inicio) == []
