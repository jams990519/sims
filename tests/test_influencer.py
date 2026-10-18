"""Diseño v1, parte 9: influencer (con el equipo de la actualización 2, parte 13)."""

import dataclasses
import json

import pytest

from simpareja import eventos as E
from simpareja import influencer_juego as I
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import dar_objetos, nuevo_juego, poner, Reloj

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
    for uid in (ADMIN, ANA):
        poner(juego, uid, **LLENO)
    return juego


def influ(juego, uid=ADMIN):
    return juego._influ(juego.db.jugador(uid))


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def hacer(juego, reloj, uid, accion, minutos):
    juego.boton(uid, "", "continuar")
    res = juego.boton(uid, "", f"as:{accion}")
    reloj.avanzar(minutos + 1)
    juego.tick()
    return res


def test_funciones():
    assert I.nivel(0) == 1 and I.nivel(250) == 3 and I.nivel(9999) == 5
    assert I.calidad(1, 0, False) == 1 and I.calidad(2, 3, True) == pytest.approx(1.95)
    assert [I.perdida(d) for d in (0, 2, 3, 6, 7, 30)] == [0, 0, 0.02, 0.02, 0.05, 0.05]


def test_un_video_de_principio_a_fin(pareja, reloj):
    assert "influ" in datos(pareja.boton(ADMIN, "", "trabajo").pantalla)
    res = pareja.boton(ADMIN, "", "influ")
    assert "influ:tema:cocina" in datos(res.pantalla) and "0 seguidores" in res.pantalla.texto
    assert "Primero elige el tema" in pareja.boton(ADMIN, "", f"as:grabar:{ADMIN}").alerta
    res = pareja.boton(ADMIN, "", "influ:tema:humor")
    assert f"a:grabar:{ADMIN}" in datos(res.pantalla)
    hacer(pareja, reloj, ADMIN, f"grabar:{ADMIN}", 15)
    assert influ(pareja)["video"]["grabado"]
    assert "a:editar" in datos(pareja.boton(ADMIN, "", "influ").pantalla)
    hacer(pareja, reloj, ADMIN, "editar", 10)
    d = influ(pareja)
    assert d["videos"] == 1 and d["seguidores"] >= 20 and "video" not in d
    assert 5 <= pareja.db.jugador(ADMIN).cartera <= 20
    assert d["ultimo"] == pareja._hoy(pareja.db.jugador(ADMIN))


def test_la_pareja_escribe_el_guion(pareja, reloj):
    pareja.boton(ADMIN, "", "influ:tema:cocina")
    res = pareja.boton(ANA, "", "influ")
    assert "a:guion" in datos(res.pantalla) and "puedes escribirle el guion" in res.pantalla.texto
    hacer(pareja, reloj, ANA, "guion", 10)
    assert influ(pareja)["video"]["guion"]
    for uid in (ADMIN, ANA):
        assert any("Guion" in c["m"] for c in pareja._extras(pareja.db.jugador(uid))["relacion_hist"])


def test_grabar_juntos_y_salir_en_el_video(pareja, reloj):
    pareja.boton(ADMIN, "", "influ:tema:pareja")
    pareja.boton(ANA, "", "influ:tema:fitness")  # Ana tiene su propio video
    res = pareja.boton(ADMIN, "", f"aj:grabar:{ADMIN}")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ANA, "", si)
    reloj.avanzar(11)  # 15 min × 0,7
    pareja.tick()
    assert influ(pareja)["video"] == {"tema": "pareja", "grabado": True, "juntos": True, "guion": False}
    assert influ(pareja, ANA)["video"]["grabado"] is False  # el de Ana sigue sin grabar


def test_patrocinio_desde_mil_seguidores(pareja, reloj, monkeypatch):
    j = pareja.db.jugador(ADMIN)
    pareja._guardar_influ(j, {"seguidores": 1500, "xp": 0, "videos": 3, "ganado": 0, "ultimo": pareja._hoy(j),
                              "video": {"tema": "humor", "grabado": True, "juntos": False, "guion": False}})
    monkeypatch.setattr(pareja.rng, "random", lambda: 0.0)
    hacer(pareja, reloj, ADMIN, "editar", 10)
    assert pareja.db.jugador(ADMIN).cartera >= 100 + 5


def test_sin_publicar_se_pierden_seguidores(pareja):
    j = pareja.db.jugador(ADMIN)
    hoy = pareja._hoy(j)
    pareja._guardar_influ(j, {"seguidores": 1010, "xp": 0, "videos": 3, "ganado": 0, "ultimo": hoy - 3})
    avisos = pareja.tick().avisos
    assert influ(pareja)["seguidores"] == int(1010 * 0.98)
    assert any("se acabaron los patrocinios" in a.texto for a in avisos)
    pareja.tick()
    assert influ(pareja)["seguidores"] == int(1010 * 0.98)  # una vez al día


def test_aprender_sube_de_nivel_y_el_equipo_mejora(pareja, reloj):
    for _ in range(4):
        hacer(pareja, reloj, ADMIN, "aprender_redes", 15)
    assert I.nivel(influ(pareja)["xp"]) == 2
    dar_objetos(pareja, ADMIN, "camara", "aro", "micro")
    assert "Equipo: 3/3" in pareja.boton(ADMIN, "", "influ").pantalla.texto


def test_video_viral(pareja, monkeypatch):
    juego = pareja
    j = juego.db.jugador(ANA)
    juego._guardar_influ(j, {"seguidores": 100, "xp": 0, "videos": 1, "ganado": 0, "ultimo": juego._hoy(j)})
    juego.cfg = dataclasses.replace(juego.cfg, eventos=True)
    monkeypatch.setattr(E, "elegir", lambda *a: E.POR_CLAVE["viral"])
    h = juego._hogar(j.sala_id)
    ex = json.loads(h.extras)
    ex["eventos"] = {"proximo": 0}
    h.extras = json.dumps(ex)
    juego.db.guardar_hogar(h)
    avisos = [a for a in juego.tick().avisos if "Video viral" in a.texto]
    assert avisos and influ(juego, ANA)["seguidores"] >= 600
