"""Adaptador de Telegram: traduce mensajes y botones a llamadas del `Juego`."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from telegram import (
    Bot,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LinkPreviewOptions,
    Message,
    ReplyKeyboardMarkup,
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

from . import ilustraciones as IL
from . import imagenes_ia as IA
from . import teclado as TK
from .config import Config
from .juego import Aviso, Botones, Juego, Pantalla, Resultado

log = logging.getLogger(__name__)

COMANDOS = [
    BotCommand("start", "Entrar o seguir jugando"),
    BotCommand("menu", "Menú principal"),
    BotCommand("sim", "Tu Sim: necesidades y acciones"),
    BotCommand("trabajo", "Tu trabajo: horas, sueldo y ascensos"),
    BotCommand("super", "Comprar ingredientes"),
    BotCommand("cocina", "Cocinar paso a paso"),
    BotCommand("nevera", "Nevera, despensa y comida hecha"),
    BotCommand("dinero", "Cartera, cuenta compartida y facturas"),
    BotCommand("casa", "Tu casa: el plano y dónde está cada uno"),
    BotCommand("plano", "El plano de la casa: dónde está cada uno"),
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
COMANDOS_MENU = ["plano", "sim", "trabajo", "super", "cocina", "nevera", "dinero", "casa", "sala", "menu", "invitar", "personajes", "animo", "ajustes", "conexion", "salir"]

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


def teclado_abajo(filas: list[TK.Fila]) -> ReplyKeyboardMarkup | None:
    """Los botones debajo de la barra de escribir, siempre visibles."""
    if not filas:
        return None
    return ReplyKeyboardMarkup(
        [[KeyboardButton(texto) for texto, _ in fila] for fila in filas],
        resize_keyboard=True, is_persistent=True, input_field_placeholder="Escribe aquí a tu pareja…",
    )


class BotSimPareja:
    def __init__(self, juego: Juego, cfg: Config, imagenes: IA.ImagenesIA | None = None):
        self.juego = juego
        self.cfg = cfg
        if imagenes is None:
            generar = (IA.generador_openai(cfg.openai_key, cfg.imagen_modelo, cfg.imagen_calidad)
                       if cfg.openai_key else None)
            imagenes = IA.ImagenesIA(juego.db, Path(cfg.db_ruta).parent / "imagenes", cfg.imagenes_por_dia, generar)
        self.imagenes = imagenes
        self._en_curso: set[asyncio.Task] = set()  # fotos que llegan cuando la IA termina

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
        log.info("Fotos de anime: %s", f"{self.cfg.imagen_modelo}, hasta {self.cfg.imagenes_por_dia} nuevas al día"
                 if self.imagenes.activa else "apagadas (falta OPENAI_API_KEY): los mensajitos van solo con texto")
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
        msg = update.effective_message
        dato = TK.buscar(self._teclado(u.id), msg.text) if self.cfg.botones_abajo else None
        if dato is not None:  # tocó un botón de abajo
            await self._borrar(context.bot, u.id, msg.message_id)
            res = self.juego.boton(u.id, u.first_name or "", dato)
            await self._aplicar(update, context, res, alerta=True)
            return
        res = self.juego.texto(u.id, u.first_name or "", msg.text)
        await self._aplicar(update, context, res)

    async def _media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        foto = msg.photo[-1].file_id if msg.photo else None  # la de mayor tamaño
        await self._aplicar(update, context, self.juego.media(update.effective_user.id, foto, msg.caption or ""))

    async def _boton(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        res = self.juego.boton(q.from_user.id, q.from_user.first_name or "", q.data or "")
        await q.answer(res.alerta)
        if self.cfg.botones_abajo and q.message is not None and res.pantalla is not None:
            try:  # un mensaje viejo con botones pegados: se le quitan, ahora van abajo
                await q.edit_message_reply_markup(None)
            except TelegramError:
                pass
        await self._aplicar(update, context, res)

    async def _tick(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._aplicar(None, context, self.juego.tick())

    async def _error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("Error procesando una actualización", exc_info=context.error)

    # --- salida ----------------------------------------------------------

    async def _aplicar(self, update: Update | None, context: ContextTypes.DEFAULT_TYPE, res: Resultado,
                       alerta: bool = False) -> None:
        """`alerta`: el aviso corto del botón va como mensaje (con los botones de abajo no hay ventanita)."""
        if alerta and res.alerta and res.pantalla is None and update is not None:
            await context.bot.send_message(update.effective_user.id, f"ℹ️ {res.alerta}")
        if res.pantalla is not None and update is not None:
            await self._mostrar(update, context, res, alerta)
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
        for clave in self.juego.pedir_fotos():  # las fotos que van a hacer falta: que la IA empiece ya
            if not self.juego.db.meta(f"ilusid:{clave}"):
                self.imagenes.pedir(clave)

    async def _mostrar(self, update: Update, context: ContextTypes.DEFAULT_TYPE, res: Resultado,
                       alerta: bool = False) -> None:
        if self.cfg.botones_abajo:
            await self._mostrar_abajo(update, context, res, alerta)
            return
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
        self.juego.registrar_pantalla(uid, msg_id, p.es_sala, p.clave)

    # --- botones abajo ---------------------------------------------------------

    def _teclado(self, uid: int) -> dict:
        return json.loads(self.juego.db.meta(f"teclado:{uid}") or "{}")

    def _guardar_teclado(self, uid: int, estado: dict) -> None:
        self.juego.db.guardar_meta(f"teclado:{uid}", json.dumps(estado, ensure_ascii=False))

    async def _borrar(self, bot: Bot, uid: int, msg_id: int | None) -> None:
        if msg_id:
            try:
                await bot.delete_message(uid, msg_id)
            except TelegramError:
                pass  # ya no existe o es muy viejo: no pasa nada

    async def _mostrar_abajo(self, update: Update, context: ContextTypes.DEFAULT_TYPE, res: Resultado,
                             alerta: bool) -> None:
        """La pantalla va en un mensaje nuevo con sus botones abajo; la anterior se borra."""
        p: Pantalla = res.pantalla
        uid = update.effective_user.id
        filas, enlaces = TK.separar(p.botones)
        texto = TK.texto_con_enlaces(p.texto, enlaces)
        if alerta and res.alerta:
            texto = f"ℹ️ {res.alerta}\n\n{texto}"
        estado = self._teclado(uid)
        estado["extra"] = []
        if filas:
            estado["filas"] = filas
            anterior = estado.get("msg")
            await self._borrar(context.bot, uid, anterior)
            if anterior:
                self.juego.olvidar_pantalla(uid, anterior)
        m = await context.bot.send_message(uid, texto, reply_markup=teclado_abajo(TK.mostrar([], estado.get("filas", []))))
        if filas:  # una pantalla sin botones (un resultado) no reemplaza a la anterior
            estado["msg"] = m.message_id
            self.juego.registrar_pantalla(uid, m.message_id, p.es_sala, p.clave)
        self._guardar_teclado(uid, estado)

    async def _enviar_aviso(self, bot: Bot, aviso: Aviso, original: Message | None) -> bool:
        if self.cfg.botones_abajo and aviso.botones and not aviso.copiar:
            filas, enlaces = TK.separar(aviso.botones)
            texto = TK.texto_con_enlaces(aviso.texto, enlaces)
            markup = None
            if filas:  # lo que pregunta el aviso va arriba de los botones de la pantalla
                estado = self._teclado(aviso.para)
                estado["extra"] = filas
                self._guardar_teclado(aviso.para, estado)
                markup = teclado_abajo(TK.mostrar(filas, estado.get("filas", [])))
            try:
                if aviso.foto:
                    await self._enviar_foto(bot, aviso.para, aviso.foto, texto, markup, aviso.silencio, aviso.solo_foto)
                else:
                    await bot.send_message(aviso.para, texto, reply_markup=markup, disable_notification=aviso.silencio)
                return True
            except Forbidden:
                log.info("El usuario %s bloqueó el bot", aviso.para)
            except TelegramError as e:
                log.warning("No se pudo avisar a %s: %s", aviso.para, e)
            return False
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
            elif aviso.foto:
                await self._enviar_foto(bot, aviso.para, aviso.foto, aviso.texto, teclado(aviso.botones),
                                        aviso.silencio, aviso.solo_foto)
            else:
                await bot.send_message(aviso.para, aviso.texto, reply_markup=teclado(aviso.botones),
                                       disable_notification=aviso.silencio)
            return True
        except Forbidden:
            log.info("El usuario %s bloqueó el bot", aviso.para)
        except TelegramError as e:
            log.warning("No se pudo avisar a %s: %s", aviso.para, e)
        return False

    async def _enviar_foto(self, bot: Bot, para: int, foto: str, texto: str, markup, silencio: bool,
                           solo_foto: bool = False) -> None:
        """Una foto de Telegram (file_id) o una foto de anime «ilus:…» hecha por la IA.

        Si la foto de la IA todavía no está, el texto sale ya y la foto llega sola cuando la IA termine. Sin IA
        (o sin fotos por hoy) va solo el texto; un aviso `solo_foto` entonces no se manda.
        """
        clave = foto[len("ilus:"):] if foto.startswith("ilus:") else None
        if clave is None:
            await bot.send_photo(para, foto, caption=texto, reply_markup=markup, disable_notification=silencio)
            return
        if await self._foto_hecha(bot, para, clave, texto, markup, silencio):
            return
        tarea = self.imagenes.pedir(clave)
        if not solo_foto:
            await bot.send_message(para, texto, reply_markup=markup, disable_notification=silencio)
        if tarea is not None:
            pie = texto if solo_foto else "📸 La foto de este momento"
            seguir = asyncio.create_task(self._foto_tarde(bot, para, clave, tarea, pie, silencio))
            self._en_curso.add(seguir)
            seguir.add_done_callback(self._en_curso.discard)

    async def _foto_hecha(self, bot: Bot, para: int, clave: str, pie: str, markup, silencio: bool) -> bool:
        """Manda la foto si ya está hecha: por su file_id de Telegram o, la primera vez, subiéndola."""
        espiar = IL.es_intima(clave)  # la íntima llega tapada hasta que la tocas
        guardada = self.juego.db.meta(f"ilusid:{clave}")
        if guardada:
            try:
                await bot.send_photo(para, guardada, caption=pie, reply_markup=markup, disable_notification=silencio,
                                     has_spoiler=espiar)
                return True
            except BadRequest:
                pass  # ya no sirve: se vuelve a subir
        jpeg = self.imagenes.lista(clave)
        if jpeg is None:
            return False
        m = await bot.send_photo(para, jpeg, caption=pie, reply_markup=markup, disable_notification=silencio,
                                 has_spoiler=espiar)
        if m.photo:
            self.juego.db.guardar_meta(f"ilusid:{clave}", m.photo[-1].file_id)
        return True

    async def _foto_tarde(self, bot: Bot, para: int, clave: str, tarea: asyncio.Task, pie: str,
                          silencio: bool) -> None:
        if await tarea is None:
            return
        try:
            await self._foto_hecha(bot, para, clave, pie, None, silencio)
        except TelegramError as e:
            log.warning("No se pudo mandar la foto a %s: %s", para, e)

    async def _editar(self, bot: Bot, uid: int, msg_id: int, p: Pantalla) -> None:
        try:
            await bot.edit_message_text(  # con los botones abajo, solo se actualiza el texto
                p.texto, chat_id=uid, message_id=msg_id,
                reply_markup=None if self.cfg.botones_abajo else teclado(p.botones),
            )
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                self.juego.olvidar_pantalla(uid, msg_id)
        except Forbidden:
            self.juego.olvidar_pantalla(uid, msg_id)
        except TelegramError as e:
            log.warning("No se pudo actualizar la sala de %s: %s", uid, e)
