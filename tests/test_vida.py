"""Parte 4: necesidades y acciones básicas."""

import json
import random

import pytest

from simpareja import vida as V
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Juego
from test_juego import ADMIN, ANA, INICIO, Reloj, aceptar, crear_personaje, invitar  # noqa: F401


@pytest.fixture
def reloj():
    return Reloj()


def nuevo_juego(reloj, eventos=False):
    cfg = Config(token="x", admins=frozenset({ADMIN}), eventos=eventos)
    return Juego(DB(":memory:"), cfg, reloj=reloj, rng=random.Random(5))


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


def nec(juego, uid):
    return json.loads(juego.db.jugador(uid).necesidades)


def poner(juego, uid, **valores):
    j = juego.db.jugador(uid)
    n = json.loads(j.necesidades)
    n.update(valores)
    j.necesidades = json.dumps(n)
    juego.db.guardar_jugador(j)


def jugar(juego, reloj, uid, minutos):
    """Simula a alguien que sigue tocando botones (su Sim no se congela)."""
    for _ in range(minutos // 4):
        reloj.avanzar(4)
        juego.boton(uid, "", "sim")
    reloj.avanzar(minutos % 4)
    juego.boton(uid, "", "sim")


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


# --- necesidades -------------------------------------------------------------------

def test_mi_sim_muestra_las_necesidades(solo):
    texto = solo.boton(ADMIN, "", "sim").pantalla.texto
    for nombre in ("Hambre", "Energía", "Higiene", "Diversión", "Social"):
        assert nombre in texto
    assert "🟩" in texto and "Lunes 08:00 · día 1" in texto


def test_las_necesidades_bajan_con_el_reloj_del_sim(solo, reloj):
    jugar(solo, reloj, ADMIN, 60)
    n = nec(solo, ADMIN)
    assert n["hambre"] == pytest.approx(80 - 6, abs=0.1)
    assert n["higiene"] == pytest.approx(80 - 4, abs=0.1)
    assert n["diversion"] == pytest.approx(70 - 5, abs=0.1)
    assert n["social"] == pytest.approx(60 - 3, abs=0.1)
    assert n["energia"] == pytest.approx(90 - 3, abs=0.1)


def test_en_pausa_no_bajan(solo, reloj):
    solo.boton(ADMIN, "", "sim")
    reloj.avanzar(5 * 60)  # 5 horas fuera: solo corrieron los 5 minutos antes de congelarse
    solo.boton(ADMIN, "", "continuar")
    assert nec(solo, ADMIN)["hambre"] == pytest.approx(80 - 0.5, abs=0.05)


def test_comer_segun_la_hora(solo, reloj):
    poner(solo, ADMIN, hambre=20)
    res = solo.boton(ADMIN, "", "acc:comer")
    assert "desayunar, +30" in str(res.pantalla.botones)
    res = solo.boton(ADMIN, "", "a:domicilio")
    assert "+30 🍔 hambre · ⏱️ 10 min · 💵 $6" in res.pantalla.texto and "¿Confirmar?" in res.pantalla.texto
    res = solo.boton(ADMIN, "", "as:domicilio")
    assert "Empezó" in res.pantalla.texto and "termina a las 08:10" in res.pantalla.texto
    reloj.avanzar(10)
    solo.boton(ADMIN, "", "sim")
    assert nec(solo, ADMIN)["hambre"] == pytest.approx(20 + 30 - 1, abs=0.2)


def test_no_deja_hacer_lo_que_no_hace_falta(solo):
    res = solo.boton(ADMIN, "", "a:domicilio")  # hambre 80, aún puede comer
    assert res.alerta is None
    poner(solo, ADMIN, higiene=99)
    res = solo.boton(ADMIN, "", "a:ducha")
    assert "no lo necesita" in res.alerta


def test_mientras_hace_algo_no_puede_hacer_otra_cosa(solo):
    poner(solo, ADMIN, hambre=20)
    solo.boton(ADMIN, "", "as:domicilio")
    res = solo.boton(ADMIN, "", "a:tele")
    assert "esperando el pedido" in res.alerta
    assert "parar" in datos(res.pantalla)


def test_parar_deja_el_efecto_parcial(solo, reloj):
    poner(solo, ADMIN, hambre=20)
    solo.boton(ADMIN, "", "as:domicilio")
    reloj.avanzar(5)
    res = solo.boton(ADMIN, "", "parar")
    assert "Paró" in res.pantalla.texto
    assert nec(solo, ADMIN)["hambre"] == pytest.approx(20 + 15 - 0.5, abs=0.2)
    assert solo.db.jugador(ADMIN).accion is None


def test_dormir_8_horas_no_congela_al_sim(solo, reloj):
    poner(solo, ADMIN, energia=10)
    res = solo.boton(ADMIN, "", "a:dormir")
    assert datos(res.pantalla)[:2] == ["a:dormir:max", "a:dormir:6"]
    assert "Hasta recuperarse (8 h)" in str(res.pantalla.botones)
    solo.boton(ADMIN, "", "as:dormir:max")
    reloj.avanzar(8 * 60 + 1)  # el jugador se fue a dormir de verdad
    res = solo.tick()
    assert any(a.para == ADMIN and "terminó" in a.texto and "Dormir" in a.texto for a in res.avisos)
    n = nec(solo, ADMIN)
    assert n["energia"] == 100  # 10 + 8 h × 12, con tope en 100
    assert n["hambre"] == pytest.approx(80 - 6 * 8, abs=0.5)  # durmiendo también le da hambre
    texto = solo.boton(ADMIN, "", "sim").pantalla.texto
    assert "Lunes 16:01 · día 1" in texto and "Sin hacer nada" in texto


def test_sin_energia_se_duerme_donde_esta(solo, reloj):
    poner(solo, ADMIN, energia=1)
    jugar(solo, reloj, ADMIN, 30)
    j = solo.db.jugador(ADMIN)
    assert json.loads(j.accion)["k"] == "dormir"
    assert "se durmió donde estaba" in solo.boton(ADMIN, "", "sim").pantalla.texto or j.accion


def test_mal_humor_con_una_necesidad_en_cero(solo):
    poner(solo, ADMIN, social=0)
    assert "De mal humor" in solo.boton(ADMIN, "", "sim").pantalla.texto


def dar_objetos(juego, uid, *claves):
    """Les compra objetos de la casa sin pasar por la tienda (por ejemplo, la tele)."""
    h = juego._hogar(juego.db.jugador(uid).sala_id)
    ex = json.loads(h.extras)
    ex["objetos"] = sorted(set(ex.get("objetos", [])) | set(claves))
    h.extras = json.dumps(ex)
    juego.db.guardar_hogar(h)


def ir_al_dia(juego, reloj, uid, dia):
    """Adelanta la hora real hasta las 08:00 del día indicado, sin que el Sim gaste necesidades."""
    reloj.t = max(reloj.t, INICIO + (dia - 1) * 86400)
    for j in juego.db.jugadores_en_sala():
        juego._congelar(j, reloj())
        j.reloj_desde = j.ultima_jugada = j.ultima_actividad = reloj()
        if j.id == uid:
            j.accion = None
        juego.db.guardar_jugador(j)


def test_constancia_sube_la_energia_maxima(solo, reloj):
    for dia in (1, 2, 3):
        ir_al_dia(solo, reloj, ADMIN, dia)
        solo.boton(ADMIN, "", "as:parque")
        reloj.avanzar(16)
        res = solo.boton(ADMIN, "", "sim")
    assert "¡Constancia! 3 días seguidos" in res.pantalla.texto
    assert solo.db.jugador(ADMIN).energia_max == 105
    assert "/105" in res.pantalla.texto


def test_registrar_ejercicio():
    racha, emax, subio = V.registrar_ejercicio({}, 1, 100)
    racha, emax, subio = V.registrar_ejercicio(racha, 2, emax)
    assert not subio
    racha, emax, subio = V.registrar_ejercicio(racha, 3, emax)
    assert subio and emax == 105
    racha, emax, subio = V.registrar_ejercicio(racha, 5, emax)  # se saltó un día
    assert racha["dias"] == 1 and emax == 105
    assert V.registrar_ejercicio({"ultimo": 9, "dias": 2}, 10, 130)[1] == 130


def test_calendario_con_fin_de_semana(solo, reloj):
    ir_al_dia(solo, reloj, ADMIN, 6)
    assert solo._reloj(solo.db.jugador(ADMIN)) == "Sábado 08:00 · día 6"
    assert V.es_fin_de_semana(5) and V.es_fin_de_semana(6) and not V.es_fin_de_semana(7)


# --- casa: limpiar y lavar ---------------------------------------------------------------

def test_limpiar_una_zona_y_lavar_la_ropa(solo, reloj):
    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    h.zonas = json.dumps({"salon": 90, "cuarto": 0, "bano": 50, "closet": 0})
    h.ropa_sucia = 25
    solo.db.guardar_hogar(h)
    texto = solo.boton(ADMIN, "", "acc:limpieza").pantalla.texto
    assert "🪳 sucio" in texto and "¡no queda limpia!" in texto
    assert "No queda ropa limpia" in solo.boton(ADMIN, "", "sim").pantalla.texto
    res = solo.boton(ADMIN, "", "a:limpiar")
    assert "a:limpiar:salon" in datos(res.pantalla)
    solo.boton(ADMIN, "", "as:limpiar:salon")
    reloj.avanzar(11)
    res = solo.boton(ADMIN, "", "sim")
    assert "quedó reluciente" in res.pantalla.texto
    solo.boton(ADMIN, "", "as:lavar")
    reloj.avanzar(16)
    solo.boton(ADMIN, "", "sim")
    h = solo._hogar(h.sala_id)
    assert json.loads(h.zonas)["salon"] == 0 and h.ropa_sucia == 0


def test_ducharse_ensucia_el_bano_y_deja_ropa(solo):
    poner(solo, ADMIN, higiene=10)
    solo.boton(ADMIN, "", "as:ducha")
    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    assert json.loads(h.zonas)["bano"] == 8 and h.ropa_sucia == 2


# --- juntos ------------------------------------------------------------------------------

def test_sin_pareja_no_hay_abrazos(solo):
    texto = str(solo.boton(ADMIN, "", "acc:pareja").pantalla.botones)
    assert "a:abrazar" not in texto
    assert "Con tu pareja en la sala también podrán" in solo.boton(ADMIN, "", "acc:pareja").pantalla.texto
    assert "Llamar a un amigo o a la familia" in str(solo.boton(ADMIN, "", "acc:diversion").pantalla.botones)
    res = solo.boton(ADMIN, "", "a:abrazar")
    assert res.alerta == "Para esto necesitas a tu pareja en la sala."


def test_hacer_algo_juntos_es_mas_rapido(pareja, reloj):
    poner(pareja, ANA, higiene=20)
    poner(pareja, ADMIN, higiene=20)
    res = pareja.boton(ANA, "", "a:banarse")
    assert "¿Confirmar?" in res.pantalla.texto and "aj:banarse" in datos(res.pantalla)
    res = pareja.boton(ANA, "", "aj:banarse")
    assert "Le propusiste" in res.pantalla.texto
    propuesta = next(a for a in res.avisos if a.para == ADMIN)
    assert "te propone" in propuesta.texto and "7 min" in propuesta.texto
    si = next(d for fila in propuesta.botones for _, d in fila if d.endswith(":1"))
    res = pareja.boton(ADMIN, "", si)
    assert "Empiezan juntos" in res.pantalla.texto
    assert any(a.para == ANA and "aceptó" in a.texto for a in res.avisos)
    for uid in (ADMIN, ANA):
        accion = json.loads(pareja.db.jugador(uid).accion)
        assert accion["k"] == "banarse" and accion["fin"] - accion["ini"] == 7 * 60  # 10 min × 0,7
    assert "bañándose con Ana" in pareja.boton(ADMIN, "", "sala").pantalla.texto
    reloj.avanzar(8)
    pareja.boton(ADMIN, "", "sim")
    assert nec(pareja, ADMIN)["higiene"] == pytest.approx(20 + 80 - 4 * 8 / 60, abs=0.5)


def test_accion_opcional_pregunta_solo_o_juntos(pareja):
    dar_objetos(pareja, ANA, "tv")
    res = pareja.boton(ANA, "", "a:tele")
    assert datos(res.pantalla)[:2] == ["as:tele", "aj:tele"]
    res = pareja.boton(ANA, "", "as:tele")
    assert "Empezó" in res.pantalla.texto


def test_rechazar_y_aceptar_tarde(pareja, reloj):
    res = pareja.boton(ANA, "", "aj:abrazar")
    propuesta = next(a for a in res.avisos if a.para == ADMIN)
    no = next(d for fila in propuesta.botones for _, d in fila if d.endswith(":0"))
    res = pareja.boton(ADMIN, "", no)
    assert any(a.para == ANA and "dijo que ahora no" in a.texto for a in res.avisos)
    res = pareja.boton(ANA, "", "aj:besar")
    propuesta = next(a for a in res.avisos if a.para == ADMIN)
    si = next(d for fila in propuesta.botones for _, d in fila if d.endswith(":1"))
    reloj.avanzar(20)
    assert pareja.boton(ADMIN, "", si).alerta == "Esa propuesta ya no está disponible."


def test_se_puede_aceptar_con_el_sim_en_pausa(pareja, reloj):
    reloj.avanzar(10)  # los dos congelados
    pareja.boton(ANA, "", "continuar")
    res = pareja.boton(ANA, "", "aj:abrazar")
    propuesta = next(a for a in res.avisos if a.para == ADMIN)
    si = next(d for fila in propuesta.botones for _, d in fila if d.endswith(":1"))
    res = pareja.boton(ADMIN, "", si)
    assert "Empiezan juntos" in res.pantalla.texto


def test_la_pareja_fuera_de_linea_no_recibe_propuestas(pareja, reloj):
    pareja.boton(ADMIN, "", "salir")
    res = pareja.boton(ANA, "", "aj:abrazar")
    assert "no está en línea" in res.alerta
