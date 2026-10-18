"""Momento íntimo: minijuego de pareja con opciones, solo si los dos quieren y sin nada explícito."""

import json

import pytest

from simpareja import intimo_juego as I
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=50, social=50)


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
    for uid in (ADMIN, ANA):
        poner(solo, uid, **LLENO)
    return solo


def datos(pantalla_o_aviso):
    return [d for fila in pantalla_o_aviso.botones for _, d in fila]


def hist(juego, uid):
    return [c for c in juego._extras(juego.db.jugador(uid)).get("relacion_hist", []) if "a solas" in c["m"]]


def proponer(juego, lugar="cuarto", ambiente="romantico"):
    res = juego.boton(ADMIN, "", f"intp:{lugar}:{ambiente}")
    return next(a for a in res.avisos if a.para == ANA)


def test_un_momento_de_principio_a_fin(pareja):
    assert "intimo" in datos(pareja.boton(ADMIN, "", "mpar").pantalla)
    res = pareja.boton(ADMIN, "", "intimo")
    assert "solo si los dos quieren" in res.pantalla.texto
    assert {"intl:cuarto", "intl:bano", "intl:salon"} <= set(datos(res.pantalla))
    assert "intp:cuarto:romantico" in datos(pareja.boton(ADMIN, "", "intl:cuarto").pantalla)
    aviso = proponer(pareja)
    assert "momento a solas" in aviso.texto and datos(aviso) == ["intsi", "intno"]
    res = pareja.boton(ANA, "", "intsi")
    assert "Ronda 1 de 3" in res.pantalla.texto and "into:velas" in datos(res.pantalla)
    assert any(a.para == ADMIN and "dijo que sí" in a.texto for a in res.avisos)
    assert pareja.db.jugador(ADMIN).lugar == pareja.db.jugador(ANA).lugar == "cuarto"

    res = pareja.boton(ADMIN, "", "into:velas")
    assert "Esperando a" in res.pantalla.texto and not res.avisos  # Ana no ve lo que eligió Luis
    res = pareja.boton(ANA, "", "into:velas")
    assert "justo el ambiente que buscaban" in res.pantalla.texto and "Ronda 2 de 3" in res.pantalla.texto
    assert any(a.para == ADMIN and "Ronda 2 de 3" in a.texto for a in res.avisos)
    pareja.boton(ADMIN, "", "into:abrazo")
    assert "se complementan" in pareja.boton(ANA, "", "into:risas").pantalla.texto
    pareja.boton(ANA, "", "into:ternura")
    res = pareja.boton(ADMIN, "", "into:ternura")  # 3 + 1 + 3 = 7 puntos
    assert "las luces se apagan" in res.pantalla.texto and "Un momento muy especial" in res.pantalla.texto
    assert any(a.para == ANA and "las luces se apagan" in a.texto for a in res.avisos)
    for uid in (ADMIN, ANA):
        assert nec(pareja, uid)["social"] > 50 + 20 and hist(pareja, uid)[-1]["d"] == 4
        assert json.loads(pareja.db.jugador(uid).accion)["k"] == "abrazados"
    plano = pareja.boton(ADMIN, "", "plano").pantalla.texto
    assert "[L]💞 [A]💞" in plano and "descansando abrazados" in plano


def test_hoy_no_sin_ningun_castigo(pareja):
    proponer(pareja)
    res = pareja.boton(ANA, "", "intno")
    assert any(a.para == ADMIN and "prefiere hoy no" in a.texto for a in res.avisos)
    assert not hist(pareja, ADMIN) and not hist(pareja, ANA)
    assert "intsi" in datos(proponer(pareja))  # se puede volver a proponer cuando quieran


def test_cualquiera_puede_parar(pareja):
    proponer(pareja, "salon", "jugueton")
    pareja.boton(ANA, "", "intsi")
    pareja.boton(ADMIN, "", "into:musica")
    res = pareja.boton(ANA, "", "intpara")
    assert any(a.para == ADMIN and "prefirió parar" in a.texto for a in res.avisos)
    assert "Paraste" in res.pantalla.texto and not hist(pareja, ADMIN)
    assert pareja.boton(ADMIN, "", "into:abrazo").alerta == "Ese momento ya terminó."


def test_responder_aunque_este_en_pausa(pareja, reloj):
    proponer(pareja)
    reloj.avanzar(6)  # Ana se quedó en pausa
    assert "Ronda 1 de 3" in pareja.boton(ANA, "", "intsi").pantalla.texto


def test_sin_pareja_ocupados_y_espera(solo, reloj):
    res = solo.boton(ADMIN, "", "intimo")
    assert "Es para hacerlo en pareja" in res.pantalla.texto and "intl:cuarto" not in datos(res.pantalla)
    aceptar(solo, ANA, invitar(solo, ADMIN, ANA))
    crear_personaje(solo, ANA, "Ana")
    poner(solo, ANA, energia=5)
    assert "sin energía" in solo.boton(ADMIN, "", "intimo").pantalla.texto
    for uid in (ADMIN, ANA):
        poner(solo, uid, **LLENO)
    proponer(solo, "bano", "apasionado")
    solo.boton(ANA, "", "intsi")
    for opcion in ("copa", "beso", "pasion"):
        solo.boton(ADMIN, "", f"into:{opcion}")
        res = solo.boton(ANA, "", f"into:{opcion}")
    assert "Un momento inolvidable" in res.pantalla.texto  # 9 puntos
    assert hist(solo, ANA)[-1]["d"] == 5
    assert "Hace poco tuvieron un momento" in solo.boton(ADMIN, "", "intimo").pantalla.texto
    reloj.avanzar(I.ESPERA // 60 + 1)
    solo.boton(ADMIN, "", "continuar")
    solo.boton(ANA, "", "continuar")
    assert "intl:cuarto" in datos(solo.boton(ADMIN, "", "intimo").pantalla)


def test_no_hay_atajos(pareja):
    assert pareja.boton(ADMIN, "", "aj:abrazados").pantalla.clave == "intimo"
    assert pareja.boton(ADMIN, "", "a:abrazados").pantalla.clave == "intimo"
    pareja.boton(ADMIN, "", "as:abrazados")
    assert pareja.db.jugador(ADMIN).accion is None
    assert pareja.boton(ANA, "", "intsi").alerta == "Esa propuesta ya no está."  # nadie propuso nada
