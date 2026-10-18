"""Actualización 2, parte 4: plano de la casa en texto."""

import json

import pytest

from simpareja import personaje as P
from simpareja import plano as PL
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import dar_objetos, nuevo_juego, poner, Reloj

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


def quien(juego, uid, nombre):
    """'Ana 🌸': el nombre con el color de su ánimo, como en la leyenda del plano."""
    return f"{nombre} {P.color_animo(juego.db.jugador(uid).ap)}"


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def plano(texto):
    """Las líneas dentro de <pre>."""
    return texto.split("<pre>")[1].split("</pre>")[0].split("\n")


@pytest.mark.parametrize("zonas", [("cuarto", "closet", "bano", "salon"), ("cuarto", "extra", "closet", "bano", "salon")])
def test_cabe_en_un_telefono_pequeno_y_no_se_descuadra(zonas):
    dentro = {z: [("Lu", "😴"), ("Lu", "🛁")] for z in zonas}
    dentro["cuarto"] = [("L", "😴"), ("A", "😴")]
    lineas = PL.dibujar(zonas, dentro)
    assert {PL.ancho(l) for l in lineas} == {PL.ANCHO} and PL.ANCHO <= 22  # cada ícono cuenta como dos
    assert all(l[0] in "+|" and l[-1] in "+|" for l in lineas)
    assert lineas[5].endswith("|[Lu][Lu]|")  # los dos en el baño caben (sin íconos)
    assert "[L]😴 [A]😴" in "".join(lineas)  # en el cuarto caben con su ícono


def test_iconos():
    assert PL.icono("😴") == "😴" and PL.icono("🍽️") == "🍴" and PL.icono("🏋️") == "💪"
    assert PL.icono("🧑‍🍳") == ""  # varios caracteres: no se arriesga
    assert PL.ancho("[L]😴") == 5 and PL.ancho("🍽️") == 2
    assert PL.marcas([("L", "😴"), ("A", "🚿")]) == "[L]😴 [A]🚿"
    assert PL.marcas([("L", "😴"), ("A", "🚿")], 8) == "[L][A]"


def test_iniciales():
    assert PL.iniciales(["Luis", "Ana"]) == ["L", "A"]
    assert PL.iniciales(["Luis", "lucía"]) == ["Lu", "Lu"]
    assert PL.iniciales(["Eva", "Emilio"]) == ["Ev", "Em"]


def test_la_casa_es_el_plano(pareja, reloj):
    pareja.boton(ANA, "", "ir:cuarto")
    poner(pareja, ANA, energia=10)
    pareja.boton(ANA, "", "as:dormir:4")
    res = pareja.boton(ADMIN, "", "mcasa")  # 🏠 Casa abre el plano directamente
    assert res.pantalla.clave == "plano" and res.pantalla.es_sala
    assert {"moverse:plano", "nevera", "objetos", "notas", "mascota", "casa"} <= set(datos(res.pantalla))
    assert pareja.comando(ADMIN, "Admin", "casa").pantalla.clave == "plano"
    texto = res.pantalla.texto
    assert "🏡 <b>Casita en renta</b> — Lunes 8:00 am" in texto
    lineas = plano(texto)
    assert "[A]😴" in lineas[2] and "CUARTO" in lineas[1]  # Ana duerme en el cuarto (arriba a la izquierda)
    assert lineas[-3].startswith("| [L]") and "SALA·COCINA·COMEDOR" in texto  # Luis en la sala, sin hacer nada
    assert not any(cosa in texto.split("</pre>")[0] for cosa in ("cama", "ducha", "nevera"))  # solo los jugadores
    assert f"<code>[A]</code> {quien(pareja, ANA, 'Ana')}: 😴 durmiendo" in texto


def test_ver_el_plano(pareja):
    pareja.boton(ANA, "", "ir:cuarto")
    texto = pareja.boton(ADMIN, "", "plano").pantalla.texto
    assert f"<code>[L]</code> {quien(pareja, ADMIN, 'Luis')} (tú): 🧍 sin hacer nada" in texto
    assert f"<code>[A]</code> {quien(pareja, ANA, 'Ana')}: 🧍 sin hacer nada" in texto


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
    assert f"{quien(pareja, ADMIN, 'Luis')} (tú): 🍳 cocinando sándwich de jamón y queso (2 min)" in texto
    assert f"{quien(pareja, ANA, 'Ana')}: 💼 trabajando (7 h 59 min)" in texto
    assert "🚗 Fuera de casa: [A]" in texto


def test_el_plano_se_actualiza_solo(pareja, reloj):
    res = pareja.boton(ADMIN, "", "plano")
    assert res.pantalla.es_sala  # pantalla en vivo
    pareja.registrar_pantalla(ADMIN, 55, True, "plano")
    res = pareja.boton(ANA, "", "ir:bano")
    edicion = next(e for e in res.ediciones if e.para == ADMIN)
    assert edicion.msg_id == 55 and plano(edicion.pantalla.texto)[5].endswith("| [A]    |")  # Ana en el baño
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
    assert "[L]" in plano(res.pantalla.texto)[2]


def test_casa_grande_con_cuarto_extra(solo):
    h = solo._hogar(solo.db.jugador(ADMIN).sala_id)
    h.cuenta = 5000
    solo.db.guardar_hogar(h)
    solo.boton(ADMIN, "", "mudanza:apartamento:si")
    solo.boton(ADMIN, "", "ir:extra")
    lineas = plano(solo.boton(ADMIN, "", "plano").pantalla.texto)
    assert "CUARTO 2" in lineas[4] and lineas[5].startswith("| [L]")  # Luis en el cuarto 2 (abajo del cuarto)


def test_la_marca_va_debajo_de_donde_hace_la_accion(solo):
    def columnas(palabra):
        lineas = plano(solo.boton(ADMIN, "", "plano").pantalla.texto)
        return lineas[7].index(palabra), lineas[8].index("[L]")

    assert columnas("SALA") == (2, 2)  # sin hacer nada: en la sala
    poner(solo, ADMIN, hambre=10)
    solo.boton(ADMIN, "", "as:picar")
    assert columnas("COCINA") == (7, 7) and "[L]🍎" in plano(solo.boton(ADMIN, "", "plano").pantalla.texto)[8]
    solo.boton(ADMIN, "", "parar")
    poner(solo, ADMIN, hambre=10)
    solo.boton(ADMIN, "", "as:domicilio")
    assert columnas("COMEDOR") == (14, 14)
    solo.boton(ADMIN, "", "parar")
    dar_objetos(solo, ADMIN, "tv")
    solo.boton(ADMIN, "", "as:tele")
    assert columnas("SALA") == (2, 2)
