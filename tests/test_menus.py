"""Actualización 2, parte 1: menús, fichas para confirmar, habitaciones y lugares (y parte 5: social)."""

import json

import pytest

from simpareja import vida as V
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import dar_objetos, ir_al_dia, nec, nuevo_juego, poner, Reloj


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


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def test_menu_principal_con_las_7_secciones(solo):
    res = solo.boton(ADMIN, "", "menu")
    assert datos(res.pantalla) == ["mcasa", "macc", "mlug", "trabajo", "mpar", "mest", "sala"]
    assert "🍔 80" in res.pantalla.texto and "📍 🛋️ Sala-cocina-comedor" in res.pantalla.texto


def test_jugar_abre_el_menu(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    res = crear_personaje(juego, ADMIN, "Luis")
    assert ("🎮 Jugar", "menu") in res.pantalla.botones[0]


@pytest.mark.parametrize("submenu, atras", [
    ("mcasa", "menu"), ("macc", "menu"), ("mlug", "menu"), ("trabajo", "menu"), ("mpar", "menu"),
    ("mest", "menu"), ("acc:comer", "macc"), ("acc:limpieza", "macc"), ("sim", "mest"), ("dinero", "mest"),
    ("nevera", "mcasa"), ("animos", "mest"), ("ajustes", "mest"), ("pjs", "mest"), ("casa", "mcasa"),
])
def test_siempre_hay_un_boton_atras(solo, submenu, atras):
    pantalla = solo.boton(ADMIN, "", submenu).pantalla
    assert ("⬅️ Atrás", atras) in [b for fila in pantalla.botones for b in fila]


def test_ficha_con_efecto_y_tiempo(solo):
    res = solo.boton(ADMIN, "", "a:redes")
    assert "📱 <b>Ver redes o videos</b>" in res.pantalla.texto
    assert "+10 🎉 diversión, +5 💬 social · ⏱️ 1 h" in res.pantalla.texto
    assert datos(res.pantalla) == ["as:redes", "acc:diversion"]
    assert solo.db.jugador(ADMIN).accion is None  # todavía no empezó
    res = solo.boton(ADMIN, "", "acc:diversion")
    assert "Diversión" in res.pantalla.texto


def test_en_pareja_la_ficha_ofrece_las_dos_opciones(pareja):
    dar_objetos(pareja, ADMIN, "tv")
    res = pareja.boton(ADMIN, "", "a:tele")
    assert "👤 Solo: +15 🎉 diversión, +3 💬 social · ⏱️ 1 h" in res.pantalla.texto
    assert "💞 Con" in res.pantalla.texto and "+15 💬 social · ⏱️ 42 min" in res.pantalla.texto
    assert datos(res.pantalla) == ["as:tele", "aj:tele", "acc:diversion"]


def test_moverse_y_las_acciones_llevan_a_su_habitacion(solo):
    assert solo.db.jugador(ADMIN).lugar == "salon"
    res = solo.boton(ADMIN, "", "moverse")
    assert "ir:cuarto" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "ir:cuarto")
    assert "Ahora estás en 🛏️ cuarto" in res.pantalla.texto
    poner(solo, ADMIN, higiene=10)
    res = solo.boton(ADMIN, "", "a:ducha")
    assert "🚶 Irá a 🚿 baño" in res.pantalla.texto
    solo.boton(ADMIN, "", "as:ducha")
    assert solo.db.jugador(ADMIN).lugar == "bano"


def test_lugares_con_precios(solo, reloj):
    res = solo.boton(ADMIN, "", "mlug")
    assert {"a:super", "a:restaurante", "a:cine", "a:parque", "a:gimnasio"} <= set(datos(res.pantalla))
    poner(solo, ADMIN, hambre=10)
    assert "💵 $20" in solo.boton(ADMIN, "", "a:restaurante").pantalla.texto
    solo.boton(ADMIN, "", "as:restaurante")
    assert hogar(solo).cuenta == 2080
    assert solo.db.jugador(ADMIN).lugar == "fuera:restaurante"
    reloj.avanzar(91)
    solo.boton(ADMIN, "", "sim")
    assert solo.db.jugador(ADMIN).lugar == "salon"  # al terminar vuelve a casa


def test_fin_de_semana_restaurante_y_cine_mas_caros(solo, reloj):
    ir_al_dia(solo, reloj, ADMIN, 6)
    assert "fin de semana" in solo.boton(ADMIN, "", "mlug").pantalla.texto.lower()
    assert "💵 $16" in solo.boton(ADMIN, "", "a:cine").pantalla.texto  # $13 + 25 %


def test_cita_en_el_cine_juntos(pareja):
    res = pareja.boton(ANA, "", "a:cine")
    assert "+50 💬 social" in res.pantalla.texto and "💵 $25" in res.pantalla.texto
    res = pareja.boton(ANA, "", "aj:cine")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ADMIN, "", si)
    assert hogar(pareja).cuenta == 2075


def test_cuota_del_gimnasio_una_vez_al_mes(solo, reloj):
    poner(solo, ADMIN, energia=100)
    assert "💵 $30" in solo.boton(ADMIN, "", "a:gimnasio").pantalla.texto
    solo.boton(ADMIN, "", "as:gimnasio")
    reloj.avanzar(61)
    solo.boton(ADMIN, "", "sim")
    assert "💵" not in solo.boton(ADMIN, "", "a:gimnasio").pantalla.texto
    solo.boton(ADMIN, "", "as:gimnasio")
    assert hogar(solo).cuenta == 2070


def test_lo_que_aun_no_existe_avisa_que_llega_pronto(solo):
    res = solo.boton(ADMIN, "", "pronto:influencer")
    assert "🚧" in res.alerta and "influencer" in res.alerta
    assert "pronto:influencer" in datos(solo.boton(ADMIN, "", "trabajo").pantalla)


def test_perfil_de_la_pareja(pareja):
    texto = pareja.boton(ADMIN, "", "perfil").pantalla.texto
    assert "Perfil de" in texto and "Ana" in texto and "🍔" in texto


def test_comer_lo_que_hay_incluye_el_taper(solo):
    j = solo.db.jugador(ADMIN)
    j.taper = "sopa"
    solo.db.guardar_jugador(j)
    poner(solo, ADMIN, hambre=10)
    res = solo.boton(ADMIN, "", "a:comer")
    assert "a:comer:taper" in datos(res.pantalla)
    solo.boton(ADMIN, "", "as:comer:taper")
    assert solo.db.jugador(ADMIN).taper == ""


def test_mi_carrera_con_historial(solo, reloj):
    solo.boton(ADMIN, "", "tomar:recepcion")
    poner(solo, ADMIN, hambre=100, energia=100, higiene=100, diversion=100, social=100)
    solo.boton(ADMIN, "", "trabajar:8:sin")
    reloj.avanzar(8 * 60 + 1)
    aviso = next(a for a in solo.tick().avisos if "Cobró" in a.texto)
    assert "⚡ −64 energía · 🍔 −72 hambre" in aviso.texto and "Faltan 4 día(s) para el ascenso" in aviso.texto
    texto = solo.boton(ADMIN, "", "carrera").pantalla.texto
    assert "👉 Nivel 1" in texto and "1/5 días" in texto and "8.0 h · $88" in texto


# --- parte 5: necesidad social --------------------------------------------------------

def test_social_ampliada():
    juntos = lambda clave: V.preparar(V.ACCIONES[clave], 0, V.nuevas_necesidades(), 100, juntos=True)["ef"]
    solo = lambda clave: V.preparar(V.ACCIONES[clave], 0, V.nuevas_necesidades(), 100)["ef"]
    assert solo("redes") == {"diversion": 10, "social": 5}
    assert solo("tele") == {"diversion": 15, "social": 3}
    assert juntos("tele")["social"] == 15 and juntos("redes")["social"] == 15
    assert solo("telefono") == {"social": 20}


def test_hablar_por_telefono(solo, reloj):
    poner(solo, ADMIN, social=10)
    solo.boton(ADMIN, "", "as:telefono")
    reloj.avanzar(21)
    solo.boton(ADMIN, "", "sim")
    assert nec(solo, ADMIN)["social"] == pytest.approx(10 + 20 - 3 * 21 / 60, abs=0.2)
    assert json.loads(solo.db.jugador(ADMIN).necesidades)
