"""Diseño v1, parte 10: estudios (cursos, certificados y carrera)."""

import json

import pytest

from simpareja import estudios_juego as S
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


def estudio(juego, uid=ADMIN):
    return juego._extras(juego.db.jugador(uid)).get("estudio")


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def sesion(juego, reloj, uid, horas=1):
    poner(juego, uid, **LLENO)
    res = juego.boton(uid, "", f"as:estudiar:{horas}")
    reloj.avanzar(horas * 60 + 1)
    juego.tick()
    return res


def casi_terminado(juego, uid, clave):
    j = juego.db.jugador(uid)
    extras = juego._extras(j)
    extras["estudio"] = {"clave": clave, "sesiones": S.ESTUDIOS[clave].sesiones - 1, "ultimo": None,
                         "pagado_hasta": juego._hoy(j) + 30}
    j.extras = json.dumps(extras)
    juego.db.guardar_jugador(j)


def test_inscribirse_y_estudiar_una_vez_al_dia(pareja, reloj):
    assert "estudios" in datos(pareja.boton(ADMIN, "", "macc").pantalla)
    res = pareja.boton(ADMIN, "", "estudios")
    assert "Cursos cortos online" in res.pantalla.texto and "estin:carrera" in datos(res.pantalla)
    assert "inscríbete" in pareja.boton(ADMIN, "", "as:estudiar:1").alerta
    res = pareja.boton(ADMIN, "", "estin:ofimatica")
    assert "¡Te inscribiste en curso de ofimática!" in res.pantalla.texto and hogar(pareja).cuenta == 2100 - 80
    assert "a:estudiar:1" in datos(res.pantalla)
    sesion(pareja, reloj, ADMIN)
    assert estudio(pareja)["sesiones"] == 1
    assert "Hoy ya estudiaste" in pareja.boton(ADMIN, "", "as:estudiar:1").alerta


def test_un_curso_acelera_el_ascenso(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    pareja.boton(ADMIN, "", "estin:ingles")
    casi_terminado(pareja, ADMIN, "ingles")
    sesion(pareja, reloj, ADMIN)
    j = pareja.db.jugador(ADMIN)
    assert json.loads(j.trabajo)["dias"] == 2
    assert "ingles" in pareja._extras(j)["estudios_hechos"] and estudio(pareja) is None


def test_certificado_entra_en_el_nivel_2(pareja, reloj):
    pareja.boton(ADMIN, "", "estin:cert_foto")
    casi_terminado(pareja, ADMIN, "cert_foto")
    sesion(pareja, reloj, ADMIN, 2)
    assert "foto" in pareja._extras(pareja.db.jugador(ADMIN))["certificados"]
    pareja.boton(ADMIN, "", "continuar")
    res = pareja.boton(ADMIN, "", "tomar:foto")
    assert "entras en el nivel 2" in res.pantalla.texto
    assert json.loads(pareja.db.jugador(ADMIN).trabajo)["nivel"] == 2


def test_la_carrera_se_paga_cada_mes_y_abre_el_mejor_puesto(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:taller")
    pareja.boton(ADMIN, "", "estin:carrera")
    assert hogar(pareja).cuenta == 2100 - 300
    ir_al_dia(pareja, reloj, ADMIN, 31)
    avisos = [a for a in pareja.tick().avisos if "mensualidad de la carrera" in a.texto]
    assert avisos and estudio(pareja)["pagado_hasta"] == pareja._hoy(pareja.db.jugador(ADMIN)) + 30
    h = hogar(pareja)
    h.cuenta = 0
    pareja.db.guardar_hogar(h)
    ir_al_dia(pareja, reloj, ADMIN, 61)
    assert any("las clases se pausan" in a.texto for a in pareja.tick().avisos)
    assert "Deben la mensualidad" in pareja.boton(ADMIN, "", "as:estudiar:2").alerta
    h = hogar(pareja)
    h.cuenta = 500
    pareja.db.guardar_hogar(h)
    assert "Mensualidad pagada" in pareja.boton(ADMIN, "", "estpagar").pantalla.texto
    casi_terminado(pareja, ADMIN, "carrera")
    sesion(pareja, reloj, ADMIN, 2)
    j = pareja.db.jugador(ADMIN)
    assert pareja._extras(j)["titulo"] and json.loads(j.trabajo)["nivel"] == 3


def test_estudiar_juntos_es_mas_rapido_y_sube_la_relacion(pareja, reloj):
    pareja.boton(ADMIN, "", "estin:ofimatica")
    pareja.boton(ANA, "", "estin:atencion")
    for uid in (ADMIN, ANA):
        poner(pareja, uid, **LLENO)
    res = pareja.boton(ADMIN, "", "aj:estudiar:1")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ANA, "", si)
    reloj.avanzar(43)  # 60 min × 0,7
    pareja.tick()
    assert estudio(pareja)["sesiones"] == 1 and estudio(pareja, ANA)["sesiones"] == 1
    for uid in (ADMIN, ANA):
        assert any("Estudiamos juntos" in c["m"] for c in pareja._extras(pareja.db.jugador(uid))["relacion_hist"])
