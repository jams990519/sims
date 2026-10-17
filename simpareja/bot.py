"""Adaptador de Telegram: traduce mensajes y botones a llamadas del `Juego`."""

from __future__ import annotations

import asyncio
import logging

from telegram import (
    Bot,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

from .config import Config
from .juego import Aviso, Botones, Juego, Pantalla, Resultado

log = logging.getLogger(__name__)

COMANDOS = [
    BotCommand("start", "Entrar o seguir jugando"),
    BotCommand("sim", "Tu Sim: necesidades y acciones"),
    BotCommand("trabajo", "Tu trabajo: horas, sueldo y ascensos"),
    BotCommand("super", "Comprar ingredientes"),
    BotCommand("cocina", "Cocinar paso a paso"),
    BotCommand("nevera", "Nevera, despensa y comida hecha"),
    BotCommand("dinero", "Cartera, cuenta compartida y facturas"),
    BotCommand("casa", "Tu casa y sus servicios"),
    BotCommand("sala", "Ver tu sala y quién está en línea"),
    BotCommand("invitar", "Invitar a un jugador"),
    BotCommand("personajes", "Ver los personajes de la sala"),
    BotCommand("animo", "Cambiar tu estado de ánimo"),
    BotCommand("ajustes", "Ajustes"),
    BotCommand("conexion", "Ver tu última conexión guardada"),
    BotCommand("novedades", "Qué trae la última actualización"),
    BotCommand("salir", "Salir y dejar tu Sim en pausa"),
    BotCommand("ayuda", "Cómo funciona"),
]
COMANDOS_MENU = ["sim", "trabajo", "super", "cocina", "nevera", "dinero", "casa", "sala", "menu", "invitar", "personajes", "animo", "ajustes", "conexion", "salir"]

# Tipos de mensaje que admiten pie de foto: se reenvían con el nombre en el pie.
_CON_PIE = ("photo", "video", "animation", "audio", "document", "voice")


def teclado(botones: Botones) -> InlineKeyboardMarkup | None:
    if not botones:
        return None
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(texto, url=dato)
            if dato.startswith(("https://", "http://"))
            else InlineKeyboardButton(texto, callback_data=dato)
            for texto, dato in fila
        ]
        for fila in botones
    ])


class BotSimPareja:
    def __init__(self, juego: Juego, cfg: Config):
        self.juego = juego
        self.cfg = cfg

    def construir(self, peticiones=None) -> Application:
        """`peticiones` permite inyectar un cliente HTTP falso en las pruebas."""
        constructor = (
            Application.builder()
            .token(self.cfg.token)
            .defaults(Defaults(
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True),  # ahorra datos
            ))
            .post_init(self._al_iniciar)
        )
        if self.cfg.api_url:
            base = self.cfg.api_url.rstrip("/")
            constructor = constructor.base_url(f"{base}/bot").base_file_url(f"{base}/file/bot")
        if peticiones is not None:
            constructor = constructor.request(peticiones).get_updates_request(peticiones)
        elif self.cfg.proxy:
            constructor = constructor.proxy(self.cfg.proxy).get_updates_proxy(self.cfg.proxy)
        app = constructor.build()

        privado = filters.ChatType.PRIVATE
        app.add_handler(CommandHandler("start", self._start, filters=privado))
        app.add_handler(CommandHandler("ayuda", self._ayuda, filters=privado))
        app.add_handler(CommandHandler("novedades", self._novedades, filters=privado))
        app.add_handler(CommandHandler(COMANDOS_MENU, self._comando, filters=privado))
        # /invitar_CÓDIGO llega como un comando con otro nombre: se trata como texto.
        app.add_handler(MessageHandler(privado & filters.Regex(r"(?i)^/invitar_\w+"), self._texto))
        app.add_handler(CallbackQueryHandler(self._boton))
        app.add_handler(MessageHandler(privado & filters.TEXT & ~filters.COMMAND, self._texto))
        app.add_handler(MessageHandler(
            privado & ~filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.ALL, self._media
        ))
        app.add_error_handler(self._error)
        app.job_queue.run_repeating(self._tick, interval=60, first=30)
        return app

    async def _al_iniciar(self, app: Application) -> None:
        self.juego.bot_usuario = app.bot.username
        await app.bot.set_my_commands(COMANDOS)
        log.info("Bot @%s listo", app.bot.username)
        res = self.juego.anunciar_novedades()
        for aviso in res.avisos:
            await self._enviar_aviso(app.bot, aviso, None)
            await asyncio.sleep(0.05)  # respeta el límite de mensajes de Telegram
        if res.avisos:
            log.info("Novedades anunciadas a %d jugadores", len(res.avisos))

    # --- manejadores -----------------------------------------------------

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        u = update.effective_user
        carga = context.args[0] if context.args else None
        await self._aplicar(update, context, self.juego.inicio(u.id, u.first_name or "", carga))

    async def _ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._aplicar(update, context, Resultado(pantalla=self.juego.ayuda(), nuevo=True))

    async def _novedades(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._aplicar(update, context, Resultado(pantalla=self.juego.novedades(), nuevo=True))

    async def _comando(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        u = update.effective_user
        nombre = update.effective_message.text.split()[0].lstrip("/").split("@")[0].lower()
        res = self.juego.comando(u.id, u.first_name or "", nombre, context.args)
        await self._aplicar(update, context, res)

    async def _texto(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        u = update.effective_user
        res = self.juego.texto(u.id, u.first_name or "", update.effective_message.text)
        await self._aplicar(update, context, res)

    async def _media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._aplicar(update, context, self.juego.media(update.effective_user.id))

    async def _boton(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        res = self.juego.boton(q.from_user.id, q.from_user.first_name or "", q.data or "")
        await q.answer(res.alerta)
        await self._aplicar(update, context, res)

    async def _tick(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._aplicar(None, context, self.juego.tick())

    async def _error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("Error procesando una actualización", exc_info=context.error)

    # --- salida ----------------------------------------------------------

    async def _aplicar(self, update: Update | None, context: ContextTypes.DEFAULT_TYPE, res: Resultado) -> None:
        if res.pantalla is not None and update is not None:
            await self._mostrar(update, context, res)
        original = update.effective_message if update else None
        fallidos = []
        for aviso in res.avisos:
            if not await self._enviar_aviso(context.bot, aviso, original) and aviso.chat:
                fallidos.append(aviso.para)
        if fallidos and update is not None:
            await context.bot.send_message(
                update.effective_user.id,
                "⚠️ No pude entregar tu mensaje: la otra persona bloqueó o cerró el bot.",
            )
        for ed in res.ediciones:
            await self._editar(context.bot, ed.para, ed.msg_id, ed.pantalla)

    async def _mostrar(self, update: Update, context: ContextTypes.DEFAULT_TYPE, res: Resultado) -> None:
        p: Pantalla = res.pantalla
        uid = update.effective_user.id
        q = update.callback_query
        msg_id = None
        if q is not None and q.message is not None and not res.nuevo:
            try:
                await q.edit_message_text(p.texto, reply_markup=teclado(p.botones))
                msg_id = q.message.message_id
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    msg_id = q.message.message_id
                else:
                    log.info("No se pudo editar, envío mensaje nuevo: %s", e)
        if msg_id is None:
            m = await context.bot.send_message(uid, p.texto, reply_markup=teclado(p.botones))
            msg_id = m.message_id
        self.juego.registrar_pantalla(uid, msg_id, p.es_sala)

    async def _enviar_aviso(self, bot: Bot, aviso: Aviso, original: Message | None) -> bool:
        try:
            if aviso.copiar and original is not None:
                pie = original.caption_html or ""
                if any(getattr(original, t) for t in _CON_PIE) and len(original.caption or "") < 900:
                    await bot.copy_message(
                        aviso.para, original.chat_id, original.message_id,
                        caption=f"{aviso.texto}\n{pie}".strip(),
                    )
                else:
                    await bot.send_message(aviso.para, aviso.texto)
                    await bot.copy_message(aviso.para, original.chat_id, original.message_id)
            else:
                await bot.send_message(aviso.para, aviso.texto, reply_markup=teclado(aviso.botones))
            return True
        except Forbidden:
            log.info("El usuario %s bloqueó el bot", aviso.para)
        except TelegramError as e:
            log.warning("No se pudo avisar a %s: %s", aviso.para, e)
        return False

    async def _editar(self, bot: Bot, uid: int, msg_id: int, p: Pantalla) -> None:
        try:
            await bot.edit_message_text(
                p.texto, chat_id=uid, message_id=msg_id, reply_markup=teclado(p.botones)
            )
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                self.juego.olvidar_pantalla(uid, msg_id)
        except Forbidden:
            self.juego.olvidar_pantalla(uid, msg_id)
        except TelegramError as e:
            log.warning("No se pudo actualizar la sala de %s: %s", uid, e)
