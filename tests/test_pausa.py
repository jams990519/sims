"""Pausa de la pareja: ⏸️ Pausar / ▶️ Reanudar congela el juego de los dos y al volver sigue donde quedó."""

import json

import pytest

from simpareja import cocina as C
from simpareja import vida as V
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nec, nuevo_juego, poner, Reloj


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


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def silencio(juego, horas):
    """Pasan horas (con el tick de cada minuto, de hora en hora): devuelve todo lo que se avisó."""
    avisos = []
    for _ in range(horas):
        juego.reloj.avanzar(60)
        avisos += juego.tick().avisos
    return avisos


def test_en_pausa_nada_avanza_y_al_reanudar_sigue_donde_quedo(pareja, reloj):
    poner(pareja, ADMIN, energia=10, hambre=80)
    pareja.boton(ADMIN, "", "as:dormir:max")  # 8 h: normalmente corre aunque Luis se vaya
    reloj.avanzar(60)
    pareja.tick()
    antes = nec(pareja, ADMIN)
    pareja.boton(ANA, "", "continuar")  # Ana vuelve a jugar
    assert "pausar" in datos(pareja.boton(ANA, "", "menu").pantalla)  # el botón está en el menú
    res = pareja.boton(ANA, "", "pausar")  # cualquiera de los dos pausa
    assert "El juego está en pausa" in res.pantalla.texto and datos(res.pantalla)[0] == "pausar"
    assert any(a.para == ADMIN and "Juego en pausa" in a.texto for a in res.avisos)
    rfin = json.loads(pareja.db.jugador(ADMIN).accion)["rfin"]
    assert silencio(pareja, 12) == []  # 12 h en pausa: ni un aviso
    assert nec(pareja, ADMIN) == antes  # nada bajó ni subió
    res = pareja.boton(ADMIN, "", "pausar")  # y cualquiera reanuda
    assert "Juego reanudado" in res.pantalla.texto and res.pantalla.clave == "menu"
    assert any(a.para == ANA and "Juego reanudado" in a.texto for a in res.avisos)
    assert nec(pareja, ADMIN) == antes  # sin saltos
    assert json.loads(pareja.db.jugador(ADMIN).accion)["rfin"] == rfin + 12 * 3600  # duerme lo que le faltaba
    reloj.avanzar(7 * 60 + 1)
    assert any(a.para == ADMIN and "terminó" in a.texto for a in pareja.tick().avisos)
    n = nec(pareja, ADMIN)
    assert n["energia"] == 100 and n["hambre"] == pytest.approx(80 - 6 * 8, abs=0.5)  # 8 h de sueño, no 20


def test_en_pausa_no_hay_avisos_de_necesidades(pareja, reloj):
    pareja.boton(ADMIN, "", "sim")
    pareja.boton(ADMIN, "", "pausar")
    poner(pareja, ADMIN, hambre=5, higiene=5)
    assert not [a for a in silencio(pareja, 3) if "necesita atención" in a.texto]
    pareja.boton(ADMIN, "", "pausar")
    assert any(a.para == ADMIN and "necesita atención" in a.texto for a in pareja.tick().avisos)


def test_en_pausa_solo_se_reanuda_se_chatea_y_se_miran_los_ajustes(pareja, reloj):
    pareja.boton(ADMIN, "", "pausar")
    for boton in ("macc", "menu", "sim", "a:ducha", "continuar"):
        assert pareja.boton(ANA, "", boton).pantalla.clave == "pausa"
    assert pareja.inicio(ANA, "Ana").pantalla.clave == "pausa"  # /start también
    assert pareja.boton(ANA, "", "sala").pantalla.clave != "pausa"  # el chat sigue
    res = pareja.texto(ANA, "Ana", "te extraño 💞")
    assert any(a.para == ADMIN and a.chat for a in res.avisos)
    assert "ajustes" in pareja.boton(ANA, "", "ajustes").pantalla.clave
    res = pareja.boton(ANA, "", "pausar")
    assert res.pantalla.clave == "menu"
    assert pareja.boton(ANA, "", "macc").pantalla.clave != "pausa"


def test_la_cocina_y_las_facturas_esperan(pareja, reloj):
    h = pareja._hogar(pareja.db.jugador(ADMIN).sala_id)
    h.despensa = json.dumps({i: 10 for i in C.RECETAS["huevos"].ingredientes})
    h.proximo_cobro = h.dia_hogar + 1  # las facturas tocaban mañana
    pareja.db.guardar_hogar(h)
    pareja.boton(ADMIN, "", "coc:huevos:1")
    paso_ini = json.loads(pareja._hogar(h.sala_id).cocina)["paso_ini"]
    pareja.boton(ADMIN, "", "pausar")
    avisos = silencio(pareja, 3 * 24)  # tres días en pausa
    assert not [a for a in avisos if "quemó" in a.texto or "facturas" in a.texto]
    pareja.boton(ADMIN, "", "pausar")
    h = pareja._hogar(h.sala_id)
    assert json.loads(h.cocina)["paso_ini"] == paso_ini + 3 * 24 * 3600  # el paso sigue donde iba
    assert h.proximo_cobro == h.dia_hogar + 1  # las facturas, todavía mañana
    assert not [a for a in pareja.tick().avisos if "quemó" in a.texto or "facturas" in a.texto]
    assert V.DIA == 86400
