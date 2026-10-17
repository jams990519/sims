"""Actualización 2, parte 8: notas en la nevera."""

import pytest

from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, poner, Reloj

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


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def dejar_nota(juego, uid, texto):
    juego.boton(uid, "", "notan")
    return juego.texto(uid, "", texto)


def test_dejar_una_nota(pareja):
    assert "notas" in datos(pareja.boton(ADMIN, "", "mcasa").pantalla)
    res = pareja.boton(ADMIN, "", "notan")
    assert "Escribe la nota" in res.pantalla.texto
    res = pareja.texto(ADMIN, "", "Te dejé pasta en la nevera 🍝")
    assert not res.avisos  # no es un mensaje del chat: se ve al entrar
    assert "Nota pegada en la nevera. Ana la verá al entrar al juego" in res.pantalla.texto
    assert "Tú · hace un momento:\n«Te dejé pasta en la nevera 🍝»" in res.pantalla.texto
    assert any(a.chat for a in pareja.texto(ADMIN, "", "hola").avisos)  # después, vuelve a ser chat


def test_la_pareja_la_ve_al_entrar(pareja, reloj):
    dejar_nota(pareja, ADMIN, "Te quiero 💞")
    assert "🏠 Casa 📝" in str(pareja.boton(ANA, "", "menu").pantalla.botones)
    assert "Tienes una nota nueva en la nevera" in pareja.boton(ANA, "", "sala").pantalla.texto
    assert "📝 Notas en la nevera (1)" in str(pareja.boton(ANA, "", "mcasa").pantalla.botones)
    reloj.avanzar(120)
    res = pareja.inicio(ANA, "Ana")  # vuelve a entrar al juego
    assert "📝 <b>Nota en la nevera</b> de" in res.pantalla.texto and "«Te quiero 💞»" in res.pantalla.texto
    assert "(hace 2 h)" in res.pantalla.texto
    pareja.boton(ANA, "", "continuar")
    assert "🏠 Casa" in str(pareja.boton(ANA, "", "menu").pantalla.botones)
    assert "🏠 Casa 📝" not in str(pareja.boton(ANA, "", "menu").pantalla.botones)  # ya la leyó
    pareja.boton(ADMIN, "", "continuar")
    assert "✓ leída" in pareja.boton(ADMIN, "", "notas").pantalla.texto


def test_al_volver_de_la_pausa(pareja, reloj):
    reloj.avanzar(10)
    pareja.boton(ADMIN, "", "continuar")
    dejar_nota(pareja, ADMIN, "Vuelvo pronto")
    res = pareja.boton(ANA, "", "continuar")
    assert "«Vuelvo pronto»" in res.pantalla.texto


def test_abrir_la_nevera_las_marca_leidas(pareja):
    dejar_nota(pareja, ADMIN, "Compra pan")
    texto = pareja.boton(ANA, "", "notas").pantalla.texto
    assert "🆕 Luis · hace un momento:\n«Compra pan»" in texto
    assert "🆕" not in pareja.boton(ANA, "", "notas").pantalla.texto


def test_nota_rapida_desde_el_trabajo(pareja):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner(pareja, ADMIN, **LLENO)
    pareja.boton(ADMIN, "", "trabajar:8:sin")
    assert "notan" in datos(pareja.boton(ADMIN, "", "trabajo").pantalla)
    dejar_nota(pareja, ADMIN, "Llego a las 5")
    assert pareja._notas_sin_leer(pareja.db.jugador(ANA))[0]["texto"] == "Llego a las 5"


def test_sin_pareja(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "para tu pareja" in juego.boton(ADMIN, "", "notan").alerta
