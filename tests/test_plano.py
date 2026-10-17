"""Actualización 2, parte 4: plano de la casa en texto."""

import json

import pytest

from simpareja import plano as PL
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


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
    return solo


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def plano(texto):
    """Las líneas dentro de <pre>."""
    return texto.split("<pre>")[1].split("</pre>")[0].split("\n")


@pytest.mark.parametrize("zonas", [("cuarto", "closet", "bano", "salon"), ("cuarto", "extra", "closet", "bano", "salon")])
def test_todas_las_lineas_miden_lo_mismo(zonas):
    dentro = {z: ["Lu", "Lu"] for z in zonas}
    lineas = PL.dibujar(zonas, dentro)
    assert len({len(l) for l in lineas}) == 1
    assert len(lineas[0]) <= 32  # cabe en la pantalla de un teléfono
    assert all(l[0] in "+|" and l[-1] in "+|" for l in lineas)
    assert lineas[6].endswith("|[Lu][Lu]|")  # los dos en el baño caben


def test_iniciales():
    assert PL.iniciales(["Luis", "Ana"]) == ["L", "A"]
    assert PL.iniciales(["Luis", "lucía"]) == ["Lu", "Lu"]
    assert PL.iniciales(["Eva", "Emilio"]) == ["Ev", "Em"]


def test_ver_el_plano(pareja):
    pareja.boton(ANA, "", "ir:cuarto")
    res = pareja.boton(ADMIN, "", "mcasa")
    assert "plano" in datos(res.pantalla)
    texto = pareja.boton(ADMIN, "", "plano").pantalla.texto
    assert "🏡 <b>Casita en renta</b> — Lunes 08:00" in texto
    lineas = plano(texto)
    assert "[A]" in lineas[5] and "CUARTO" in lineas[1]  # Ana en el cuarto (arriba a la izquierda)
    assert "[L]" in lineas[-2] and "SALA · COCINA · COMEDOR" in texto  # Luis en la sala
    assert "<code>[L]</code> Luis (tú): 🧍 sin hacer nada" in texto
    assert "<code>[A]</code> Ana: 🧍 sin hacer nada" in texto


def test_lo_que_hacen_y_lo_que_falta(pareja, reloj):
    h = pareja._hogar(pareja.db.jugador(ADMIN).sala_id)
    h.despensa = json.dumps({"pan": 2, "jamon": 1, "queso": 1})
    pareja.db.guardar_hogar(h)
    pareja.boton(ADMIN, "", "coc:sandwich:1")
    poner(pareja, ANA, **LLENO)
    pareja.boton(ANA, "", "tomar:recepcion")
    pareja.boton(ANA, "", "trabajar:8:sin")
    reloj.avanzar(1)
    texto = pareja.boton(ADMIN, "", "plano").pantalla.texto
    assert "Luis (tú): 🍳 cocinando sándwich de jamón y queso (5 min)" in texto
    assert "Ana: 💼 trabajando (7 h 59 min)" in texto
    assert "🚗 Fuera de casa: [A]" in texto


def test_el_plano_se_actualiza_solo(pareja, reloj):
    res = pareja.boton(ADMIN, "", "plano")
    assert res.pantalla.es_sala  # pantalla en vivo
    pareja.registrar_pantalla(ADMIN, 55, True, "plano")
    res = pareja.boton(ANA, "", "ir:bano")
    edicion = next(e for e in res.ediciones if e.para == ADMIN)
    assert edicion.msg_id == 55 and plano(edicion.pantalla.texto)[6].endswith("| [A]    |")  # Ana en el baño
    reloj.avanzar(6)  # Luis se queda mirando y su Sim se pausa
    edicion = next(e for e in pareja.tick().ediciones if e.para == ADMIN)
    assert "Tu Sim está en pausa" in edicion.pantalla.texto and datos(edicion.pantalla)[0] == "continuar"
    pareja.registrar_pantalla(ADMIN, 56, True, "sala")
    edicion = next(e for e in pareja.boton(ANA, "", "ir:cuarto").ediciones if e.para == ADMIN)
    assert "<pre>" not in edicion.pantalla.texto and "Sala de" in edicion.pantalla.texto


def test_moverse_desde_el_plano_vuelve_al_plano(solo):
    res = solo.boton(ADMIN, "", "moverse:plano")
    assert "ir:cuarto:plano" in datos(res.pantalla) and ("⬅️ Atrás", "plano") in res.pantalla.botones[-1]
    res = solo.boton(ADMIN, "", "ir:cuarto:plano")
    assert "Ahora estás en 🛏️ cuarto" in res.pantalla.texto and "<pre>" in res.pantalla.texto
    assert "[L]" in plano(res.pantalla.texto)[5]


def test_casa_grande_con_cuarto_extra(solo):
    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    h.cuenta = 5000
    solo.db.guardar_hogar(h)
    solo.boton(ADMIN, "", "mudanza:apartamento:si")
    solo.boton(ADMIN, "", "ir:extra")
    lineas = plano(solo.boton(ADMIN, "", "plano").pantalla.texto)
    assert "CUARTO 2" in lineas[1] and lineas[5].index("[L]") > lineas[5].index("|", 1)
