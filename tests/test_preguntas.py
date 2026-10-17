"""Actualización 2, parte 7: preguntas de pareja según el estado de ánimo."""

import random

import pytest

from simpareja import preguntas as Q
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


def pregunta(juego):
    return juego._pregunta(juego._hogar(juego.db.jugador(ADMIN).sala_id))


def test_banco_con_muchas_preguntas_por_estado():
    from simpareja import personaje as P
    for o in P.ANIMO.opciones:
        banco = Q.BANCO[o.clave]
        assert len(banco) >= 10 and len({t for _, t in banco}) == len(banco)
        assert all(tema in Q.TEMAS for tema, _ in banco)
    assert "¿Qué necesitas de mí ahora mismo?" in [t for _, t in Q.BANCO["triste"]]
    recientes = [t for _, t in Q.BANCO["feliz"][:9]]
    assert Q.elegir("feliz", recientes, random.Random(1)) == Q.BANCO["feliz"][9]  # no repite


def test_al_cambiar_de_animo_aparece_una_pregunta(pareja):
    pareja.boton(ANA, "", "animo:triste")
    res = pareja.boton(ANA, "", "animop")
    p = pregunta(pareja)
    assert p["animo"] == "triste" and p["para"] == ANA
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert p["texto"] in aviso.texto and "Según el ánimo de Ana: 🔵 😢 Triste" in aviso.texto
    assert ("✍️ Responder", "pregr") in aviso.botones[0]
    assert "Según tu ánimo" in res.pantalla.texto
    pareja.boton(ANA, "", "animo:feliz")
    pareja.boton(ANA, "", "animop")
    assert pregunta(pareja)["id"] == p["id"]  # no cambia a cada rato
    assert "❓ Preguntas (1)" in str(pareja.boton(ADMIN, "", "mpar").pantalla.botones)


def test_responder_y_me_gusto(pareja):
    pareja.boton(ADMIN, "", "pregn")  # Luis le hace una pregunta a Ana, según el ánimo de ella
    p = pregunta(pareja)
    assert p["para"] == ANA and p["por"] == ADMIN
    res = pareja.boton(ANA, "", "pregr")
    assert "Escribe tu respuesta" in res.pantalla.texto
    res = pareja.texto(ANA, "", "Cuando nos perdimos en la playa 😂")
    assert "Respuesta enviada" in res.pantalla.texto
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert "«Cuando nos perdimos en la playa 😂»" in aviso.texto
    assert datos(aviso)[:2] == [f"pregv:{p['id']}:1", f"pregv:{p['id']}:0"] and "pregr" in datos(aviso)
    assert "Ana: «Cuando nos perdimos" in pareja.boton(ADMIN, "", "preg").pantalla.texto
    res = pareja.boton(ADMIN, "", f"pregv:{p['id']}:1")
    assert "Tu medidor subió 3" in res.pantalla.texto
    assert pareja._relacion(pareja.db.jugador(ADMIN)) == 53
    assert any(a.para == ANA and "le gustó tu respuesta" in a.texto for a in res.avisos)
    assert pareja.boton(ADMIN, "", f"pregv:{p['id']}:1").alerta == "Ya la valoraste."
    album = pareja.boton(ADMIN, "", "album").pantalla.texto
    assert "Respuestas que les gustaron" in album and "«Cuando nos perdimos en la playa 😂»" in album
    temas = pareja.boton(ADMIN, "", "pregt").pantalla.texto
    assert f"{Q.TEMAS[p['tema']]}: 💗 1 · 🙈 0" in temas


def test_no_me_gusto_no_baja_nada_solo(pareja):
    pareja.boton(ANA, "", "pregn")
    p = pregunta(pareja)
    pareja.boton(ADMIN, "", "pregr")
    pareja.texto(ADMIN, "", "no sé")
    res = pareja.boton(ANA, "", f"pregv:{p['id']}:0")
    assert "No baja nada solo" in res.pantalla.texto
    assert datos(res.pantalla)[:2] == ["sala", "rel:-"]
    assert pareja._relacion(pareja.db.jugador(ANA)) == 50
    assert any(a.para == ADMIN and "no le convenció" in a.texto for a in res.avisos)
    assert "Respuestas que les gustaron" not in pareja.boton(ANA, "", "album").pantalla.texto
    assert f"{Q.TEMAS[p['tema']]}: 💗 0 · 🙈 1" in pareja.boton(ANA, "", "pregt").pantalla.texto


def test_responder_no_va_al_chat_y_luego_si(pareja):
    pareja.boton(ADMIN, "", "pregn")
    pareja.boton(ANA, "", "pregr")
    res = pareja.texto(ANA, "", "mi respuesta")
    assert not [a for a in res.avisos if a.para == ADMIN and a.texto.startswith("💬")]
    res = pareja.texto(ANA, "", "ahora es chat")
    assert any(a.chat and "ahora es chat" in a.texto for a in res.avisos)


def test_nueva_pregunta_guarda_la_anterior(pareja):
    pareja.boton(ADMIN, "", "pregn")
    primera = pregunta(pareja)["texto"]
    pareja.boton(ADMIN, "", "pregn")
    assert pregunta(pareja)["texto"] != primera
    assert primera in pareja.boton(ADMIN, "", "pregt").pantalla.texto


def test_sin_pareja_no_hay_preguntas(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "para jugar en pareja" in juego.boton(ADMIN, "", "preg").alerta
    juego.boton(ADMIN, "", "animo:triste")
    juego.boton(ADMIN, "", "animop")
    assert juego._pregunta(juego._hogar(juego.db.jugador(ADMIN).sala_id)) is None
