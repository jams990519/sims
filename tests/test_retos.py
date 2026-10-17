"""Actualización 2, parte 11: retos semanales de pareja."""

import json

import pytest

from simpareja import retos_juego as R
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, poner, Reloj


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


def poner_reto(juego, clave, premio="dinero", valor=150):
    h = hogar(juego)
    ex = json.loads(h.extras)
    ex["reto"] = {"semana": juego._lunes(juego.db.jugador(ADMIN)), "clave": clave, "meta": R.RETOS[clave][1],
                  "progreso": 0, "premio": premio, "valor": valor, "hecho": False, "contados": []}
    h.extras = json.dumps(ex)
    juego.db.guardar_hogar(h)


def reto(juego):
    return json.loads(hogar(juego).extras)["reto"]


def juntos(juego, reloj, clave, minutos):
    for uid in (ADMIN, ANA):
        juego.boton(uid, "", "continuar")  # por si se pausaron mientras tanto
    res = juego.boton(ANA, "", f"aj:{clave}")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    juego.boton(ADMIN, "", si)
    reloj.avanzar(minutos)
    return juego.tick()


def test_un_reto_cada_semana(pareja, reloj):
    avisos = [a for a in pareja.tick().avisos if "Reto de la semana" in a.texto]
    assert {a.para for a in avisos} == {ADMIN, ANA}
    primero = reto(pareja)
    assert primero["semana"] == pareja._lunes(pareja.db.jugador(ADMIN))
    assert not [a for a in pareja.tick().avisos if "Reto de la semana" in a.texto]
    ir_al_dia(pareja, reloj, ADMIN, 8)  # el lunes siguiente
    assert any("Reto de la semana" in a.texto for a in pareja.tick().avisos)
    assert reto(pareja)["clave"] != primero["clave"] and reto(pareja)["semana"] == primero["semana"] + 7
    assert "retos" in str(pareja.boton(ADMIN, "", "mpar").pantalla.botones)


def test_abrazos_con_premio_en_dinero(pareja, reloj):
    poner_reto(pareja, "abrazos")
    for _ in range(5):
        poner(pareja, ADMIN, social=10)
        poner(pareja, ANA, social=10)
        ultimo = juntos(pareja, reloj, "abrazar", 30)
    pareja.boton(ADMIN, "", "continuar")
    texto = pareja.boton(ADMIN, "", "retos").pantalla.texto
    assert "🤗 Darse 5 abrazos" in texto and "5/5" in texto
    assert any("¡Reto cumplido!" in a.texto for a in ultimo.avisos)
    assert reto(pareja)["hecho"] and hogar(pareja).cuenta == 2100 + 150
    assert "Retos cumplidos: 1" in pareja.boton(ADMIN, "", "retos").pantalla.texto


def test_cita_el_fin_de_semana_con_premio_en_relacion(pareja, reloj):
    poner_reto(pareja, "cita_finde", "relacion", 5)
    juntos(pareja, reloj, "cine", 3 * 60)  # lunes: no cuenta
    assert reto(pareja)["progreso"] == 0
    ir_al_dia(pareja, reloj, ADMIN, 6)  # sábado
    pareja.tick()
    juntos(pareja, reloj, "cine", 3 * 60)
    pareja.tick()
    assert reto(pareja)["hecho"]
    assert pareja._relacion(pareja.db.jugador(ADMIN)) == 55 and pareja._relacion(pareja.db.jugador(ANA)) == 55


def test_preguntas_respondidas_por_los_dos(pareja):
    poner_reto(pareja, "preguntas")
    for _ in range(2):
        pareja.boton(ADMIN, "", "pregn")
        for uid in (ADMIN, ANA):
            pareja.boton(uid, "", "pregr")
            pareja.texto(uid, "", "respuesta")
    assert reto(pareja)["progreso"] == 2


def test_cocinar_juntos_cuenta(pareja, reloj):
    from simpareja import cocina as C
    poner_reto(pareja, "cocinar")
    h = hogar(pareja)
    h.despensa = json.dumps({"pan": 4, "jamon": 2, "queso": 2})
    pareja.db.guardar_hogar(h)
    res = pareja.boton(ADMIN, "", "aj:cocinar:sandwich:2")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ANA, "", si)
    for _, minutos in C.RECETAS["sandwich"].pasos:
        reloj.avanzar(C.minutos_paso(minutos, True))
        pareja.boton(ADMIN, "", "coc:sig")
    assert reto(pareja)["progreso"] == 1


def test_sin_pareja(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "para jugar en pareja" in juego.boton(ADMIN, "", "retos").alerta
    assert not [a for a in juego.tick().avisos if "Reto" in a.texto]
