"""Medidor de relación: cada quien mueve el suyo, dice por qué y queda un historial."""

import pytest

from simpareja import relacion_juego as R
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, Reloj


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


def test_empieza_en_50_y_se_ve_en_el_menu(pareja):
    assert "medidor" in datos(pareja.boton(ADMIN, "", "mpar").pantalla)
    texto = pareja.boton(ADMIN, "", "medidor").pantalla.texto
    assert "Tú → Ana: ❤️❤️❤️❤️❤️🤍🤍🤍🤍🤍 <b>50 %</b>" in texto and "Ana → tú:" in texto


def test_subir_con_motivo_avisa_a_la_pareja(pareja):
    res = pareja.boton(ANA, "", "rel:+")
    assert datos(res.pantalla)[:3] == ["rel:+:1", "rel:+:5", "rel:+:10"]
    res = pareja.boton(ANA, "", "rel:+:5")
    assert "rel:+:5:1" in datos(res.pantalla) and "rel:+:5:otro" in datos(res.pantalla)
    res = pareja.boton(ANA, "", "rel:+:5:1")  # 🍳 Cocinó para mí
    assert "tu medidor subió a 55 %" in res.pantalla.texto
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert "subió su medidor +5 por «🍳 Cocinó para mí». Ahora siente un 55 %" in aviso.texto
    texto = pareja.boton(ADMIN, "", "medidor").pantalla.texto
    assert "Ana → tú: ❤️❤️❤️❤️❤️❤️🤍🤍🤍🤍 <b>55 %</b>" in texto  # 55 % son 6 corazones
    assert "Ana: +5 · 🍳 Cocinó para mí" in texto
    assert "💗 Tú → Ana: 50 % · Ana → tú: 55 %" in pareja.boton(ADMIN, "", "perfil").pantalla.texto


def test_bajar_con_motivo_escrito(pareja):
    pareja.boton(ADMIN, "", "rel:-:10")
    res = pareja.boton(ADMIN, "", "rel:-:10:otro")
    assert "Escribe el motivo" in res.pantalla.texto
    res = pareja.texto(ADMIN, "", "no me esperó para cenar")
    assert not [a for a in res.avisos if a.chat]  # el motivo no va al chat
    assert "tu medidor bajó a 40 %" in res.pantalla.texto
    assert any(a.para == ANA and "−10 por «✍️ no me esperó para cenar»" in a.texto for a in res.avisos)
    assert any(a.chat for a in pareja.texto(ADMIN, "", "perdón 💞").avisos)  # después, vuelve a ser chat


def test_no_pasa_de_0_ni_de_100(pareja):
    for _ in range(6):
        pareja.boton(ADMIN, "", "rel:+:10:0")
    assert pareja._relacion(pareja.db.jugador(ADMIN)) == 100
    res = pareja.boton(ADMIN, "", "rel:+:10:0")
    assert "ya está en 100 %" in res.pantalla.texto and not res.avisos
    assert R.barra_relacion(0) == "🤍" * 10 and R.barra_relacion(45).count("❤️") == 5


def test_sin_pareja_no_hay_medidor(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "para jugar en pareja" in juego.boton(ADMIN, "", "medidor").alerta
