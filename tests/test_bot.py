"""Recorrido completo a través del adaptador de Telegram, con la API de Telegram simulada."""

import asyncio
import json
import random

from telegram import Update
from telegram.request import BaseRequest

from simpareja.bot import BotSimPareja
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Juego

ADMIN, ANA = 1000, 2000


class TelegramFalso(BaseRequest):
    def __init__(self):
        self.llamadas = []
        self._msg = 100

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    @property
    def read_timeout(self):
        return 5

    async def do_request(self, url, method, request_data=None, **kwargs):
        metodo = url.rsplit("/", 1)[-1]
        datos = request_data.parameters if request_data else {}
        self.llamadas.append((metodo, datos))
        if metodo == "getMe":
            r = {"id": 999, "is_bot": True, "first_name": "Sims", "username": "sims000bot"}
        elif metodo in ("sendMessage", "editMessageText"):
            self._msg += 1
            r = {
                "message_id": datos.get("message_id", self._msg), "date": 0,
                "chat": {"id": datos["chat_id"], "type": "private"}, "text": datos["text"],
            }
        elif metodo == "copyMessage":
            self._msg += 1
            r = {"message_id": self._msg}
        else:
            r = True
        return 200, json.dumps({"ok": True, "result": r}).encode()

    def enviados(self, metodo, chat_id):
        return [d for m, d in self.llamadas if m == metodo and d.get("chat_id") == chat_id]


def mensaje(uid, texto, upd_id):
    return {
        "update_id": upd_id,
        "message": {
            "message_id": upd_id, "date": 0, "text": texto,
            "chat": {"id": uid, "type": "private"},
            "from": {"id": uid, "is_bot": False, "first_name": f"u{uid}"},
            **({"entities": [{"type": "bot_command", "offset": 0, "length": len(texto.split()[0])}]}
               if texto.startswith("/") else {}),
        },
    }


def boton(uid, data, msg_id, upd_id):
    return {
        "update_id": upd_id,
        "callback_query": {
            "id": str(upd_id), "chat_instance": "x", "data": data,
            "from": {"id": uid, "is_bot": False, "first_name": f"u{uid}"},
            "message": {"message_id": msg_id, "date": 0, "text": "…", "chat": {"id": uid, "type": "private"}},
        },
    }


def test_recorrido_por_telegram():
    asyncio.run(_recorrido())


async def _recorrido():
    tg = TelegramFalso()
    cfg = Config(token="123:ABC", admins=frozenset({ADMIN}))
    juego = Juego(DB(":memory:"), cfg, rng=random.Random(3))
    bot = BotSimPareja(juego, cfg)
    app = bot.construir(peticiones=tg)
    await app.initialize()
    await bot._al_iniciar(app)
    n = iter(range(1, 1000))

    async def enviar(upd):
        await app.process_update(Update.de_json(upd, app.bot))

    # El admin crea su personaje con todo al azar
    await enviar(mensaje(ADMIN, "/start", next(n)))
    await enviar(mensaje(ADMIN, "Luis", next(n)))
    ultimo = tg.enviados("sendMessage", ADMIN)[-1]
    await enviar(boton(ADMIN, "apr", ultimo.get("message_id", 101), next(n)))
    await enviar(boton(ADMIN, "apok", 101, next(n)))
    assert "Personaje creado" in tg.enviados("sendMessage", ADMIN)[-1]["text"]

    # Abre la sala (queda registrada para actualizarse en vivo) y genera una invitación
    await enviar(mensaje(ADMIN, "/sala", next(n)))
    sala_admin = juego.db.jugador(ADMIN).msg_sala
    assert sala_admin
    await enviar(boton(ADMIN, "inv:pareja", 500, next(n)))
    invitacion = tg.llamadas[-1][1]["text"]
    assert "https://t.me/sims000bot?start=" in invitacion
    codigo = invitacion.split("?start=")[1].split()[0]
    # editar el mensaje 500 (que no era la sala) no rompe la sala en vivo
    assert juego.db.jugador(ADMIN).msg_sala == sala_admin

    # Ana entra por el enlace
    await enviar(mensaje(ANA, f"/start {codigo}", next(n)))
    assert any("abrió tu invitación" in d["text"] for d in tg.enviados("sendMessage", ADMIN))
    await enviar(mensaje(ANA, "Ana", next(n)))
    await enviar(boton(ANA, "apr", 600, next(n)))
    await enviar(boton(ANA, "apok", 600, next(n)))
    assert any("entró a tu sala" in d["text"] for d in tg.enviados("sendMessage", ADMIN))
    # la sala abierta del admin se actualizó sola mostrando a Ana en línea
    ediciones = [d for d in tg.enviados("editMessageText", ADMIN) if d["message_id"] == sala_admin]
    assert "Ana</b> — 🟢 en línea" in ediciones[-1]["text"]

    # Chat interno
    await enviar(mensaje(ANA, "te extraño 💞", next(n)))
    assert tg.enviados("sendMessage", ADMIN)[-1]["text"].endswith("<b>Ana</b>: te extraño 💞")

    await app.shutdown()
