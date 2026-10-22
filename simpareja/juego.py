"""Lógica del juego, separada de Telegram para poder probarla sin conexión.

Cada entrada (comando, texto, botón) devuelve un `Resultado` que el bot traduce a
mensajes de Telegram: la pantalla para quien tocó, avisos para otras personas y
ediciones de las salas abiertas (para que el estado "en línea" se vea en vivo).
"""

from __future__ import annotations

import functools
import html
import json
import logging
import random
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote

from . import novedades as N
from . import personaje as P
from . import vida as V
from . import zonas as Z
from .config import Config
from .db import DB, Invitacion, Jugador, UltimaConexion, Visitante
from .animo_juego import AnimoMixin
from .boda_juego import BodaMixin
from .aniversario_juego import AniversarioMixin
from .cocina_juego import CocinaMixin
from .dinero_juego import DineroMixin
from .caja_juego import CajaMixin
from .intimo_juego import IntimoMixin
from .narracion_juego import NarracionMixin
from .pausa_juego import EN_PAUSA, PausaMixin, SinPausadas
from .estudios_juego import EstudiosMixin
from .eventos_juego import EventosMixin
from .hitos_juego import HitosMixin
from .influencer_juego import InfluencerMixin
from .mascota_juego import MascotaMixin
from .menus import MenuMixin
from .notas_juego import NotasMixin
from .preguntas_juego import PreguntasMixin
from .relacion_juego import RelacionMixin
from .retos_juego import RetosMixin
from .tiendas_juego import TiendasMixin
from .trabajo_juego import ZONAS_HORARIAS, TrabajoMixin, _hora_en
from .viaje_juego import ViajeMixin
from .vida_juego import VidaMixin

log = logging.getLogger(__name__)

Botones = list[list[tuple[str, str]]]


@dataclass
class Pantalla:
    texto: str
    botones: Botones = field(default_factory=list)
    es_sala: bool = False
    # Clave para volver a construir esta pantalla al reconectarse (None = no se guarda).
    clave: str | None = None


@dataclass
class Aviso:
    para: int
    texto: str
    botones: Botones = field(default_factory=list)
    chat: bool = False  # mensaje del chat interno: si no se entrega, se avisa a quien lo mandó
    copiar: bool = False  # además, copiar el mensaje original (foto, sticker, nota de voz…)
    foto: str | None = None  # file_id de Telegram (o "ilus:…", una foto de la IA): va como foto con el texto de pie
    silencio: bool = False  # llega sin sonido (la narración de las acciones)
    solo_foto: bool = False  # si la foto no se puede hacer, no se manda nada


@dataclass
class Edicion:
    para: int
    msg_id: int
    pantalla: Pantalla


@dataclass
class Resultado:
    pantalla: Pantalla | None = None
    alerta: str | None = None
    nuevo: bool = False  # mostrar en un mensaje nuevo aunque venga de un botón
    avisos: list[Aviso] = field(default_factory=list)
    ediciones: list[Edicion] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)  # lo que pasó mientras no mirabas (va arriba de la pantalla)


ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para que no se confundan
LARGO_CODIGO_INVITACION = 10
NOMBRE_RE = re.compile(r"[^\W\d_][\w '.\-]{1,19}")
INVITAR_RE = re.compile(r"/?invitar[_\s]+([A-Za-z0-9]{4,16})(?:@\w+)?", re.IGNORECASE)
MINUTO = 60
DIA = 86400
AVISO_CONEXION_CADA = 30 * MINUTO
MAX_FALLOS_CODIGO = 8
VENTANA_FALLOS = 15 * MINUTO

SALA = ("🏠 Sala", "sala")
# Quién es la persona invitada. Solo la pareja entra a tu sala; los demás tienen la suya.
VINCULOS = {
    "pareja": ("💞", "Pareja"),
    "familia": ("👨‍👩‍👧", "Familia"),
    "amistad": ("🤝", "Amistad"),
    "trabajo": ("💼", "Trabajo o estudios"),
}
VINCULOS_ANTIGUOS = {"amigo": "amistad"}  # invitaciones de antes de los vínculos


def vinculo(tipo: str) -> str:
    """'💞 Pareja', '👨‍👩‍👧 Familia'…"""
    emoji, nombre = VINCULOS.get(VINCULOS_ANTIGUOS.get(tipo, tipo), VINCULOS["amistad"])
    return f"{emoji} {nombre}"
ESPERA_TEXTO = 10 * 60  # cuánto se espera un texto pedido (un motivo, una respuesta…)
CONTINUAR = ("▶️ Continuar", "continuar")

# Pantallas que se guardan como "última conexión": (lugar, qué estaba haciendo).
LUGARES = {
    "nombre": ("✍️ Nombre del personaje", "eligiendo el nombre de su personaje"),
    "creador": ("🧑‍🎨 Creador de personaje", "creando su personaje"),
    "bienvenida": ("✨ Personaje recién creado", "decidiendo si jugar o invitar"),
    "sala": ("💬 Chat de la sala", "en la sala"),
    "menu": ("🎮 Menú", "en el menú"),
    "mcasa": ("🏠 Casa", "en el menú de la casa"),
    "macc": ("⚡ Acciones", "eligiendo qué hacer"),
    "mlug": ("📍 Lugares", "pensando a dónde salir"),
    "mpar": ("💕 Pareja", "en el menú de pareja"),
    "mest": ("👤 Estado", "mirando su estado"),
    "perfil": ("👀 Perfil de su pareja", "mirando el perfil de su pareja"),
    "carrera": ("📈 Mi carrera", "mirando su carrera"),
    "sim": ("🧍 Mi Sim", "mirando a su Sim"),
    "acc": ("🎬 Acciones", "eligiendo qué hacer"),
    "dinero": ("💰 Dinero", "revisando el dinero"),
    "mover": ("💰 Dinero", "moviendo dinero"),
    "facturas": ("📄 Facturas", "revisando las facturas"),
    "casa": ("🔑 Renta y mudanza", "mirando la renta y los servicios"),
    "plano": ("🏠 Casa", "mirando la casa"),
    "mudanza": ("🚚 Renta y mudanza", "pensando en mudarse"),
    "trabajo": ("💼 Trabajo", "mirando su trabajo"),
    "super": ("🛒 Súper", "en el súper"),
    "nevera": ("🧊 Nevera", "mirando la nevera"),
    "cocina": ("🍳 Cocina", "en la cocina"),
    "invitar": ("💌 Invitar", "invitando a alguien"),
    "invs": ("📋 Invitaciones enviadas", "revisando sus invitaciones"),
    "pjs": ("🪪 Personajes", "mirando los personajes"),
    "animo": ("🎭 Estado de ánimo", "eligiendo su estado de ánimo"),
    "animofoto": ("🎭 Estado de ánimo", "eligiendo la foto de su estado de ánimo"),
    "album": ("📸 Álbum de recuerdos", "mirando el álbum de recuerdos"),
    "medidor": ("💗 Medidor de relación", "mirando el medidor de relación"),
    "relmotivo": ("💗 Medidor de relación", "escribiendo por qué cambió su medidor"),
    "preguntas": ("❓ Preguntas de pareja", "mirando las preguntas de pareja"),
    "pregresp": ("❓ Preguntas de pareja", "respondiendo una pregunta de pareja"),
    "notas": ("📝 Notas en la nevera", "leyendo las notas de la nevera"),
    "notaesc": ("📝 Notas en la nevera", "escribiendo una nota para la nevera"),
    "aniv": ("🎂 Aniversario", "planeando el aniversario"),
    "retos": ("🎯 Retos de la semana", "mirando el reto de la semana"),
    "hitos": ("🏆 Hitos de pareja", "mirando los hitos de pareja"),
    "viaje": ("✈️ Viajes", "planeando un viaje"),
    "comp": ("💍 Compromiso", "pensando en el compromiso"),
    "boda": ("💒 La boda", "planeando la boda"),
    "objetos": ("🪑 Objetos de la casa", "mirando los objetos de la casa"),
    "tienda": ("🛍️ Tienda", "de compras"),
    "mascota": ("🐾 Mascota", "con la mascota"),
    "mascnombre": ("🐾 Mascota", "eligiendo el nombre de la mascota"),
    "influ": ("📱 Influencer", "preparando un video"),
    "estudios": ("📚 Estudios", "mirando sus estudios"),
    "caja": ("🐷 Caja de ahorros", "mirando la caja de ahorros"),
    "intimo": ("💕 Pareja", "en el menú de pareja"),
    "pausa": ("⏸️ Juego en pausa", "con el juego en pausa"),
    "ajustes": ("⚙️ Ajustes", "en los ajustes"),
    "renombrar": ("✏️ Cambiar nombre", "cambiando su nombre"),
}
CHATEANDO = "💬 chateando"


def esc(texto: str) -> str:
    return html.escape(texto, quote=False)


def unir(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def duracion(seg: float) -> str:
    seg = max(0, int(seg))
    if seg < MINUTO:
        return "un momento"
    m = seg // MINUTO
    if m < 60:
        return f"{m} min"
    h = m // 60
    if h < 24:
        return f"{h} h"
    d = h // 24
    return "1 día" if d == 1 else f"{d} días"


def _con_notas(metodo):
    """Pone arriba de la pantalla lo que le pasó al Sim mientras el jugador no miraba."""
    @functools.wraps(metodo)
    def envoltura(self, uid, *args, **kwargs):
        res = metodo(self, uid, *args, **kwargs)
        if res.notas:
            texto = "\n".join(res.notas)
            if res.pantalla is not None:
                res.pantalla.texto = texto + "\n\n" + res.pantalla.texto
            else:
                res.avisos.append(Aviso(uid, texto))
            res.notas = []
        return res
    return envoltura


def normalizar_codigo(texto: str) -> str:
    return re.sub(r"[\s\-]", "", texto).upper()


def en_filas(botones: list[tuple[str, str]], por_fila: int = 2) -> Botones:
    return [botones[i:i + por_fila] for i in range(0, len(botones), por_fila)]


# Respuestas a la pareja que valen aunque el Sim esté en pausa.
RESPUESTAS_EN_PAUSA = ("pj", "intsi", "intno", "into", "intpara")

class Juego(VidaMixin, DineroMixin, TrabajoMixin, CocinaMixin, MenuMixin, AnimoMixin, RelacionMixin, PreguntasMixin,
            NotasMixin, EventosMixin, AniversarioMixin, RetosMixin, HitosMixin, ViajeMixin, BodaMixin, TiendasMixin,
            MascotaMixin, InfluencerMixin, EstudiosMixin, CajaMixin, IntimoMixin, NarracionMixin, PausaMixin):
    def __init__(self, db: DB, cfg: Config, reloj=time.time, rng: random.Random | None = None):
        self.db = db
        self.cfg = cfg
        self.reloj = reloj
        self.rng = rng or random.Random()
        self.bot_usuario = "sims000bot"
        self._fallos: dict[int, list[float]] = {}
        self.por_dibujar: list[str] = []  # fotos que conviene ir haciendo ya (ver pedir_fotos)

    def pedir_fotos(self) -> list[str]:
        """Las fotos que van a hacer falta pronto: el bot se las pide a la IA en segundo plano."""
        claves, self.por_dibujar = list(dict.fromkeys(self.por_dibujar)), []
        return claves

    @property
    def pausa(self) -> float:
        return self.cfg.pausa_min * MINUTO

    # --- hora local de cada jugador ---------------------------------------

    def _local(self, j: Jugador, ts: float | None = None) -> datetime:
        """La hora real del jugador: la de su lugar (con horario de verano) o su hora fija."""
        ts = self.reloj() if ts is None else ts
        return Z.local(ts, j.extras, j.utc_offset, self.cfg.zona_por_defecto)

    def _zona(self, j: Jugador) -> str | None:
        return Z.zona_de(j.extras, j.utc_offset, self.cfg.zona_por_defecto)

    def _dia(self, j: Jugador, ts: float | None = None) -> int:
        """Día del Sim: 1 el día en que se creó (según la hora local del jugador)."""
        return (self._local(j, ts).date() - self._local(j, j.creado).date()).days + 1

    def _hoy(self, j: Jugador, ts: float | None = None) -> int:
        """Número de la fecha local, para comparar días (hoy, ayer…)."""
        return self._local(j, ts).toordinal()

    def _reloj(self, j: Jugador, ts: float | None = None) -> str:
        return V.reloj_texto(self._local(j, ts), self._dia(j, ts))

    def _hora(self, j: Jugador, ts: float) -> str:
        return V.hora_12(self._local(j, ts))

    def _finde(self, j: Jugador, ts: float | None = None) -> bool:
        return V.es_fin_de_semana(self._local(j, ts).weekday())

    def _hora_local(self, j: Jugador, ts: float | None = None) -> float:
        return V.hora_decimal(self._local(j, ts))

    # ------------------------------------------------------------------
    # Entradas desde Telegram
    # ------------------------------------------------------------------

    @_con_notas
    def inicio(self, uid: int, nombre_tg: str, carga: str | None = None) -> Resultado:
        """/start: quien no juega ve su código personal; quien juega retoma donde lo dejó.

        Con un enlace de invitación (start=inv_CÓDIGO), la invitación le llega directamente.
        """
        if carga and carga.lower().startswith("inv_"):
            res = self._abrir_enlace(uid, nombre_tg, normalizar_codigo(carga[4:]))
            if res is not None:
                return res
        j = self.db.jugador(uid)
        if j is None:
            return self._visitante(uid, nombre_tg)
        if j.estado == "activo" and self._congelado(j, self.reloj()):
            return self._pausa(j, nuevo=True)
        return self._reanudar(j)

    @_con_notas
    def texto(self, uid: int, nombre_tg: str, texto: str) -> Resultado:
        j = self.db.jugador(uid)
        if j is None:
            return self._visitante(uid, nombre_tg)
        if j.estado in ("nombrando", "renombrando"):
            res = self._recibir_nombre(j, texto)
        elif j.estado == "creando":
            res = self._tocar(j)
            res.pantalla = self._pantalla_creador(j)
            res.pantalla.texto = "👇 Usa los botones para elegir.\n\n" + res.pantalla.texto
            res.nuevo = True
        else:
            invitar = INVITAR_RE.fullmatch(texto.strip())
            captura = self._texto_esperado(j) if invitar is None else None
            if captura is not None:
                res = self._tocar(j, jugada=False)
                captura(j, texto, res)
                res.nuevo = True
                self._anotar(j.id, res)
                return res
            if invitar is None:
                return self._chat(j, texto)
            res = self._tocar(j)
            self._invitar_codigo(j, invitar.group(1), res)
            res.nuevo = True
        self._anotar(j.id, res)
        return res

    def _texto_esperado(self, j: Jugador):
        """Si la última pantalla pidió escribir algo (la frase del ánimo, un motivo…), quién recibe el texto.

        Si no, el texto es chat con la pareja.
        """
        uc = self.db.ultima_conexion(j.id)
        pantalla = uc.pantalla if uc else ""
        if pantalla == "animofoto" and self._animo_pendiente(j):
            return self._frase_animo
        pendiente = self._extras(j).get("rel_pendiente")
        if pantalla == "relmotivo" and pendiente and self.reloj() - pendiente["ts"] < ESPERA_TEXTO:
            return self._motivo_escrito
        pendiente = self._extras(j).get("preg_pendiente")
        if pantalla == "pregresp" and pendiente and self.reloj() - pendiente["ts"] < ESPERA_TEXTO:
            return self._respuesta_escrita
        pendiente = self._extras(j).get("nota_pendiente")
        if pantalla == "notaesc" and pendiente and self.reloj() - pendiente["ts"] < ESPERA_TEXTO:
            return self._nota_escrita
        pendiente = self._extras(j).get("mascota_nombre")
        if pantalla == "mascnombre" and pendiente and self.reloj() - pendiente["ts"] < ESPERA_TEXTO:
            return self._nombre_mascota
        return None

    @_con_notas
    def media(self, uid: int, foto: str | None = None, pie: str = "") -> Resultado:
        """Foto, sticker, nota de voz, etc.: se reenvía a la sala como parte del chat.

        Si acaba de elegir su estado de ánimo, la foto (`file_id`) y su pie son los del ánimo.
        """
        j = self.db.jugador(uid)
        if j is None:
            return self._visitante(uid, "")
        if not j.activo:
            return Resultado(pantalla=Pantalla("✋ Primero termina de crear tu personaje."), nuevo=True)
        if foto and self._animo_pendiente(j):
            res = self._tocar(j, jugada=False)
            self._publicar_animo(j, foto, pie, res)
            res.nuevo = True
            self._anotar(j.id, res)
            return res
        res = self._tocar(j, jugada=False)
        otros = self._companeros(j)
        if not otros:
            res.pantalla = self._sin_companeros()
            res.nuevo = True
            return res
        for o in otros:
            res.avisos.append(Aviso(o.id, f"💬 {self._firma_animo(j)}:", chat=True, copiar=True))
        self._anotar(j.id, res, CHATEANDO)
        return res

    @_con_notas
    def boton(self, uid: int, nombre_tg: str, data: str) -> Resultado:
        accion, _, arg = data.partition(":")
        j = self.db.jugador(uid)
        if j is None:
            return self._boton_visitante(uid, nombre_tg, accion, arg)
        if j.estado == "nombrando":
            return Resultado(alerta="✍️ Primero escribe el nombre de tu personaje.")
        if accion == "salir":
            return self._salir(j)
        if j.estado == "renombrando":
            j.estado = "activo"
        if accion in ("continuar", "volver"):
            return self._continuar(j)
        # Con el juego de la pareja en pausa solo se puede reanudar, chatear y mirar los ajustes.
        en_pausa = j.estado == "activo" and self._pausa_pareja(j.sala_id) is not None
        if en_pausa and accion not in EN_PAUSA:
            return self._pausa(j)
        # Con el Sim en pausa solo se puede continuar o responder a una propuesta de la pareja.
        if (not en_pausa and j.estado == "activo" and self._congelado(j, self.reloj())
                and accion not in RESPUESTAS_EN_PAUSA):
            return self._pausa(j)
        res = self._tocar(j)
        if j.estado == "creando" and not accion.startswith("ap"):
            res.alerta = "🧑‍🎨 Primero termina de crear tu personaje."
            return res
        if accion.startswith("ap"):
            res = self._creador(j, accion, arg, res)
        else:
            manejador = self._manejadores().get(accion)
            if manejador is None:
                res.alerta = "Ese botón ya no funciona."
                res.pantalla = self._pantalla_sala(j)
            else:
                manejador(j, arg, res)
        self._anotar(j.id, res)
        return res

    def comando(self, uid: int, nombre_tg: str, nombre: str, args: list[str] | None = None) -> Resultado:
        """Comandos de menú (/invitar, /sala, /ajustes…) que abren una pantalla en mensaje nuevo."""
        if nombre == "invitar" and args:
            return self.texto(uid, nombre_tg, f"invitar_{args[0]}")
        if nombre == "conexion":
            j = self.db.jugador(uid)
            if j is None:
                return self._visitante(uid, nombre_tg)
            return Resultado(pantalla=self._pantalla_conexion(j), nuevo=True)
        data = {"sala": "sala", "menu": "menu", "sim": "sim", "dinero": "dinero", "casa": "mcasa", "plano": "plano",
                "trabajo": "trabajo", "super": "super", "nevera": "nevera", "cocina": "cocina",
                "invitar": "invitar", "ajustes": "ajustes",
                "personajes": "pjs", "animo": "animos", "salir": "salir"}.get(nombre, "sala")
        res = self.boton(uid, nombre_tg, data)
        res.nuevo = True
        return res

    def ayuda(self) -> Pantalla:
        return Pantalla(
            f"❓ <b>{esc(self.cfg.nombre_juego)}: cómo funciona</b> · versión {N.VERSION}\n\n"
            "🔐 Se entra <b>solo por invitación</b>: al abrir el bot ves tu código personal, se lo pasas "
            "a quien ya juega y esa persona escribe <code>invitar_TUCÓDIGO</code>.\n"
            "🧑‍🎨 Creas tu personaje: aspecto, rasgos, aspiración y estado de ánimo.\n"
            "🎮 Puedes jugar sin compañía o 💌 invitar a tu pareja a tu sala.\n"
            "🎮 En el <b>Menú</b> están 🏠 Casa, ⚡ Acciones, 📍 Lugares, 💼 Trabajo, 💕 Pareja, 👤 Estado y 💬 Chat. "
            "Cada acción muestra su efecto y su tiempo antes de confirmar; juntos terminan antes.\n"
            "💰 Empiezan con $3.000, rentan una casita ($900 al mes) y pagan renta, facturas y comida. "
            "Cada quien tiene su cartera y hay una cuenta compartida; ahorrando se mudan o compran «nuestra casa».\n"
            "💼 Cada quien elige su trabajo y su horario real: a esa hora tu Sim se va solo, y si están juntos "
            "nunca se les obliga.\n"
            "🛒 Compran ingredientes en el súper y 🍳 cocinan paso a paso: ¡si te pasas de tiempo se quema!\n"
            "💬 En la sala, todo lo que escribas (texto, fotos, stickers, notas de voz) le llega a la otra persona.\n"
            f"🕒 El juego usa tu hora local real. Si pasas {self.cfg.pausa_min} min sin hacer nada, tu Sim se "
            "congela ❄️ (no gasta necesidades); al volver tocas ▶️ Continuar y sigues donde lo dejaste.\n"
            "⏸️ En el Menú, <b>Pausar el juego</b> congela todo para los dos (necesidades, acciones, cocina, "
            "trabajo, facturas y avisos) hasta que cualquiera toque ▶️ Reanudar.\n\n"
            "Comandos: /start · /menu · /plano · /sim · /trabajo · /super · /cocina · /nevera · /dinero · /casa · /sala · /invitar · /personajes · /animo · /ajustes · /conexion · /novedades · /salir",
            [[SALA]],
        )

    def novedades(self) -> Pantalla:
        return Pantalla(self._texto_novedades(N.NOVEDADES[:2], titulo="📢 <b>Novedades</b>"), [[SALA]])

    def anunciar_novedades(self) -> Resultado:
        """Al arrancar una versión nueva, avisa a todos los jugadores de lo que cambió (una sola vez)."""
        anterior = self.db.meta("version_anunciada")
        if anterior == N.VERSION:
            return Resultado()
        self.db.guardar_meta("version_anunciada", N.VERSION)
        cambios = N.desde(anterior)
        if not cambios:
            return Resultado()
        texto = self._texto_novedades(
            cambios, titulo=f"🆕 <b>¡{esc(self.cfg.nombre_juego)} se actualizó a la versión {N.VERSION}!</b>"
        )
        return Resultado(avisos=[Aviso(j.id, texto, [[SALA]]) for j in self.db.todos_los_jugadores()])

    def registrar_pantalla(self, uid: int, msg_id: int, es_sala: bool, clave: str | None = None) -> None:
        """El bot avisa qué mensaje muestra la sala (o el plano), para poder actualizarlo en vivo."""
        j = self.db.jugador(uid)
        if j is None:
            return
        if es_sala:
            j.msg_sala = msg_id
            extras = self._extras(j)
            extras["vivo"] = "plano" if clave == "plano" else "sala"
            j.extras = json.dumps(extras)
        elif j.msg_sala == msg_id:
            j.msg_sala = None
        else:
            return
        self.db.guardar_jugador(j)

    def olvidar_pantalla(self, uid: int, msg_id: int) -> None:
        j = self.db.jugador(uid)
        if j is not None and j.msg_sala == msg_id:
            j.msg_sala = None
            self.db.guardar_jugador(j)

    def tick(self) -> Resultado:
        """Se llama cada minuto: avanza a los Sims y detecta quién pasó a ausente o fuera de línea."""
        ahora = self.reloj()
        res = Resultado()
        real = self.db
        self.db = SinPausadas(real, self._salas_en_pausa())  # lo que corre solo no ve las salas en pausa
        try:
            self._tick_vida(ahora, res)
            self._tick_narracion(ahora, res)
            self._tick_cocina(res)
            self._tick_dinero(res)
            self._tick_viaje(res)
            self._tick_trabajo(res)
            self._tick_mascota(res)
            self._tick_influencer(res)
            self._tick_estudios(res)
            self._tick_eventos(res)
            self._tick_aniversario(res)
            self._tick_retos(res)
            self._tick_boda(res)
            self._tick_hitos(res)
        finally:
            self.db = real
        salas: set[int] = set()
        for j in self.db.jugadores_en_sala():
            estado = self._estado_presencia(j, ahora)
            if estado == j.presencia:
                continue
            j.presencia = estado
            self.db.guardar_jugador(j)
            salas.add(j.sala_id)
            if estado == "fuera":
                uc = self._ultima(j)
                if uc.desconectado is None:
                    uc.desconectado = j.ultima_actividad
                    self.db.guardar_ultima_conexion(uc)
        for sala_id in salas:
            res.ediciones += self._refrescar_sala(sala_id)
        # Una sola edición por mensaje: la última es la más actual.
        res.ediciones = list({(e.para, e.msg_id): e for e in res.ediciones}.values())
        return res

    def _manejadores(self):
        return {
            "sala": self._b_sala,
            "act": self._b_actualizar,
            "invitar": self._b_invitar,
            "invc": self._b_confirmar_invitacion,
            "invq": self._b_pasar_bot,
            "invcod": self._b_invitar_con_codigo,
            "aceptoj": self._b_aceptar_mudarse,
            "rechazoj": self._b_rechazar_mudarse,
            "invs": self._b_mis_invitaciones,
            "anular": self._b_anular,
            "pjs": self._b_personajes,
            "animos": self._b_animos,
            "animo": self._b_animo,
            "ajustes": self._b_ajustes,
            "avisos": self._b_avisos,
            "renombrar": self._b_renombrar,
            "conexion": self._b_conexion,
            "sim": self._b_sim,
            "acc": self._b_categoria,
            "a": self._b_accion,
            "as": self._b_solo,
            "aj": self._b_juntos,
            "pj": self._b_respuesta,
            "pjx": self._b_cancelar_propuesta,
            "parar": self._b_parar,
            "dinero": self._b_dinero,
            "mover": self._b_mover,
            "mv": self._b_mover_monto,
            "facturas": self._b_facturas,
            "pagar": self._b_pagar,
            "casa": self._b_casa,
            "trabajo": self._b_trabajo,
            "vtrab": self._b_ver_trabajo,
            "tomar": self._b_tomar_trabajo,
            "renunciar": self._b_renunciar,
            "trabajar": self._b_trabajar,
            "super": self._b_super,
            "sup": self._b_super_accion,
            "nevera": self._b_nevera,
            "rec": self._b_receta,
            "coc": self._b_cocinar_solo,
            "cocina": self._b_coccion,
            "taper": self._b_taper,
            "menu": self._b_menu,
            "mcasa": self._b_menu_casa,
            "macc": self._b_menu_acciones,
            "mlug": self._b_menu_lugares,
            "mpar": self._b_menu_pareja,
            "mest": self._b_menu_estado,
            "moverse": self._b_moverse,
            "ir": self._b_ir,
            "perfil": self._b_perfil,
            "pronto": self._b_pronto,
            "carrera": self._b_carrera,
            "hor": self._b_horario,
            "rapida": self._b_rapida,
            "zona": self._b_zona,
            "mudanza": self._b_mudanza,
            "mudok": self._b_mudanza_si,
            "mudno": self._b_mudanza_no,
            "remodelar": self._b_remodelar,
            "plano": self._b_plano,
            "animop": self._b_publicar_animo,
            "fotoan": self._b_foto_animo,
            "album": self._b_album,
            "medidor": self._b_medidor,
            "rel": self._b_relacion,
            "preg": self._b_preguntas,
            "pregn": self._b_nueva_pregunta,
            "pregr": self._b_responder,
            "pregv": self._b_valorar,
            "pregt": self._b_temas,
            "notas": self._b_notas,
            "notan": self._b_nota_nueva,
            "arreglar": self._b_arreglar,
            "aniv": self._b_aniversario,
            "anivp": self._b_aniv_plan,
            "anivok": self._b_aniv_aceptar,
            "anivb": self._b_aniv_brindis,
            "anivr": self._b_aniv_regalo,
            "retos": self._b_retos,
            "hitos": self._b_hitos,
            "viaje": self._b_viaje,
            "viajeok": self._b_viaje_aceptar,
            "viajeno": self._b_viaje_no,
            "comp": self._b_compromiso,
            "compa": self._b_comprar_anillo,
            "comppe": self._b_pedir,
            "compsi": self._b_pedida_si,
            "compno": self._b_pedida_no,
            "boda": self._b_boda,
            "bodap": self._b_boda_plan,
            "bodaok": self._b_boda_aceptar,
            "bodasi": self._b_boda_si,
            "unir": self._b_unir,
            "unirok": self._b_unir_aceptar,
            "objetos": self._b_objetos,
            "tienda": self._b_tienda,
            "comprar": self._b_comprar,
            "mascota": self._b_mascota,
            "mascad": self._b_adoptar,
            "mascok": self._b_adopcion_si,
            "mascno": self._b_adopcion_no,
            "influ": self._b_influencer,
            "estudios": self._b_estudios,
            "estin": self._b_inscribirse,
            "estno": self._b_dejar_estudio,
            "estpagar": self._b_pagar_carrera,
            "caja": self._b_caja,
            "cajap": self._b_caja_poner,
            "cajas": self._b_caja_sacar,
            "cajaok": self._b_caja_si,
            "cajano": self._b_caja_no,
            "intimo": self._b_intimo,
            "intl": self._b_intimo_lugar,
            "intp": self._b_intimo_proponer,
            "intsi": self._b_intimo_si,
            "intno": self._b_intimo_no,
            "into": self._b_intimo_opcion,
            "intpara": self._b_intimo_parar,
            "pausar": self._b_pausar,
            "rplato": self._b_restaurante_plato,
            "rpostre": self._b_restaurante_postre,
            "narr": self._b_narracion,
            "registro": self._b_registro,
            "zonal": self._b_zona_lugar,
            "fotos": self._b_fotos,
        }

    def _texto_novedades(self, cambios: list[tuple[str, list[str]]], titulo: str) -> str:
        lineas = [titulo]
        for version, notas in cambios:
            lineas += ["", f"<b>Versión {version}</b>"] + [f"• {n}" for n in notas]
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # Visitantes: código personal e invitaciones
    # ------------------------------------------------------------------

    def _codigo_libre(self, largo: int, existe) -> str:
        while True:
            codigo = "".join(secrets.choice(ALFABETO) for _ in range(largo))
            if not existe(codigo):
                return codigo

    def _registrar_visitante(self, uid: int, nombre_tg: str) -> Visitante:
        """El código personal de cada quien es su ID de jugador (el de Telegram)."""
        v = self.db.visitante(uid)
        if v is None:
            v = Visitante(id=uid, codigo=str(uid), nombre_tg=nombre_tg, creado=self.reloj())
            self.db.guardar_visitante(v)
        elif v.codigo != str(uid) or (nombre_tg and v.nombre_tg != nombre_tg):
            v.codigo = str(uid)  # los códigos al azar de antes pasan a ser el ID
            v.nombre_tg = nombre_tg or v.nombre_tg
            self.db.guardar_visitante(v)
        return v

    def _resolver_codigo(self, codigo: str) -> tuple[Visitante | None, Jugador | None]:
        """A quién pertenece un código: su ID de jugador (o un código antiguo de visitante)."""
        if codigo.isdigit():
            uid = int(codigo)
            return self.db.visitante(uid), self.db.jugador(uid)
        v = self.db.visitante_por_codigo(codigo)
        return v, (self.db.jugador(v.id) if v else None)

    def _visitante(self, uid: int, nombre_tg: str) -> Resultado:
        if uid in self.cfg.admins:
            return self._crear_jugador(uid, nombre_tg, None)
        if not self.cfg.admins and self.db.contar_jugadores() == 0:
            log.warning("No hay ADMIN_IDS ni jugadores: %s (%s) entra como primer jugador.", uid, nombre_tg)
            return self._crear_jugador(uid, nombre_tg, None)
        if not self._registro_abierto():
            return Resultado(pantalla=self._pantalla_cerrado(), nuevo=True)
        v = self._registrar_visitante(uid, nombre_tg)
        pendientes = self.db.invitaciones_para(uid, self.reloj())
        if pendientes:
            return Resultado(pantalla=self._pantalla_invitado(pendientes[0]), nuevo=True)
        return Resultado(pantalla=self._candado(v), nuevo=True)

    # --- registro abierto o cerrado a jugadores nuevos ---

    def _registro_abierto(self) -> bool:
        valor = self.db.meta("registro")
        return self.cfg.registro_abierto if valor is None else valor == "abierto"

    def _pantalla_cerrado(self) -> Pantalla:
        return Pantalla(
            f"🔒 <b>{esc(self.cfg.nombre_juego)} no acepta jugadores nuevos por ahora.</b>\n\n"
            "Es un juego privado. Si alguien te pasó el bot, pídele que te avise cuando se abra.",
            [],
        )

    def _b_registro(self, j: Jugador, arg: str, res: Resultado) -> None:
        """⚙️ Ajustes (solo admins): abrir o cerrar el juego a jugadores nuevos."""
        if j.id in self.cfg.admins:
            abierto = not self._registro_abierto()
            self.db.guardar_meta("registro", "abierto" if abierto else "cerrado")
            res.alerta = "🔓 Abierto a jugadores nuevos" if abierto else "🔒 Cerrado a jugadores nuevos"
        self._b_ajustes(j, "", res)

    def _candado(self, v: Visitante, nota: str | None = None) -> Pantalla:
        lineas = [nota, ""] if nota else []
        lineas += [
            f"🔒 <b>{esc(self.cfg.nombre_juego)} es solo por invitación.</b>",
            "",
            f"🔑 Tu código personal (tu ID de jugador): <code>{v.codigo}</code>",
            "",
            "Pásale este código a quien te va a invitar (tu pareja o alguien que ya juegue). "
            "Esa persona tiene que escribir en el bot:",
            f"<code>invitar_{v.codigo}</code>",
            "",
            "Cuando lo haga, te llegará aquí un aviso para entrar. 💌",
        ]
        return Pantalla("\n".join(lineas), [[("🔄 Ya me invitaron", "vis")]])

    def _pantalla_invitado(self, inv: Invitacion) -> Pantalla:
        creador = self.db.jugador(inv.creador)
        quien = self._firma(creador) if creador else "Alguien"
        detalle = (
            "💞 Entrarás a su sala como pareja." if inv.tipo == "pareja" else "🏠 Tendrás tu propia sala."
        )
        return Pantalla(
            f"💌 <b>¡Tienes una invitación!</b>\n\n"
            f"{quien} te invitó a jugar {esc(self.cfg.nombre_juego)}.\n"
            f"Te invita como: <b>{vinculo(inv.tipo)}</b>\n{detalle}",
            [[("✅ Aceptar y crear mi personaje", f"acepto:{inv.codigo}")],
             [("❌ No, gracias", f"rechazo:{inv.codigo}")]],
        )

    def _boton_visitante(self, uid: int, nombre_tg: str, accion: str, codigo: str) -> Resultado:
        if accion not in ("acepto", "rechazo") or not self._registro_abierto():
            res = self._visitante(uid, nombre_tg)
            res.nuevo = False
            return res
        ahora = self.reloj()
        inv = self.db.invitacion(codigo)
        creador = self.db.jugador(inv.creador) if inv else None
        if inv is None or inv.para_id != uid or not inv.vigente(ahora) or creador is None or not creador.activo:
            res = self._visitante(uid, nombre_tg)
            res.alerta = "Esa invitación ya no está disponible."
            res.nuevo = False
            return res
        quien = esc(nombre_tg) if nombre_tg else "La persona que invitaste"
        if accion == "rechazo":
            inv.anulada = 1
            self.db.guardar_invitacion(inv)
            v = self._registrar_visitante(uid, nombre_tg)
            res = Resultado(pantalla=self._candado(v, "👌 Invitación rechazada."))
            res.avisos.append(Aviso(creador.id, f"😕 <b>{quien}</b> no aceptó tu invitación."))
            return res
        inv.usada_por = uid
        inv.usada_ts = ahora
        self.db.guardar_invitacion(inv)
        res = self._crear_jugador(uid, nombre_tg, inv)
        res.nuevo = False
        res.avisos.append(Aviso(creador.id, f"🎟️ <b>{quien}</b> ({vinculo(inv.tipo)}) aceptó tu invitación y está "
                                             "creando su personaje…"))
        return res

    # --- quien ya juega invita escribiendo invitar_CÓDIGO ---

    def _fallos_recientes(self, uid: int, ahora: float) -> list[float]:
        fallos = [t for t in self._fallos.get(uid, []) if ahora - t < VENTANA_FALLOS]
        self._fallos[uid] = fallos
        return fallos

    def _invitar_codigo(self, j: Jugador, codigo: str, res: Resultado) -> None:
        ahora = self.reloj()
        codigo = normalizar_codigo(codigo)
        volver = [[("💌 Invitar", "invitar"), SALA]]
        if len(self._fallos_recientes(j.id, ahora)) >= MAX_FALLOS_CODIGO:
            res.pantalla = Pantalla("⏳ Demasiados códigos equivocados. Espera unos minutos y vuelve a probar.", volver)
            return
        v, otro = self._resolver_codigo(codigo)
        if otro is not None and otro.id == j.id:
            res.pantalla = Pantalla(
                "🪪 Ese es <b>tu</b> código. Para invitar a alguien, escribe <code>invitar_</code> y "
                "<b>su</b> código (su ID de jugador).",
                volver,
            )
            return
        if otro is not None:
            self._invitar_jugador(j, otro, volver, res)
            return
        if not self._registro_abierto():  # quien no juega todavía no puede entrar
            res.pantalla = Pantalla("🔒 El juego está cerrado a jugadores nuevos: esa persona no puede entrar.", volver)
            return
        if v is None:
            self._fallos[j.id].append(ahora)
            res.pantalla = Pantalla(
                f"❌ No encontré el código <code>{esc(codigo)}</code>.\n\n"
                "Revisa que esté bien escrito: es su ID de jugador (solo números). La otra persona lo ve al "
                f"abrir @{esc(self.bot_usuario)} y tocar <b>Iniciar</b>, o en 💌 Invitar si ya juega.",
                volver,
            )
            return
        res.pantalla = Pantalla(
            f"🔑 El código <code>{v.codigo}</code> es de <b>{esc(v.nombre_tg or 'alguien')}</b> en Telegram.\n\n"
            "¿Quién es esta persona para ti?\n<i>Solo la pareja entra a tu sala; los demás tienen la suya.</i>",
            self._botones_vinculo(j, lambda tipo: f"invc:{v.codigo}:{tipo}") + [[("❌ Cancelar", "sala")]],
        )

    def _botones_vinculo(self, j: Jugador, dato) -> Botones:
        """Un botón por cada vínculo (la pareja, solo si hay lugar en tu sala)."""
        opciones = [
            (f"{emoji} {nombre}", dato(tipo)) for tipo, (emoji, nombre) in VINCULOS.items()
            if tipo != "pareja" or self._hay_lugar(j)
        ]
        return en_filas(opciones)

    def _invitar_jugador(self, j: Jugador, otro: Jugador, volver: Botones, res: Resultado) -> None:
        """El código es de alguien que ya juega: si juega sin pareja, se le invita a mudarse a tu sala."""
        if not otro.activo:
            res.pantalla = Pantalla("ℹ️ Esa persona todavía está creando su personaje. Prueba en un rato.", volver)
            return
        if otro.sala_id == j.sala_id:
            res.pantalla = Pantalla(f"💞 {self._firma(otro)} ya está en tu sala.", volver)
            return
        if self._pareja_en_sala(otro) is not None:
            res.pantalla = Pantalla(f"ℹ️ {self._firma(otro)} ya juega en pareja en otra sala.", volver)
            return
        if not self._hay_lugar(j):
            res.pantalla = Pantalla("ℹ️ Tu sala ya está completa.", volver)
            return
        res.pantalla = Pantalla(
            f"🪪 El código <code>{otro.id}</code> es de {self._firma(otro)}, que ya juega sin pareja.\n\n"
            "¿Le invitas a mudarse a tu sala como tu pareja? Sus ahorros y sus cosas se vienen con su Sim.",
            [[("💞 Sí, como mi pareja", f"invc:{otro.id}:pareja")], [("❌ Cancelar", "sala")]],
        )

    def _b_confirmar_invitacion(self, j: Jugador, arg: str, res: Resultado) -> None:
        ahora = self.reloj()
        codigo, _, tipo = arg.partition(":")
        tipo = VINCULOS_ANTIGUOS.get(tipo, tipo)
        v, otro = self._resolver_codigo(codigo)
        if otro is not None and otro.id != j.id:
            self._confirmar_invitacion_jugador(j, otro, tipo, res)
            return
        if v is None or otro is not None or tipo not in VINCULOS or not self._registro_abierto():
            res.alerta = "Esa persona ya no se puede invitar."
            self._b_invitar(j, "", res)
            return
        if tipo == "pareja" and not self._hay_lugar(j):
            res.alerta = "Tu sala ya está completa."
            self._b_invitar(j, "", res)
            return
        activas = [i for i in self.db.invitaciones_de(j.id, 50) if i.vigente(ahora)]
        if len(activas) >= self.cfg.max_invitaciones_activas:
            res.alerta = f"Ya tienes {len(activas)} invitaciones sin respuesta. Anula alguna en 📋."
            self._b_mis_invitaciones(j, "", res)
            return
        # Solo vale la invitación más reciente para cada persona.
        for vieja in self.db.invitaciones_para(v.id, ahora):
            vieja.anulada = 1
            self.db.guardar_invitacion(vieja)
        inv = Invitacion(
            codigo=self._codigo_libre(LARGO_CODIGO_INVITACION, self.db.invitacion),
            creador=j.id,
            tipo=tipo,
            sala_id=j.sala_id if tipo == "pareja" else None,
            creada=ahora,
            expira=ahora + self.cfg.invitacion_dias * DIA,
            para_id=v.id,
        )
        self.db.guardar_invitacion(inv)
        pantalla = self._pantalla_invitado(inv)
        res.avisos.append(Aviso(v.id, pantalla.texto, pantalla.botones))
        res.pantalla = Pantalla(
            f"✅ <b>Invitación enviada a {esc(v.nombre_tg or 'esa persona')}</b> ({vinculo(tipo)}).\n\n"
            "Le llegó un aviso en el bot para aceptarla. Te aviso cuando entre.\n"
            f"⏳ Vence en {duracion(inv.expira - ahora + MINUTO)}.\n\n"
            "🎮 Mientras tanto, puedes seguir jugando.",
            [[("🎮 Jugar mientras tanto", "sim")], [("📋 Invitaciones enviadas", "invs"), SALA]],
        )

    def _confirmar_invitacion_jugador(self, j: Jugador, otro: Jugador, tipo: str, res: Resultado) -> None:
        ahora = self.reloj()
        if tipo != "pareja" or not otro.activo or self._pareja_en_sala(otro) is not None or not self._hay_lugar(j):
            res.alerta = "Esa persona ya no se puede invitar."
            self._b_invitar(j, "", res)
            return
        for vieja in self.db.invitaciones_para(otro.id, ahora):
            vieja.anulada = 1
            self.db.guardar_invitacion(vieja)
        inv = Invitacion(
            codigo=self._codigo_libre(LARGO_CODIGO_INVITACION, self.db.invitacion),
            creador=j.id, tipo="pareja", sala_id=j.sala_id, creada=ahora,
            expira=ahora + self.cfg.invitacion_dias * DIA, para_id=otro.id,
        )
        self.db.guardar_invitacion(inv)
        res.avisos.append(Aviso(
            otro.id,
            f"💌 <b>¡Tienes una invitación!</b>\n\n{self._firma(j)} te invita a mudarte a su sala como su pareja. "
            "Tu Sim, tus ahorros de la cuenta compartida y tus cosas se mudan contigo.",
            [[("✅ Aceptar y mudarme", f"aceptoj:{inv.codigo}")], [("❌ No, gracias", f"rechazoj:{inv.codigo}")]],
        ))
        res.pantalla = Pantalla(
            f"✅ <b>Invitación enviada a {self._firma(otro)}.</b>\n\nLe llegó un aviso para aceptarla. "
            f"⏳ Vence en {duracion(inv.expira - ahora + MINUTO)}.",
            [[("📋 Invitaciones enviadas", "invs"), SALA]],
        )

    def _b_aceptar_mudarse(self, j: Jugador, codigo: str, res: Resultado) -> None:
        """Alguien que jugaba sin pareja acepta mudarse a la sala de quien le invitó."""
        ahora = self.reloj()
        inv = self.db.invitacion(codigo)
        creador = self.db.jugador(inv.creador) if inv else None
        if (
            inv is None or inv.para_id != j.id or not inv.vigente(ahora) or creador is None or not creador.activo
            or creador.sala_id is None or self._pareja_en_sala(j) is not None or not self._hay_lugar(creador)
        ):
            res.alerta = "Esa invitación ya no está disponible."
            res.pantalla = self._pantalla_sala(j)
            return
        inv.usada_por = j.id
        inv.usada_ts = ahora
        self.db.guardar_invitacion(inv)
        if self._accion(j):
            self._vivir(j, ahora)
            j.accion = None
        vieja = j.sala_id
        self._mudar_hogar(vieja, creador.sala_id, j)
        j.sala_id = creador.sala_id
        j.invitado_por = creador.id
        j.lugar = V.HABITACION_INICIAL
        extras = self._extras(j)
        extras["vinculo"] = "pareja"
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.avisos.append(Aviso(creador.id, f"💞 {self._firma(j)} aceptó tu invitación y se mudó a tu sala.", [[SALA]]))
        res.ediciones += self._refrescar_sala(creador.sala_id, excepto=j.id)
        res.pantalla = self._pantalla_sala(j, f"💞 ¡Te mudaste a la sala de {self._firma(creador)}!")

    def _mudar_hogar(self, vieja: int | None, nueva: int, j: Jugador) -> None:
        """Lo de la casa anterior que se lleva: los ahorros, los objetos y la mascota."""
        h0 = self.db.hogar(vieja) if vieja is not None else None
        if h0 is None or not h0.casa:
            return
        h = self._hogar(nueva)
        ex0, ex = self._extras_hogar(h0), self._extras_hogar(h)
        if h0.cuenta > 0:
            h.cuenta += h0.cuenta
            self._anotar_movimiento(nueva, j.id, "compartida", h0.cuenta, f"🧳 Ahorros de {j.personaje}")
            h0.cuenta = 0
        caja0 = ex0.pop("caja", None)
        if caja0 and caja0["saldo"] > 0:  # su caja de ahorros pasa a la cuenta compartida
            h.cuenta += caja0["saldo"]
            self._anotar_movimiento(nueva, j.id, "compartida", caja0["saldo"], f"🐷 Caja de ahorros de {j.personaje}")
        ex0.pop("caja_prop", None)
        ex["objetos"] = sorted(set(ex.get("objetos", [])) | set(ex0.pop("objetos", [])))
        if ex0.get("mascota") and not ex.get("mascota"):
            ex["mascota"] = ex0.pop("mascota")
        h0.cocina = ""
        h0.extras = json.dumps(ex0)
        self.db.guardar_hogar(h0)
        self._guardar_extras_hogar(h, ex)

    def _b_rechazar_mudarse(self, j: Jugador, codigo: str, res: Resultado) -> None:
        inv = self.db.invitacion(codigo)
        if inv is not None and inv.para_id == j.id and inv.vigente(self.reloj()):
            inv.anulada = 1
            self.db.guardar_invitacion(inv)
            res.avisos.append(Aviso(inv.creador, f"😕 {self._firma(j)} no aceptó tu invitación."))
            res.alerta = "👌 Invitación rechazada"
        res.pantalla = self._pantalla_sala(j)

    # ------------------------------------------------------------------
    # Creación del personaje
    # ------------------------------------------------------------------

    def _crear_jugador(self, uid: int, nombre_tg: str, inv: Invitacion | None) -> Resultado:
        ahora = self.reloj()
        j = Jugador(
            id=uid,
            estado="nombrando",
            nombre_tg=nombre_tg,
            invitado_por=inv.creador if inv else None,
            inv_codigo=inv.codigo if inv else None,
            ultima_actividad=ahora,
            creado=ahora,
            extras=json.dumps({"vinculo": VINCULOS_ANTIGUOS.get(inv.tipo, inv.tipo)} if inv else {}),
        )
        self.db.guardar_jugador(j)
        res = self._tocar(j)
        res.pantalla = self._pedir_nombre(j)
        res.nuevo = True
        self._anotar(j.id, res)
        return res

    def _pedir_nombre(self, j: Jugador) -> Pantalla:
        texto = f"🎉 <b>¡Te damos la bienvenida a {esc(self.cfg.nombre_juego)}!</b>\n\n"
        anfitrion = self.db.jugador(j.invitado_por) if j.invitado_por else None
        if anfitrion:
            texto += f"Te invitó <b>{esc(anfitrion.personaje)}</b>.\n\n"
        texto += "Primero vas a crear tu personaje.\n✍️ <b>¿Cómo se llamará?</b> Escribe el nombre aquí abajo."
        return Pantalla(texto, clave="nombre")

    def _recibir_nombre(self, j: Jugador, texto: str) -> Resultado:
        res = self._tocar(j)
        nombre = " ".join(texto.split())
        if not NOMBRE_RE.fullmatch(nombre):
            botones = [[("❌ Cancelar", "sala")]] if j.estado == "renombrando" else []
            res.pantalla = Pantalla(
                "✋ Ese nombre no me sirve. Usa entre 2 y 20 caracteres, empezando por una letra "
                "(puede llevar espacios). Prueba otra vez:",
                botones,
            )
            res.nuevo = True
            return res
        j.personaje = nombre
        if j.estado == "renombrando":
            j.estado = "activo"
            self.db.guardar_jugador(j)
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
            res.pantalla = self._pantalla_sala(j, f"✏️ Ahora tu personaje se llama <b>{esc(nombre)}</b>.")
            res.nuevo = True
            return res
        j.estado = "creando"
        j.borrador = "{}"
        self.db.guardar_jugador(j)
        res.pantalla = self._pantalla_creador(j)
        res.nuevo = True
        return res

    # --- creador de personaje (sirve para crearlo y para cambiarlo después) ---

    def _borrador(self, j: Jugador) -> dict:
        return json.loads(j.borrador) if j.borrador else {}

    def _guardar_borrador(self, j: Jugador, b: dict) -> None:
        j.borrador = json.dumps(b, ensure_ascii=False)
        self.db.guardar_jugador(j)

    def _creador(self, j: Jugador, accion: str, arg: str, res: Resultado) -> Resultado:
        if accion == "apedit" and j.estado != "creando":
            j.borrador = j.apariencia
            self.db.guardar_jugador(j)
            res.pantalla = self._pantalla_ficha(j, self._borrador(j))
            return res
        if j.borrador is None:
            res.alerta = "Ese menú ya se cerró."
            res.pantalla = self._pantalla_sala(j)
            return res
        b = self._borrador(j)
        campo_actual = None
        if accion == "ap":  # elegir una opción de un campo simple
            campo, _, valor = arg.partition(":")
            c = P.POR_CLAVE.get(campo)
            if c is not None and not c.multiple:
                P.elegir(b, campo, P.al_azar(c, self.rng) if valor == "?" else valor)
        elif accion == "apm":  # marcar o desmarcar en un campo de varias opciones
            campo, _, valor = arg.partition(":")
            c = P.POR_CLAVE.get(campo)
            if c is not None and c.multiple:
                if valor == "?":
                    b[campo] = P.al_azar(c, self.rng)
                    b.pop("_sel", None)
                else:
                    seleccion = b.get("_sel", {}).get(campo, b.get(campo, []))
                    seleccion, res.alerta = P.alternar(c, seleccion, valor)
                    b["_sel"] = {campo: seleccion}
                    campo_actual = c
        elif accion == "apml":  # listo con un campo de varias opciones
            c = P.POR_CLAVE.get(arg)
            if c is not None and c.multiple:
                seleccion = b.get("_sel", {}).get(arg, b.get(arg, []))
                if len(seleccion) < c.minimo:
                    res.alerta = f"Elige al menos {c.minimo}."
                    campo_actual = c
                else:
                    b[arg] = seleccion
                    b.pop("_sel", None)
        elif accion == "ape":  # volver a un campo para cambiarlo
            campo_actual = P.POR_CLAVE.get(arg)
            if campo_actual is not None and campo_actual.multiple:
                b["_sel"] = {arg: list(b.get(arg, []))}
        elif accion == "apr":
            b = P.todo_al_azar(self.rng)
        elif accion == "apx" and j.estado != "creando":
            j.borrador = None
            self.db.guardar_jugador(j)
            self._b_personajes(j, "", res)
            return res
        elif accion == "apok" and P.completa(b):
            return self._confirmar_personaje(j, b, res)
        self._guardar_borrador(j, b)
        res.pantalla = self._pantalla_creador(j, campo_actual)
        return res

    def _pantalla_creador(self, j: Jugador, campo: P.Campo | None = None) -> Pantalla:
        b = self._borrador(j)
        clave = f"creador:{campo.clave}" if campo else "creador"
        campo = campo or P.siguiente_campo(b)
        if campo is None:
            return self._pantalla_ficha(j, b)
        genero = b.get("genero")
        visibles = P.campos_visibles(b)
        paso = next((i for i, c in enumerate(visibles) if c.clave == campo.clave), 0) + 1
        verbo = "Creando" if j.estado == "creando" else "Editando"
        texto = (
            f"🧑‍🎨 <b>{verbo} a {esc(j.personaje)}</b> {P.avatar(b)}\n"
            f"Paso {paso} de {len(visibles)} · {campo.seccion}: {campo.emoji} {campo.titulo}\n\n"
            f"<b>{campo.pregunta}</b>"
        )
        if campo.multiple:
            elegidos = b.get("_sel", {}).get(campo.clave, b.get(campo.clave, []))
            opciones = [
                (("✅ " if o.clave in elegidos else "") + o.boton(genero), f"apm:{campo.clave}:{o.clave}")
                for o in campo.opciones
            ]
            cuenta = f" ({len(elegidos)}/{campo.maximo})" if campo.maximo else ""
            botones = en_filas(opciones) + [
                [("🎲 Al azar", f"apm:{campo.clave}:?"), (f"✅ Listo{cuenta}", f"apml:{campo.clave}")]
            ]
        else:
            actual = b.get(campo.clave)
            opciones = [
                (("✅ " if o.clave == actual else "") + o.boton(genero), f"ap:{campo.clave}:{o.clave}")
                for o in campo.opciones
            ]
            botones = en_filas(opciones) + [[("🎲 Al azar", f"ap:{campo.clave}:?")]]
        if P.completa(b):
            botones.append([("⬅️ Volver a la ficha", "apf")])
        elif paso > 1:
            botones.append([("⬅️ Atrás", f"ape:{visibles[paso - 2].clave}")])
        return Pantalla(texto, botones, clave=clave)

    def _pantalla_ficha(self, j: Jugador, b: dict) -> Pantalla:
        lineas = [f"🪪 <b>Ficha de {esc(j.personaje)}</b>  {P.avatar(b)}"]
        seccion = None
        for c in P.campos_visibles(b):
            if c.seccion != seccion:
                seccion = c.seccion
                lineas += ["", f"<b>{seccion}</b>"]
            lineas.append(f"{c.emoji} {c.titulo}: <b>{P.etiqueta(b, c.clave)}</b>")
        lineas += ["", f"<i>{esc(P.descripcion(j.personaje, b))}</i>", "", "¿Te gusta cómo quedó?"]
        editar = [(f"✏️ {c.titulo}", f"ape:{c.clave}") for c in P.campos_visibles(b)]
        botones = en_filas(editar) + [
            [("🎲 Sorpréndeme (todo al azar)", "apr")],
            [("✅ ¡Listo, así me gusta!", "apok")],
        ]
        if j.estado != "creando":
            botones.append([("❌ Cancelar cambios", "apx")])
        return Pantalla("\n".join(lineas), botones, clave="creador")

    def _confirmar_personaje(self, j: Jugador, b: dict, res: Resultado) -> Resultado:
        b.pop("_sel", None)
        j.apariencia = json.dumps(b, ensure_ascii=False)
        j.borrador = None
        if j.estado != "creando":
            self.db.guardar_jugador(j)
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
            self._b_personajes(j, "", res)
            res.alerta = "✅ Personaje guardado"
            return res
        return self._entrar_a_sala(j)

    def _entrar_a_sala(self, j: Jugador) -> Resultado:
        """Último paso de la creación: el personaje entra a la sala de su pareja o a una propia."""
        ahora = self.reloj()
        inv = self.db.invitacion(j.inv_codigo) if j.inv_codigo else None
        creador = self.db.jugador(inv.creador) if inv else None
        anfitrion = None
        if (
            inv is not None and inv.tipo == "pareja" and creador is not None
            and creador.activo and creador.sala_id == inv.sala_id
            and len(self.db.miembros_sala(inv.sala_id)) < self.cfg.max_sala
        ):
            j.sala_id = inv.sala_id
            anfitrion = creador
        else:
            j.sala_id = self.db.crear_sala(j.id, ahora)
        j.estado = "activo"
        j.reloj_juego = 0.0
        j.reloj_desde = ahora
        j.ultima_jugada = ahora
        j.necesidades = json.dumps(V.nuevas_necesidades())
        j.nec_seg = 0.0
        res = self._tocar(j, avisar_conexion=False)
        if not res.ediciones:  # alguien nuevo en la sala: hay que redibujarla siempre
            res.ediciones = self._refrescar_sala(j.sala_id, excepto=j.id)
        for o in self._companeros(j):
            res.avisos.append(Aviso(
                o.id,
                f"💞 {self._firma(j)} entró a tu sala.\n"
                "Ya pueden escribirse: todo lo que mandes aquí le llega al instante.",
                [[("🏠 Ver la sala", "sala")]],
            ))
        if creador is not None and anfitrion is None:
            res.avisos.append(Aviso(
                creador.id, f"🎉 {self._firma(j)} aceptó tu invitación y ya está en el juego."
            ))
        res.pantalla = self._pantalla_bienvenida(j, anfitrion)
        res.nuevo = True
        return res

    def _pantalla_bienvenida(self, j: Jugador, anfitrion: Jugador | None) -> Pantalla:
        lineas = [
            f"✨ <b>¡Personaje creado!</b> {P.avatar(j.ap)} <b>{esc(j.personaje)}</b>",
            "",
            f"<i>{esc(P.descripcion(j.personaje, j.ap))}</i>",
            "",
        ]
        if anfitrion:
            lineas += [
                f"💞 Entraste a la sala de {self._firma(anfitrion)}. "
                "Todo lo que escribas aquí le llega directo.",
                "",
            ]
        lineas += [
            "<b>¿Qué quieres hacer ahora?</b>",
            "🎮 <b>Jugar</b>: cuida a tu Sim y vive el día, con o sin compañía.",
            "💌 <b>Invitar</b>: invita a tu pareja o a quien quieras.",
        ]
        return Pantalla(
            "\n".join(lineas), [[("🎮 Jugar", "menu"), ("💌 Invitar", "invitar")]], clave="bienvenida"
        )

    # ------------------------------------------------------------------
    # Reloj del Sim: corre como un día real y se congela sin actividad
    # ------------------------------------------------------------------

    def _limite_pausa(self, j: Jugador) -> float:
        """El reloj corre hasta 5 min después de la última jugada o del fin de la acción en curso."""
        return max(j.ultima_jugada, self._fin_accion_real(j)) + self.pausa

    def _congelado(self, j: Jugador, ahora: float) -> bool:
        return j.reloj_desde is None or ahora >= self._limite_pausa(j)

    def _segundos_juego(self, j: Jugador, ahora: float) -> float:
        if j.reloj_desde is None:
            return j.reloj_juego
        hasta = min(ahora, self._limite_pausa(j))
        return j.reloj_juego + max(0.0, hasta - j.reloj_desde)

    def _congelar(self, j: Jugador, ahora: float) -> None:
        if j.reloj_desde is not None:
            j.reloj_juego = self._segundos_juego(j, ahora)
            j.reloj_desde = None

    def _pausa(self, j: Jugador, nuevo: bool = False) -> Resultado:
        """Pantalla de 'tu Sim estaba en pausa': hay que tocar Continuar para seguir (o, con el juego de la
        pareja en pausa, la pantalla de la pausa)."""
        if self._pausa_pareja(j.sala_id):
            res = self._tocar(j, jugada=False)
            res.pantalla = self._pantalla_pausa_pareja(j)
            res.nuevo = nuevo
            self._anotar(j.id, res)
            return res
        ahora = self.reloj()
        desde = self._limite_pausa(j) if j.ultima_jugada else j.ultima_actividad
        self._congelar(j, ahora)
        res = self._tocar(j, jugada=False)
        uc = self.db.ultima_conexion(j.id)
        lugar = uc.lugar if uc and uc.lugar else LUGARES["sala"][0]
        notas = "".join(f"\n\n{n}" for n in self._leer_notas(j))  # las notas de la nevera se ven al entrar
        res.pantalla = Pantalla(
            "❄️ <b>Tu Sim estaba en pausa</b>\n\n"
            f"{self._firma(j)} se quedó en pausa hace {duracion(ahora - desde)}, en <b>{lugar}</b>.\n"
            "❄️ Mientras está en pausa no gasta necesidades.\n\n"
            "La pausa es solo tuya: tu pareja pudo seguir jugando." + notas,
            [[CONTINUAR]],
        )
        res.nuevo = nuevo
        return res

    def _continuar(self, j: Jugador) -> Resultado:
        if self._pausa_pareja(j.sala_id):
            return self._pausa(j)  # con el juego en pausa, se sigue con ▶️ Reanudar
        self._descongelar(j, self.reloj())
        return self._reanudar(j, nuevo=False, saludo="▶️ <b>¡Seguimos!</b>")

    # ------------------------------------------------------------------
    # Última conexión: guardar dónde se quedó y retomarlo al volver
    # ------------------------------------------------------------------

    def _ultima(self, j: Jugador) -> UltimaConexion:
        return self.db.ultima_conexion(j.id) or UltimaConexion(jugador_id=j.id)

    def _anotar(self, uid: int, res: Resultado, actividad: str | None = None) -> None:
        """Sobrescribe la última conexión con la pantalla que se acaba de mostrar."""
        clave = res.pantalla.clave if res.pantalla else None
        if clave is None and actividad is None:
            return
        j = self.db.jugador(uid)
        if j is None:
            return
        uc = self._ultima(j)
        if clave is not None:
            uc.pantalla = clave
            uc.lugar, uc.actividad = LUGARES[clave.partition(":")[0]]
        if actividad is not None:
            uc.actividad = actividad
        uc.estado = j.estado
        uc.sala_id = j.sala_id
        uc.ultima_actividad = self.reloj()
        self.db.guardar_ultima_conexion(uc)

    def _reanudar(self, j: Jugador, nuevo: bool = True, saludo: str = "👋 <b>¡Hola de nuevo!</b>") -> Resultado:
        ahora = self.reloj()
        previa = self.db.ultima_conexion(j.id)
        res = self._tocar(j)
        notas = self._leer_notas(j) if j.activo else []  # las notas de la nevera se ven al entrar
        pantalla, nota = self._reconstruir(j, previa)
        cabecera = []
        if previa is not None and previa.ultima_actividad:
            cabecera.append(
                f"{saludo} Retomas donde lo dejaste: <b>{previa.lugar}</b> "
                f"· hace {duracion(ahora - previa.ultima_actividad)}."
            )
        if nota:
            cabecera.append(nota)
        cabecera += notas
        if cabecera:
            pantalla.texto = "\n".join(cabecera) + "\n\n" + pantalla.texto
        res.pantalla = pantalla
        res.nuevo = nuevo
        self._anotar(j.id, res)
        return res

    def _reconstruir(self, j: Jugador, previa: UltimaConexion | None) -> tuple[Pantalla, str | None]:
        """Vuelve a armar la pantalla guardada, comprobando que siga siendo válida."""
        if j.estado == "nombrando":
            return self._pedir_nombre(j), None
        if j.estado == "renombrando":
            return self._pantalla_renombrar(j), None
        accion, _, arg = (previa.pantalla if previa else "sala").partition(":")
        if j.estado == "creando" or (accion == "creador" and j.borrador is not None):
            return self._pantalla_creador(j, P.POR_CLAVE.get(arg)), None
        nota = None
        if j.sala_id is None:
            j.sala_id = self.db.crear_sala(j.id, self.reloj())
            self.db.guardar_jugador(j)
            nota = "🔧 Tu sala no aparecía y la volví a crear."
        elif previa is not None and previa.sala_id is not None and previa.sala_id != j.sala_id:
            return self._pantalla_sala(j), "ℹ️ Tu sala cambió desde la última vez."
        if accion == "bienvenida":
            return self._pantalla_bienvenida(j, None), nota
        manejador = {
            "sala": self._b_sala, "invitar": self._b_invitar, "invs": self._b_mis_invitaciones,
            "pjs": self._b_personajes, "animo": self._b_animos, "ajustes": self._b_ajustes,
            "sim": self._b_sim, "acc": self._b_categoria, "dinero": self._b_dinero,
            "mover": self._b_mover, "facturas": self._b_facturas, "casa": self._b_casa,
            "trabajo": self._b_trabajo, "super": self._b_super, "nevera": self._b_nevera,
            "cocina": self._b_coccion, "menu": self._b_menu, "mcasa": self._b_menu_casa,
            "macc": self._b_menu_acciones, "mlug": self._b_menu_lugares, "mpar": self._b_menu_pareja,
            "mest": self._b_menu_estado, "perfil": self._b_perfil, "carrera": self._b_carrera,
            "mudanza": self._b_mudanza, "plano": self._b_plano,
            "animofoto": self._b_animos, "album": self._b_album,
            "medidor": self._b_medidor, "relmotivo": self._b_medidor,
            "preguntas": self._b_preguntas, "pregresp": self._b_preguntas,
            "notas": self._b_notas, "notaesc": self._b_notas, "aniv": self._b_aniversario,
            "retos": self._b_retos, "hitos": self._b_hitos, "viaje": self._b_viaje,
            "comp": self._b_compromiso, "boda": self._b_boda, "objetos": self._b_objetos, "tienda": self._b_tienda,
            "mascota": self._b_mascota, "mascnombre": self._b_mascota, "influ": self._b_influencer,
            "intimo": self._b_intimo,
            "caja": self._b_caja,
            "pausa": self._b_ver_pausa,
            "estudios": self._b_estudios,
        }.get(accion, self._b_menu)
        tmp = Resultado()
        manejador(j, arg, tmp)
        return tmp.pantalla, nota

    def _pantalla_conexion(self, j: Jugador) -> Pantalla:
        ahora = self.reloj()
        uc = self.db.ultima_conexion(j.id)
        if uc is None:
            return Pantalla("🧾 Todavía no hay ninguna conexión guardada.", [[SALA]])
        if uc.desconectado:
            salida = f"hace {duracion(ahora - uc.desconectado)}"
        else:
            salida = "— (sigues conectado)" if self._estado_presencia(j, ahora) != "fuera" else "—"
        reloj = ""
        if j.activo:
            estado = "❄️ en pausa" if self._congelado(j, ahora) else "▶️ corriendo"
            reloj = f"🕒 Hora: {self._reloj(j)} · Sim {estado}\n"
        return Pantalla(
            "🧾 <b>Tu última conexión guardada</b>\n\n"
            f"📍 Lugar: <b>{uc.lugar or '—'}</b>\n"
            f"🎬 Haciendo: {esc(uc.actividad or '—')}\n"
            f"🏠 Sala n.º {uc.sala_id if uc.sala_id is not None else '—'}\n"
            f"{reloj}"
            f"🔌 Entraste: hace {duracion(ahora - uc.conectado_desde)}\n"
            f"🕒 Última actividad: hace {duracion(ahora - uc.ultima_actividad)}\n"
            f"🚪 Salida: {salida}\n\n"
            "<i>Solo se guarda la última. Es lo que se usa para devolverte al mismo sitio cuando vuelves.</i>",
            [[("⬅️ Volver", "volver")]],
        )

    # ------------------------------------------------------------------
    # Presencia (en línea / en pausa / fuera de línea)
    # ------------------------------------------------------------------

    def _estado_presencia(self, j: Jugador, ahora: float) -> str:
        if j.salio or not j.ultima_actividad:
            return "fuera"
        inactivo = ahora - j.ultima_actividad
        if inactivo < self.cfg.en_linea_min * MINUTO:
            return "en_linea"
        if inactivo < self.cfg.ausente_min * MINUTO:
            return "ausente"
        return "fuera"

    def _texto_presencia(self, j: Jugador, ahora: float, actividad: str | None = None) -> str:
        """Si la persona está conectada y qué está haciendo su Sim."""
        estado = self._estado_presencia(j, ahora)
        hace = duracion(ahora - j.ultima_actividad)
        if estado == "en_linea":
            partes = ["🟢 en línea"]
        elif estado == "ausente":
            partes = [f"🟡 ausente · hace {hace}"]
        else:
            partes = [f"⚫ fuera de línea · visto hace {hace}" if j.ultima_actividad else "⚫ fuera de línea"]
        haciendo = self._texto_accion(j, ahora)
        if haciendo:
            partes.append(haciendo)
        elif j.estado == "activo" and self._congelado(j, ahora):
            partes.append("❄️ Sim en pausa")
        elif estado == "en_linea" and actividad:
            partes.append(esc(actividad))
        return " · ".join(partes)

    def _tocar(self, j: Jugador, avisar_conexion: bool = True, jugada: bool = True) -> Resultado:
        """Marca actividad: quien usa el bot aparece en línea y su sala se actualiza.

        `jugada` indica una acción de juego (el chat no lo es): mantiene el reloj del Sim corriendo.
        """
        ahora = self.reloj()
        eventos = self._vivir(j, ahora)
        estaba = self._estado_presencia(j, ahora)
        if jugada and j.estado == "activo" and not self._congelado(j, ahora):
            j.ultima_jugada = ahora
        j.ultima_actividad = ahora
        j.salio = 0
        cambio = j.presencia != "en_linea"
        j.presencia = "en_linea"
        avisar = (
            avisar_conexion and estaba == "fuera" and j.activo
            and ahora - j.aviso_conexion_ts > AVISO_CONEXION_CADA
        )
        if avisar:
            j.aviso_conexion_ts = ahora
        self.db.guardar_jugador(j)
        uc = self._ultima(j)
        if estaba == "fuera" or not uc.conectado_desde:
            uc.conectado_desde = ahora
            uc.desconectado = None
            self.db.guardar_ultima_conexion(uc)
        res = Resultado(notas=[texto for texto, _ in eventos])
        if not j.activo:
            return res
        if cambio:
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        if avisar:
            for o in self._companeros(j):
                if o.avisos_conexion:
                    res.avisos.append(Aviso(o.id, f"🟢 {self._firma(j)} entró a la sala.", [[("🏠 Ver la sala", "sala")]]))
        return res

    def _salir(self, j: Jugador) -> Resultado:
        ahora = self.reloj()
        j.salio = 1
        j.presencia = "fuera"
        self.db.guardar_jugador(j)
        uc = self._ultima(j)
        uc.desconectado = ahora
        self.db.guardar_ultima_conexion(uc)
        res = Resultado(ediciones=self._refrescar_sala(j.sala_id, excepto=j.id))
        res.pantalla = Pantalla(
            "🚪 <b>Saliste del juego.</b>\n"
            "Ahora apareces ⚫ fuera de línea. Tu Sim termina lo que esté haciendo y luego queda en pausa ❄️.\n\n"
            f"Guardé dónde estabas (<b>{uc.lugar or LUGARES['sala'][0]}</b>): al volver, sigues desde ahí.\n"
            "Los mensajes de tu sala te seguirán llegando. Para volver, toca el botón o escribe /start.",
            [[("🔁 Volver a entrar", "volver")]],
        )
        return res

    # ------------------------------------------------------------------
    # Sala y chat interno
    # ------------------------------------------------------------------

    def _firma(self, j: Jugador) -> str:
        return f"{P.avatar(j.ap)} <b>{esc(j.personaje)}</b>"

    def _firma_animo(self, j: Jugador) -> str:
        """La firma con el color de su ánimo al lado (en sus mensajes): '🧑🏽 <b>Luis</b> 🟣'."""
        color = P.color_animo(j.ap)
        return f"{self._firma(j)} {color}" if color else self._firma(j)

    def _companeros(self, j: Jugador) -> list[Jugador]:
        return [m for m in self.db.miembros_sala(j.sala_id) if m.id != j.id]

    def _refrescar_sala(self, sala_id: int | None, excepto: int | None = None) -> list[Edicion]:
        return [
            Edicion(m.id, m.msg_sala, self._pantalla_viva(m))
            for m in self.db.miembros_sala(sala_id)
            if m.id != excepto and m.msg_sala and m.estado == "activo"
        ]

    def _pantalla_viva(self, j: Jugador) -> Pantalla:
        """La pantalla que se actualiza sola: la sala o el plano de la casa."""
        return self._pantalla_plano(j) if self._extras(j).get("vivo") == "plano" else self._pantalla_sala(j)

    def _pantalla_sala(self, j: Jugador, aviso: str | None = None) -> Pantalla:
        ahora = self.reloj()
        miembros = self.db.miembros_sala(j.sala_id)
        otros = [m for m in miembros if m.id != j.id]
        pausado = self._congelado(j, ahora)
        lineas = [aviso, ""] if aviso else []
        if pausado:
            lineas += [
                f"❄️ <b>Tu Sim está en pausa.</b> Pasaron {self.cfg.pausa_min} min sin jugar y dejó de "
                "gastar necesidades. Toca ▶️ Continuar para seguir.",
                "",
            ]
        estado = {"casados": " · 💒 Casados", "comprometidos": " · 💍 Comprometidos"}.get(
            self._estado_pareja(self._hogar(j.sala_id)), "")
        lineas += [f"🏠 <b>Sala de {esc(unir([m.personaje for m in miembros]))}</b>{estado}", ""]
        for m in miembros:
            animo = P.animo(m.ap)
            if m.id == j.id:
                cabeza, presencia = f"{self._firma(m)} (tú)", self._texto_presencia(m, ahora)
            else:
                uc = self.db.ultima_conexion(m.id)
                cabeza = self._firma(m)
                presencia = self._texto_presencia(m, ahora, uc.actividad if uc else None)
            lineas.append(f"{cabeza}{' · ' + animo if animo else ''}")
            lineas.append(f"      {presencia}")
            lineas.append(f"      🕒 {self._reloj(m)}")
        lineas.append("")
        if self._notas_sin_leer(j):
            lineas += ["📝 <b>Tienes una nota nueva en la nevera</b> (🏠 Casa → Notas).", ""]
        if otros:
            lineas.append(
                f"💬 Escribe aquí y le llegará a {esc(unir([o.personaje for o in otros]))}: "
                "texto, fotos, stickers o notas de voz."
            )
        else:
            lineas.append("🎮 Por ahora juegas sin compañía. Cuando quieras, invita a alguien con 💌.")
        botones = [
            [("🎮 Menú", "menu")],
            [("🎭 Mi ánimo", "animos"), ("🪪 Personajes", "pjs")],
            [("💌 Invitar", "invitar"), ("⚙️ Ajustes", "ajustes")],
            [("🔄 Actualizar", "act"), ("🚪 Salir", "salir")],
        ]
        if pausado:
            botones.insert(0, [CONTINUAR])
        return Pantalla("\n".join(lineas), botones, es_sala=True, clave="sala")

    def _sin_companeros(self) -> Pantalla:
        return Pantalla(
            "📭 Todavía no hay nadie más en tu sala que pueda leerte.\n"
            "Invita a tu pareja y lo que escribas le llegará al instante.",
            [[("💌 Invitar", "invitar"), SALA]],
        )

    def _chat(self, j: Jugador, texto: str) -> Resultado:
        res = self._tocar(j, avisar_conexion=False, jugada=False)
        otros = self._companeros(j)
        if not otros:
            res.pantalla = self._sin_companeros()
            res.nuevo = True
            return res
        largo = 3800
        while len(esc(texto[:largo])) > 3800:
            largo = largo * 3 // 4
        cuerpo = esc(texto[:largo])
        for o in otros:
            res.avisos.append(Aviso(o.id, f"💬 {self._firma_animo(j)}: {cuerpo}", chat=True))
        self._anotar(j.id, res, CHATEANDO)
        return res

    # ------------------------------------------------------------------
    # Botones del menú
    # ------------------------------------------------------------------

    def _b_sala(self, j: Jugador, arg: str, res: Resultado) -> None:
        res.pantalla = self._pantalla_sala(j)

    def _b_actualizar(self, j: Jugador, arg: str, res: Resultado) -> None:
        res.pantalla = self._pantalla_sala(j)
        res.alerta = "🔄 Actualizado"

    def _b_personajes(self, j: Jugador, arg: str, res: Resultado) -> None:
        lineas = ["🪪 <b>Personajes de la sala</b>", ""]
        for m in self.db.miembros_sala(j.sala_id):
            yo = " (tú)" if m.id == j.id else ""
            lineas += [f"{self._firma(m)}{yo}", f"<i>{esc(P.descripcion(m.personaje, m.ap))}</i>", ""]
        res.pantalla = Pantalla(
            "\n".join(lineas).rstrip(),
            [
                [("🪞 Cambiar mi personaje", "apedit"), ("✏️ Cambiar nombre", "renombrar")],
                [("⬅️ Atrás", "mest")],
            ],
            clave="pjs",
        )

    def _b_ajustes(self, j: Jugador, arg: str, res: Resultado) -> None:
        avisos = "Sí" if j.avisos_conexion else "No"
        narracion = self._extras(j).get("narracion", True)
        fotos = self._extras(j).get("fotos", True)
        lugar = Z.nombre(self._zona(j), j.utc_offset)
        res.pantalla = Pantalla(
            "⚙️ <b>Ajustes</b>\n\n"
            f"👤 Personaje: {self._firma(j)}\n"
            f"🔔 Avisarme cuando alguien entra a mi sala: <b>{avisos}</b>\n"
            f"🎬 Mensajitos de lo que va pasando en cada acción: <b>{'Sí' if narracion else 'No'}</b>\n"
            f"📸 Con fotos estilo anime (gastan algo más de datos): <b>{'Sí' if fotos else 'No'}</b>\n"
            f"🕒 Tu hora local: {self._hora(j, self.reloj())} · {lugar}\n"
            f"🪪 Tu código de jugador (tu ID): <code>{j.id}</code>\n"
            f"🏷️ Versión del juego: {N.VERSION}"
            + (f"\n🚪 Jugadores nuevos: <b>{'🔓 abierto' if self._registro_abierto() else '🔒 cerrado'}</b>"
               if j.id in self.cfg.admins else ""),
            [
                [("🔕 Desactivar avisos" if j.avisos_conexion else "🔔 Activar avisos", "avisos")],
                [("🎬 Apagar los mensajitos" if narracion else "🎬 Encender los mensajitos", "narr"),
                 ("📸 Quitar las fotos" if fotos else "📸 Poner las fotos", "fotos")],
                [("🪞 Cambiar personaje", "apedit"), ("✏️ Cambiar nombre", "renombrar")],
                [("🕒 Mi hora local", "zona"), ("🧾 Mi última conexión", "conexion")],
                *([[("🔓 Abrir a jugadores nuevos" if not self._registro_abierto() else "🔒 Cerrar a jugadores nuevos",
                     "registro")]] if j.id in self.cfg.admins else []),
                [("⬅️ Atrás", "mest")],
            ],
            clave="ajustes",
        )

    def _b_zona(self, j: Jugador, arg: str, res: Resultado) -> None:
        """zona · zona:otra · zona:<minutos respecto a UTC>: el reloj del Sim usa la hora real del jugador."""
        if arg.lstrip("-").isdigit() and int(arg) in ZONAS_HORARIAS:
            j.utc_offset = int(arg)
            extras = self._extras(j)
            extras.update(hora_ok=True, zona="")  # hora fija, sin horario de verano
            j.extras = json.dumps(extras)
            self.db.guardar_jugador(j)
            res.alerta = f"🕒 Listo: tu hora es {self._hora(j, self.reloj())}"
            self._b_ajustes(j, "", res)
            return
        ahora = self.reloj()
        if arg == "otra":
            opciones = [(f"🕒 {_hora_en(o, ahora)}", f"zona:{o}") for o in ZONAS_HORARIAS]
            res.pantalla = Pantalla(
                "🕒 <b>Tu hora local</b>\n\n<b>¿Qué hora es ahora donde estás?</b>\n"
                "<i>Con una hora fija no se ajusta sola al horario de verano.</i>",
                [opciones[k:k + 4] for k in range(0, len(opciones), 4)] + [[("⬅️ Atrás", "zona")]],
                clave="ajustes",
            )
            return
        res.pantalla = Pantalla(
            "🕒 <b>Tu hora local</b>\n\nTu Sim vive con la hora real de tu lugar (los horarios, las comidas, el "
            "trabajo y los eventos), y se ajusta sola cuando cambia el horario de verano.\n\n"
            f"Ahora: {self._hora(j, ahora)} · {Z.nombre(self._zona(j), j.utc_offset)}\n\n<b>¿Dónde vives?</b>",
            self._botones_lugares(ahora, "") + [[("🕒 Otro lugar: elegir la hora", "zona:otra")],
                                                [("⬅️ Atrás", "ajustes")]],
            clave="ajustes",
        )

    def _botones_lugares(self, ahora: float, sufijo: str) -> Botones:
        return en_filas([(f"{nombre} {_hora_en(Z.offset(clave, ahora), ahora)}", f"zonal:{clave}{sufijo}")
                         for clave, nombre, _ in Z.LUGARES])

    def _b_zona_lugar(self, j: Jugador, arg: str, res: Resultado) -> None:
        """zonal:<lugar>[:hor]: seguir la hora real de ese lugar (y volver a Ajustes o al horario)."""
        clave, _, volver = arg.partition(":")
        if clave not in Z.POR_CLAVE:
            self._b_zona(j, "", res)
            return
        extras = self._extras(j)
        extras.update(hora_ok=True, zona=clave)
        j.extras = json.dumps(extras)
        j.utc_offset = Z.offset(clave, self.reloj())
        self.db.guardar_jugador(j)
        res.alerta = f"🕒 Listo: tu hora es {self._hora(j, self.reloj())} ({Z.POR_CLAVE[clave][0]})"
        if volver == "hor":
            self._b_horario(j, "", res)
        else:
            self._b_ajustes(j, "", res)

    def _b_avisos(self, j: Jugador, arg: str, res: Resultado) -> None:
        j.avisos_conexion = 0 if j.avisos_conexion else 1
        self.db.guardar_jugador(j)
        self._b_ajustes(j, arg, res)

    def _pantalla_renombrar(self, j: Jugador) -> Pantalla:
        return Pantalla(
            f"✏️ Tu personaje se llama <b>{esc(j.personaje)}</b>.\nEscribe el nuevo nombre:",
            [[("❌ Cancelar", "sala")]],
            clave="renombrar",
        )

    def _b_renombrar(self, j: Jugador, arg: str, res: Resultado) -> None:
        j.estado = "renombrando"
        self.db.guardar_jugador(j)
        res.pantalla = self._pantalla_renombrar(j)

    def _b_conexion(self, j: Jugador, arg: str, res: Resultado) -> None:
        res.pantalla = self._pantalla_conexion(j)

    # --- invitaciones ---

    def _hay_lugar(self, j: Jugador) -> bool:
        return len(self.db.miembros_sala(j.sala_id)) < self.cfg.max_sala

    def _b_invitar(self, j: Jugador, arg: str, res: Resultado) -> None:
        """💌 Invitar: tu código y las dos formas de invitar (las dos invitan igual)."""
        res.pantalla = Pantalla(
            "💌 <b>Invitar</b>\n\n"
            + ("🔒 <b>Ahora el juego está cerrado a jugadores nuevos.</b>\n\n" if not self._registro_abierto() else "")
            + f"🪪 <b>Tu código</b> ({self._firma(j)}): <code>{j.id}</code>\n"
            "<i>Es tu ID de jugador. Tócalo para copiarlo y pásaselo a quien quiera invitarte.</i>\n\n"
            "<b>Dos formas de invitar</b> (las dos invitan igual):\n"
            "📤 <b>Pasar el bot</b>: le mandas un enlace y, al abrirlo, le llega tu invitación directamente.\n"
            "⌨️ <b>Con su código</b>: escribes <code>invitar_</code> y su código (su ID de jugador).\n\n"
            "En las dos eliges quién es: 💞 pareja, 👨‍👩‍👧 familia, 🤝 amistad o 💼 trabajo o estudios. "
            "Solo la pareja entra a tu sala; los demás juegan en la suya.\n\n"
            "🎮 No hace falta esperar: puedes jugar ya y tu pareja se une cuando entre.",
            [
                [("📤 Pasar el bot a alguien", "invq")],
                [("⌨️ Invitar con su código", "invcod")],
                [("🎮 Jugar sin esperar", "sim"), ("📋 Invitaciones enviadas", "invs")],
                [SALA],
            ],
            clave="invitar",
        )

    def _b_invitar_con_codigo(self, j: Jugador, arg: str, res: Resultado) -> None:
        res.pantalla = Pantalla(
            "⌨️ <b>Invitar con su código</b>\n\n"
            f"1️⃣ Pídele que abra @{esc(self.bot_usuario)} y toque <b>Iniciar</b> (si ya juega, que mire en "
            "💌 Invitar).\n"
            "2️⃣ El bot le mostrará <b>su código</b>: su ID de jugador.\n"
            "3️⃣ Cuando te lo pase, escríbelo aquí así:\n"
            "<code>invitar_CÓDIGO</code>   (por ejemplo: <code>invitar_123456789</code>)\n"
            "4️⃣ Eliges quién es para ti y le llega la invitación para aceptarla.",
            [[("📤 Mejor pasarle el bot", "invq")], [("⬅️ Atrás", "invitar")]],
            clave="invitar",
        )

    def _b_pasar_bot(self, j: Jugador, tipo: str, res: Resultado) -> None:
        """invq · invq:<vínculo>: un enlace que invita directamente a quien lo abra."""
        if not self._registro_abierto():
            res.alerta = "🔒 El juego está cerrado a jugadores nuevos."
            self._b_invitar(j, "", res)
            return
        if tipo not in VINCULOS:
            res.pantalla = Pantalla(
                "📤 <b>Pasar el bot a alguien</b>\n\n¿Quién es esa persona para ti?\n"
                "<i>Solo la pareja entra a tu sala; los demás tienen la suya.</i>",
                self._botones_vinculo(j, lambda t: f"invq:{t}") + [[("⬅️ Atrás", "invitar")]],
                clave="invitar",
            )
            return
        if tipo == "pareja" and not self._hay_lugar(j):
            res.alerta = "Tu sala ya está completa."
            self._b_pasar_bot(j, "", res)
            return
        ahora = self.reloj()
        inv = next((i for i in self.db.invitaciones_de(j.id, 50)
                    if i.vigente(ahora) and i.para_id is None and i.tipo == tipo), None)
        if inv is None:
            activas = [i for i in self.db.invitaciones_de(j.id, 50) if i.vigente(ahora)]
            if len(activas) >= self.cfg.max_invitaciones_activas:
                res.alerta = f"Ya tienes {len(activas)} invitaciones sin respuesta. Anula alguna en 📋."
                self._b_mis_invitaciones(j, "", res)
                return
            inv = Invitacion(
                codigo=self._codigo_libre(LARGO_CODIGO_INVITACION, self.db.invitacion),
                creador=j.id, tipo=tipo, sala_id=j.sala_id if tipo == "pareja" else None,
                creada=ahora, expira=ahora + self.cfg.invitacion_dias * DIA,
            )
            self.db.guardar_invitacion(inv)
        enlace = f"https://t.me/{self.bot_usuario}?start=inv_{inv.codigo}"
        mensaje = (
            f"¡Te invito a jugar {self.cfg.nombre_juego} conmigo! 💞 Abre el enlace y toca Iniciar: "
            "te llega mi invitación."
        )
        compartir = f"https://t.me/share/url?url={quote(enlace, safe='')}&text={quote(mensaje)}"
        res.pantalla = Pantalla(
            f"📤 <b>Invitación directa</b> · {vinculo(tipo)}\n\n"
            "1️⃣ Toca <b>Enviar el enlace</b> y elige a quién mandárselo (o copia el enlace).\n"
            "2️⃣ Cuando lo abra y toque <b>Iniciar</b>, le llega tu invitación para aceptarla.\n\n"
            f"🔗 <code>{esc(enlace)}</code>\n\n"
            f"🔐 Sirve para una sola persona y vence en {duracion(inv.expira - ahora + MINUTO)}.",
            [
                [("📤 Enviar el enlace", compartir)],
                [("❌ Anular este enlace", f"anular:{inv.codigo}"), ("⬅️ Atrás", "invitar")],
            ],
            clave="invitar",
        )

    def _abrir_enlace(self, uid: int, nombre_tg: str, codigo: str) -> Resultado | None:
        """Alguien abrió un enlace de invitación: la invitación le llega directamente."""
        ahora = self.reloj()
        inv = self.db.invitacion(codigo)
        if inv is None or not inv.vigente(ahora) or inv.para_id not in (None, uid):
            return None
        creador = self.db.jugador(inv.creador)
        if creador is None or not creador.activo:
            return None
        if creador.id == uid:
            return Resultado(pantalla=Pantalla(
                "📤 Este es <b>tu</b> enlace de invitación: pásaselo a la otra persona.", [[("💌 Invitar", "invitar")]]
            ), nuevo=True)
        j = self.db.jugador(uid)
        if j is None and uid not in self.cfg.admins and not self._registro_abierto():
            return Resultado(pantalla=self._pantalla_cerrado(), nuevo=True)
        if j is None and uid not in self.cfg.admins:
            self._registrar_visitante(uid, nombre_tg)
            inv.para_id = uid
            self.db.guardar_invitacion(inv)
            return Resultado(pantalla=self._pantalla_invitado(inv), nuevo=True)
        if (
            j is not None and j.activo and inv.tipo == "pareja" and j.sala_id != creador.sala_id
            and self._pareja_en_sala(j) is None and self._hay_lugar(creador)
        ):
            inv.para_id = uid
            self.db.guardar_invitacion(inv)
            return Resultado(pantalla=Pantalla(
                f"💌 <b>¡Tienes una invitación!</b>\n\n{self._firma(creador)} te invita a mudarte a su sala como su "
                "pareja. Tu Sim, tus ahorros de la cuenta compartida y tus cosas se mudan contigo.",
                [[("✅ Aceptar y mudarme", f"aceptoj:{inv.codigo}")], [("❌ No, gracias", f"rechazoj:{inv.codigo}")]],
            ), nuevo=True)
        return None

    def _b_mis_invitaciones(self, j: Jugador, arg: str, res: Resultado) -> None:
        ahora = self.reloj()
        lineas = ["📋 <b>Invitaciones enviadas</b>", ""]
        botones: Botones = []
        invs = self.db.invitaciones_de(j.id, 10)
        if not invs:
            lineas.append("Todavía no has invitado a nadie.")
        for i in invs:
            v = self.db.visitante(i.para_id) if i.para_id else None
            otro = self.db.jugador(i.para_id) if i.para_id else None
            para = (v.nombre_tg if v and v.nombre_tg else otro.personaje if otro else
                    "📤 enlace sin abrir" if i.para_id is None else "alguien")
            tipo = vinculo(i.tipo)
            if i.usada_por:
                quien = self.db.jugador(i.usada_por)
                nombre = (quien.personaje or quien.nombre_tg) if quien else para
                lineas.append(f"✅ {esc(nombre)} · {tipo} · aceptada")
            elif i.anulada:
                lineas.append(f"🚫 {esc(para)} · {tipo} · anulada o rechazada")
            elif i.expira <= ahora:
                lineas.append(f"⌛ {esc(para)} · {tipo} · vencida")
            else:
                lineas.append(
                    f"🟢 {esc(para)} · {tipo} · esperando respuesta "
                    f"(vence en {duracion(i.expira - ahora + MINUTO)})"
                )
                botones.append([(f"❌ Anular invitación a {para}"[:60], f"anular:{i.codigo}")])
        botones.append([("💌 Invitar a alguien", "invitar"), SALA])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="invs")

    def _b_anular(self, j: Jugador, codigo: str, res: Resultado) -> None:
        inv = self.db.invitacion(codigo)
        if inv is not None and inv.creador == j.id and inv.vigente(self.reloj()):
            inv.anulada = 1
            self.db.guardar_invitacion(inv)
            res.alerta = "🚫 Invitación anulada"
        self._b_mis_invitaciones(j, "", res)
