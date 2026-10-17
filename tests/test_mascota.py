"""Actualización 2, parte 14: mascota."""

import json

import pytest

from simpareja import dinero as D
from simpareja import mascota_juego as M
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


def mascota(juego):
    return json.loads(hogar(juego).extras).get("mascota")


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def adoptar(juego, tipo="perro", nombre="Kira"):
    juego.boton(ADMIN, "", f"mascad:{tipo}:0")
    juego.texto(ADMIN, "", nombre)
    return juego.boton(ANA, "", "mascok")


def poner_mascota(juego, **barras):
    h = hogar(juego)
    ex = json.loads(h.extras)
    ex["mascota"]["nec"].update(barras)
    h.extras = json.dumps(ex)
    juego.db.guardar_hogar(h)


def test_adoptar_de_acuerdo_los_dos(pareja):
    res = pareja.boton(ADMIN, "", "mascota")
    assert datos(res.pantalla)[:2] == ["mascad:perro", "mascad:gato"]
    res = pareja.boton(ADMIN, "", "mascad:perro")
    assert "mascad:perro:0" in datos(res.pantalla)
    res = pareja.boton(ADMIN, "", "mascad:perro:0")
    assert "¿Cómo se va a llamar?" in res.pantalla.texto
    res = pareja.texto(ADMIN, "", "Kira")
    assert not [a for a in res.avisos if a.chat]  # el nombre no va al chat
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "quiere adoptar a <b>Kira</b>: 🐶 perro 🤎 marrón ($150" in aviso.texto and "mascok" in datos(aviso)
    res = pareja.boton(ANA, "", "mascok")
    assert "¡Kira llegó a casa!" in res.pantalla.texto and hogar(pareja).cuenta == 2100 - 150
    assert mascota(pareja)["nec"] == {"hambre": 100, "felicidad": 100, "limpieza": 100}
    assert "mascota" in json.loads(hogar(pareja).extras)["hitos"]


def test_barras_y_acciones(pareja, reloj):
    adoptar(pareja)
    pareja.tick()
    reloj.avanzar(60)
    pareja.boton(ADMIN, "", "continuar")
    pareja.tick()
    texto = pareja.boton(ADMIN, "", "mascota").pantalla.texto
    assert "🍖" in texto and "Felicidad" in texto
    assert mascota(pareja)["nec"]["hambre"] < 100
    poner_mascota(pareja, hambre=30)
    pareja.boton(ADMIN, "", "as:dar_comida")
    reloj.avanzar(6)
    pareja.boton(ADMIN, "", "sim")
    assert mascota(pareja)["nec"]["hambre"] == pytest.approx(90, abs=1)


def test_pasear_al_perro_juntos_sube_la_relacion_y_cuenta_como_parque(pareja, reloj):
    adoptar(pareja)
    poner_mascota(pareja, felicidad=40)
    poner(pareja, ADMIN, **LLENO)
    poner(pareja, ANA, **LLENO)
    res = pareja.boton(ANA, "", "aj:pasear")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ADMIN, "", si)
    assert "Fuera de casa: [L][A](K)" in pareja.boton(ADMIN, "", "plano").pantalla.texto
    reloj.avanzar(45)
    pareja.tick()
    assert mascota(pareja)["nec"]["felicidad"] == pytest.approx(80, abs=1)  # +40 una sola vez
    for uid in (ADMIN, ANA):
        historial = pareja._extras(pareja.db.jugador(uid))["relacion_hist"]
        assert any("Con Kira, juntos" in c["m"] for c in historial)


def test_al_gato_no_se_lo_pasea(pareja):
    adoptar(pareja, "gato", "Michi")
    assert "los gatos prefieren jugar en casa" in pareja.boton(ADMIN, "", "as:pasear").alerta
    assert "a:pasear" not in datos(pareja.boton(ADMIN, "", "mascota").pantalla)


def test_sin_mascota_no_hay_acciones(pareja):
    assert "No tienen mascota" in pareja.boton(ADMIN, "", "as:jugar_mascota").alerta


def test_comida_en_las_facturas_y_cuidador_en_el_viaje(pareja):
    adoptar(pareja)
    assert "🐾 Comida de la mascota: $40" in pareja.boton(ADMIN, "", "facturas").pantalla.texto
    assert D.total_mes({}, D.CASAS["casita"], mascota=True) == 1110 + 40
    hoy = pareja._hoy(pareja.db.jugador(ADMIN))
    antes = hogar(pareja).cuenta
    pareja.boton(ADMIN, "", f"viaje:playa:{hoy}")
    pareja.boton(ANA, "", "viajeok")
    assert hogar(pareja).cuenta == antes - 800 - 2 * M.CUIDADOR_DIA


def test_en_el_plano(pareja):
    adoptar(pareja)
    texto = pareja.boton(ADMIN, "", "plano").pantalla.texto
    assert "(K)" in texto.split("<pre>")[1] and "<code>(K)</code> 🐶 Kira: 🍖 100" in texto


def test_si_se_la_descuida_hace_ruido_de_noche(pareja, reloj):
    adoptar(pareja)
    poner_mascota(pareja, felicidad=5)
    ir_al_dia(pareja, reloj, ADMIN, 2)
    reloj.avanzar(14 * 60)  # 22:00
    pareja.boton(ADMIN, "", "continuar")
    poner(pareja, ADMIN, energia=30)
    pareja.boton(ADMIN, "", "as:dormir:4")
    avisos = [a for a in pareja.tick().avisos if "toda la noche" in a.texto]
    assert avisos and "ladró" in avisos[0].texto
    assert not [a for a in pareja.tick().avisos if "toda la noche" in a.texto]  # una vez por noche


def test_si_esta_triste_rompe_cosas(pareja, monkeypatch):
    adoptar(pareja)
    poner_mascota(pareja, felicidad=5)
    monkeypatch.setattr(pareja.rng, "random", lambda: 0.0)
    antes = hogar(pareja).cuenta
    avisos = [a for a in pareja.tick().avisos if "rompió algo" in a.texto]
    assert avisos and hogar(pareja).cuenta < antes
    assert not [a for a in pareja.tick().avisos if "rompió algo" in a.texto]  # como mucho una vez al día
