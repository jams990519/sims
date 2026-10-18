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
        elif metodo == "sendPhoto":
            self._msg += 1
            r = {
                "message_id": self._msg, "date": 0, "chat": {"id": datos["chat_id"], "type": "private"},
                "photo": [{"file_id": datos["photo"], "file_unique_id": "u", "width": 1, "height": 1}],
                "caption": datos.get("caption", ""),
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


def foto(uid, file_id, pie, upd_id):
    return {
        "update_id": upd_id,
        "message": {
            "message_id": upd_id, "date": 0, "caption": pie,
            "photo": [
                {"file_id": f"{file_id}_chica", "file_unique_id": "a", "width": 90, "height": 90},
                {"file_id": file_id, "file_unique_id": "b", "width": 800, "height": 800},
            ],
            "chat": {"id": uid, "type": "private"},
            "from": {"id": uid, "is_bot": False, "first_name": f"u{uid}"},
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


def botones(datos):
    markup = datos.get("reply_markup") or {}
    if isinstance(markup, str):
        markup = json.loads(markup)
    return [b.get("callback_data") for fila in markup.get("inline_keyboard", []) for b in fila]


async def _recorrido():
    tg = TelegramFalso()
    cfg = Config(token="123:ABC", admins=frozenset({ADMIN}), botones_abajo=False)  # botones en los mensajes
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
    await enviar(boton(ADMIN, "apr", 101, next(n)))
    await enviar(boton(ADMIN, "apok", 101, next(n)))
    assert "Personaje creado" in tg.enviados("sendMessage", ADMIN)[-1]["text"]

    # Abre la sala: queda registrada para actualizarse en vivo
    await enviar(mensaje(ADMIN, "/sala", next(n)))
    sala_admin = juego.db.jugador(ADMIN).msg_sala
    assert sala_admin

    # Ana abre el bot y recibe su código personal
    await enviar(mensaje(ANA, "/start", next(n)))
    candado = tg.enviados("sendMessage", ANA)[-1]["text"]
    codigo = candado.split("invitar_")[1].split("<")[0]

    # Luis escribe /invitar_CÓDIGO y elige invitarla como pareja
    await enviar(mensaje(ADMIN, f"/invitar_{codigo}", next(n)))
    assert f"invc:{codigo}:pareja" in botones(tg.enviados("sendMessage", ADMIN)[-1])
    await enviar(boton(ADMIN, f"invc:{codigo}:pareja", 500, next(n)))
    invitacion = tg.enviados("sendMessage", ANA)[-1]
    assert "te invitó" in invitacion["text"]
    acepto = next(d for d in botones(invitacion) if d and d.startswith("acepto:"))

    # Ana acepta, crea su personaje y entra a la sala de Luis
    await enviar(boton(ANA, acepto, 600, next(n)))
    await enviar(mensaje(ANA, "Ana", next(n)))
    await enviar(boton(ANA, "apr", 600, next(n)))
    await enviar(boton(ANA, "apok", 600, next(n)))
    assert any("entró a tu sala" in d["text"] for d in tg.enviados("sendMessage", ADMIN))
    # la sala abierta de Luis se actualizó sola mostrando a Ana en línea
    ediciones = [d for d in tg.enviados("editMessageText", ADMIN) if d["message_id"] == sala_admin]
    assert "Ana</b> · " in ediciones[-1]["text"] and "🟢 en línea" in ediciones[-1]["text"]

    # Chat interno
    await enviar(mensaje(ANA, "te extraño 💞", next(n)))
    texto = tg.enviados("sendMessage", ADMIN)[-1]["text"]
    assert "<b>Ana</b>" in texto and texto.endswith(": te extraño 💞")

    # Ana cambia su ánimo con foto y frase: a Luis le llega la foto (la grande) con la frase
    await enviar(boton(ANA, "animo:coqueto", 600, next(n)))
    await enviar(foto(ANA, "FOTO123", "pensando en ti", next(n)))
    envio = tg.enviados("sendPhoto", ADMIN)[-1]
    assert envio["photo"] == "FOTO123" and "«pensando en ti»" in envio["caption"]
    assert not tg.enviados("copyMessage", ADMIN)  # no se reenvió como chat
    # Luis la vuelve a ver desde el perfil
    await enviar(boton(ADMIN, f"fotoan:{ANA}", 700, next(n)))
    assert tg.enviados("sendPhoto", ADMIN)[-1]["photo"] == "FOTO123"
    # una foto cualquiera, sin acabar de elegir ánimo, va al chat
    await enviar(foto(ANA, "OTRA", "", next(n)))
    assert tg.enviados("copyMessage", ADMIN)
    await app.shutdown()

    # Al arrancar una versión nueva se anuncian las novedades a los dos (una sola vez)
    juego.db.guardar_meta("version_anunciada", "0.0")
    await bot._al_iniciar(app)
    for uid in (ADMIN, ANA):
        assert "se actualizó a la versión" in tg.enviados("sendMessage", uid)[-1]["text"]
    antes = len(tg.llamadas)
    await bot._al_iniciar(app)
    assert not [m for m, _ in tg.llamadas[antes:] if m == "sendMessage"]


def teclado_de(datos):
    markup = datos.get("reply_markup") or {}
    return json.loads(markup) if isinstance(markup, str) else markup


def test_botones_abajo():
    asyncio.run(_botones_abajo())


async def _botones_abajo():
    tg = TelegramFalso()
    cfg = Config(token="123:ABC", admins=frozenset({ADMIN}))  # por defecto, los botones van abajo
    juego = Juego(DB(":memory:"), cfg, rng=random.Random(3))
    bot = BotSimPareja(juego, cfg)
    app = bot.construir(peticiones=tg)
    await app.initialize()
    n = iter(range(1, 1000))

    async def enviar(upd):
        await app.process_update(Update.de_json(upd, app.bot))

    def tocar_dato(uid, dato):
        return next(t for fila in bot._teclado(uid)["filas"] for t, d in fila if d == dato)

    await enviar(mensaje(ADMIN, "/start", next(n)))
    await enviar(mensaje(ADMIN, "Luis", next(n)))
    markup = teclado_de(tg.enviados("sendMessage", ADMIN)[-1])
    assert markup["is_persistent"] and markup["resize_keyboard"] and markup["keyboard"]
    assert "inline_keyboard" not in markup  # nada pegado al mensaje: todo abajo

    # Tocar un botón de abajo manda su texto: el bot lo reconoce, borra el toque y la pantalla anterior
    anterior = bot._teclado(ADMIN)["msg"]
    toque = next(n)
    await enviar(mensaje(ADMIN, tocar_dato(ADMIN, "ap:genero:?"), toque))
    borrados = [d["message_id"] for d in tg.enviados("deleteMessage", ADMIN)]
    assert toque in borrados and anterior in borrados
    assert "genero" in juego.db.jugador(ADMIN).borrador  # el toque eligió el género al azar
    # los botones viejos pegados a un mensaje siguen funcionando
    await enviar(boton(ADMIN, "apr", 101, next(n)))
    await enviar(boton(ADMIN, "apok", 101, next(n)))
    assert "Personaje creado" in tg.enviados("sendMessage", ADMIN)[-1]["text"]
    assert juego.db.jugador(ADMIN).estado == "activo"

    # Los botones con enlace (pasar el bot) van en el texto, como enlaces
    await enviar(mensaje(ADMIN, "/invitar", next(n)))
    await enviar(mensaje(ADMIN, tocar_dato(ADMIN, "invq"), next(n)))
    await enviar(mensaje(ADMIN, tocar_dato(ADMIN, "invq:pareja"), next(n)))
    assert '<a href="https://t.me/share/url?' in tg.enviados("sendMessage", ADMIN)[-1]["text"]

    # Un aviso que pregunta algo pone sus botones arriba, sin quitar los de la pantalla (y con 🎮 Menú)
    await enviar(mensaje(ANA, "/start", next(n)))
    await enviar(mensaje(ADMIN, f"/invitar_{ANA}", next(n)))
    await enviar(mensaje(ADMIN, tocar_dato(ADMIN, f"invc:{ANA}:pareja"), next(n)))
    invitacion = tg.enviados("sendMessage", ANA)[-1]
    etiquetas = [b["text"] for fila in teclado_de(invitacion)["keyboard"] for b in fila]
    assert "✅ Aceptar y crear mi personaje" in etiquetas and "🎮 Menú" in etiquetas
    await enviar(mensaje(ANA, "✅ Aceptar y crear mi personaje", next(n)))
    assert juego.db.jugador(ANA).estado == "nombrando"

    # Lo que no es un botón sigue siendo chat: un aviso corto del botón llega como mensaje
    res_alerta = [d["text"] for d in tg.enviados("sendMessage", ADMIN) if d["text"].startswith("ℹ️")]
    await enviar(mensaje(ADMIN, tocar_dato(ADMIN, "invs"), next(n)))
    assert "Invitaciones enviadas" in tg.enviados("sendMessage", ADMIN)[-1]["text"]
    assert res_alerta == []
    await app.shutdown()
