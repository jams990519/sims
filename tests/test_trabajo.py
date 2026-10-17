"""Parte 6: trabajos y días de la semana."""

import json
import random

import pytest

from simpareja import trabajo as T
from test_juego import ADMIN, crear_personaje
from test_vida import ir_al_dia, nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def juego(reloj):
    j = nuevo_juego(reloj)
    j.inicio(ADMIN, "Admin")
    crear_personaje(j, ADMIN, "Luis")
    return j


def ser(juego, genero):
    jug = juego.db.jugador(ADMIN)
    ap = jug.ap
    ap["genero"] = genero
    jug.apariencia = json.dumps(ap)
    juego.db.guardar_jugador(jug)


def ser_mujer(juego):
    ser(juego, "mujer")


def empleo(juego):
    return json.loads(juego.db.jugador(ADMIN).trabajo)


def turno(juego, reloj, horas=8):
    res = juego.boton(ADMIN, "", f"trabajar:{horas}")
    reloj.avanzar(horas * 60 + 1)
    return res, juego.tick()


def test_lista_de_trabajos(juego):
    ser(juego, "hombre")
    res = juego.boton(ADMIN, "", "trabajo")
    texto = str(res.pantalla.botones)
    assert len([d for fila in res.pantalla.botones for _, d in fila if d.startswith("vtrab:")]) == 7
    for t in ("Manicurista · $10/h", "Asistente de estudio · $11/h", "$10/h", "Repartidor", "Ayudante de cocina",
              "Recepcionista · $11/h", "$12/h"):
        assert t in texto


def test_ver_y_aceptar_un_trabajo(juego):
    ser_mujer(juego)
    texto = juego.boton(ADMIN, "", "vtrab:foto").pantalla.texto
    assert "Nivel 2: Fotógrafa · $16/h" in texto and "Nivel 3: Directora del estudio · $24/h" in texto
    assert "De lunes a viernes" in texto
    res = juego.boton(ADMIN, "", "tomar:foto")
    assert "¡Tienes trabajo!" in res.pantalla.texto
    assert empleo(juego)["libres"] == [5, 6]
    assert "📸 Asistente de estudio · $11/h" in juego.boton(ADMIN, "", "sim").pantalla.texto


def test_un_turno_de_8_horas(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    res = juego.boton(ADMIN, "", "trabajo")
    assert "trabajar:8" in str(res.pantalla.botones) and "8 h · $88" in str(res.pantalla.botones)
    res = juego.boton(ADMIN, "", "trabajar:8")
    assert "Sales a las 16:00" in res.pantalla.texto
    assert "💼 trabajando hasta las 16:00" in juego.boton(ADMIN, "", "sala").pantalla.texto
    reloj.avanzar(8 * 60 + 1)
    avisos = juego.tick().avisos
    assert any(a.para == ADMIN and "Cobró $88" in a.texto for a in avisos)
    j = juego.db.jugador(ADMIN)
    assert j.cartera == 88
    assert juego._hogar(j.sala_id).cuenta == 1500 - 4  # transporte
    assert nec(juego, ADMIN)["energia"] == pytest.approx(100 - 64, abs=0.5)
    assert empleo(juego)["dias"] == 1


def test_un_turno_por_dia_y_dias_libres(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    turno(juego, reloj)
    assert "Hoy (Lunes) ya trabajaste" in juego.boton(ADMIN, "", "trabajo").pantalla.texto
    assert juego.boton(ADMIN, "", "trabajar:8").alerta == "Hoy ya trabajaste."
    ir_al_dia(juego, reloj, ADMIN, 6)
    assert "Hoy (Sábado) es tu día libre" in juego.boton(ADMIN, "", "trabajo").pantalla.texto
    assert juego.boton(ADMIN, "", "trabajar:8").alerta == "Hoy es tu día libre."


def test_rotativo_libra_dos_dias_seguidos_entre_semana():
    for semilla in range(20):
        libres = T.dias_libres(T.ROTATIVO, random.Random(semilla))
        assert libres[1] == libres[0] + 1 and libres[1] <= 4
    assert T.trabaja_hoy([1, 2], 6) and T.trabaja_hoy([1, 2], 7)  # trabaja sábado y domingo
    assert not T.trabaja_hoy([1, 2], 2)


def test_con_mal_humor_no_se_trabaja(juego):
    juego.boton(ADMIN, "", "tomar:taller")
    poner(juego, ADMIN, social=0)
    assert "mal humor" in juego.boton(ADMIN, "", "trabajar:8").alerta


def test_ascenso_tras_5_dias_sin_rojos(juego, reloj):
    ser_mujer(juego)
    juego.boton(ADMIN, "", "tomar:recepcion")
    avisos = []
    for dia in range(1, 6):
        ir_al_dia(juego, reloj, ADMIN, dia)
        poner(juego, ADMIN, **LLENO)
        _, res = turno(juego, reloj)
        avisos += res.avisos
    assert any("¡Ascenso!</b> Ahora es administrativa ($16/h)" in a.texto for a in avisos)
    e = empleo(juego)
    assert e["nivel"] == 2 and e["dias"] == 0


def test_con_necesidades_en_rojo_el_dia_no_cuenta(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    poner(juego, ADMIN, hambre=20)
    res, _ = turno(juego, reloj)
    assert "no contará para el ascenso" in res.pantalla.texto
    assert empleo(juego)["dias"] == 0
    assert juego.db.jugador(ADMIN).cartera == 88  # pero cobra igual


def test_parar_a_mitad_cobra_las_horas_hechas(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    juego.boton(ADMIN, "", "trabajar:8")
    reloj.avanzar(3 * 60)
    res = juego.boton(ADMIN, "", "parar")
    assert "Cobró $33" in res.pantalla.texto and "turno incompleto" in res.pantalla.texto
    assert empleo(juego)["dias"] == 0


def test_sin_energia_se_duerme_en_el_trabajo(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    poner(juego, ADMIN, energia=20)
    juego.boton(ADMIN, "", "trabajar:8")
    avisos = []
    for _ in range(3 * 60):  # el bot revisa cada minuto
        reloj.avanzar(1)
        avisos += juego.tick().avisos
        if any("Dejó de trabajar" in a.texto for a in avisos):
            break
    assert any("necesita atención" in a.texto for a in avisos)  # antes avisó de la energía baja
    assert any("Dejó de trabajar a mitad del turno" in a.texto for a in avisos)
    assert json.loads(juego.db.jugador(ADMIN).accion)["k"] == "dormir"
    assert juego.db.jugador(ADMIN).cartera == round(11 * 19 / 8)  # cae al bajar de 1: (20 − 1) ÷ 8 h


def test_renunciar_y_empezar_de_cero(juego):
    juego.boton(ADMIN, "", "tomar:taller")
    j = juego.db.jugador(ADMIN)
    j.trabajo = json.dumps({**empleo(juego), "nivel": 3})
    juego.db.guardar_jugador(j)
    assert "renunciar:si" in str(juego.boton(ADMIN, "", "renunciar").pantalla.botones)
    res = juego.boton(ADMIN, "", "renunciar:si")
    assert "Renunciaste" in res.pantalla.texto and empleo(juego) == {}
    juego.boton(ADMIN, "", "tomar:taller")
    assert empleo(juego)["nivel"] == 1
