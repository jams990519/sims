"""Dibujos de los mensajitos: según el momento real del día y con las figuras de cada uno."""

import asyncio
import random

import pytest

from simpareja import ilustraciones as IL
from simpareja import narracion as N
from simpareja.bot import BotSimPareja
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Aviso, Juego
from test_bot import TelegramFalso
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, poner, Reloj


def test_momentos_del_dia():
    assert [N.momento(h) for h in (6, 10.9, 11, 17.4, 18, 19.6, 23, 3)] == [
        "manana", "manana", "tarde", "tarde", "atardecer", "noche", "noche", "noche"]


def test_dibujos_pequenos_para_gastar_pocos_datos():
    for escena in IL.ESCENAS:
        for cuando in N.MOMENTOS:
            jpeg = IL.dibujar(f"{escena}:{cuando}:hm")
            assert jpeg[:2] == b"\xff\xd8" and len(jpeg) < 40_000
    assert IL.dibujar("parque_banca:noche:m") != IL.dibujar("parque_banca:noche:hm")  # sola o en pareja
    with pytest.raises(ValueError):
        IL.dibujar("parque_banca:mediodia:h")


def test_de_noche_el_parque_es_de_noche():
    reloj = Reloj()
    reloj.avanzar(13 * 60)  # 9:00 pm
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    for uid in (ADMIN, ANA):
        poner(juego, uid, energia=100)
    res = juego.boton(ADMIN, "", "aj:parque")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    juego.boton(ANA, "", si)  # 15 min × 0,7 ≈ 10 min
    inicio = reloj()
    reloj.t = inicio + 7.5 * 60  # la banca
    avisos = {a.para: a for a in juego.tick().avisos if a.silencio}
    luis, ana = (juego.db.jugador(u) for u in (ADMIN, ANA))
    figuras = N.letra(luis.ap.get("genero")) + N.letra(ana.ap.get("genero"))
    assert avisos[ADMIN].foto == f"ilus:parque_banca:noche:{figuras}"
    assert "bajo la farola y conversan mirando las estrellas" in avisos[ADMIN].texto
    juego.boton(ANA, "", "fotos")  # Ana prefiere sin dibujos (gasta menos datos)
    assert "Con dibujos (gastan algo más de datos): <b>No</b>" in juego.boton(ANA, "", "ajustes").pantalla.texto
    reloj.t = inicio + 9.5 * 60
    avisos = {a.para: a for a in juego.tick().avisos if a.silencio}
    assert avisos[ANA].foto is None and avisos[ADMIN].foto.startswith("ilus:parque_regreso:noche:")


def test_el_bot_sube_el_dibujo_una_vez_y_despues_lo_reusa():
    async def probar():
        tg = TelegramFalso()
        cfg = Config(token="123:ABC", admins=frozenset({ADMIN}))
        juego = Juego(DB(":memory:"), cfg, rng=random.Random(3))
        bot = BotSimPareja(juego, cfg)
        app = bot.construir(peticiones=tg)
        await app.initialize()
        aviso = Aviso(ADMIN, "🪑 Se sientan en una banca…", foto="ilus:parque_banca:noche:hm", silencio=True)
        assert await bot._enviar_aviso(app.bot, aviso, None)
        assert await bot._enviar_aviso(app.bot, aviso, None)
        fotos = [d for m, d in tg.llamadas if m == "sendPhoto"]
        assert len(fotos) == 2 and fotos[0]["disable_notification"]
        assert fotos[1]["photo"] == juego.db.meta("ilusid:parque_banca:noche:hm")  # la segunda vez, sin subirla
        await app.shutdown()

    asyncio.run(probar())
