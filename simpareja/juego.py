"""Lógica del juego, separada de Telegram para poder probarla sin conexión.

Cada entrada (comando, texto, botón) devuelve un `Resultado` que el bot traduce a
mensajes de Telegram: la pantalla para quien tocó, avisos para otras personas y
ediciones de las salas abiertas (para que el estado "en línea" se vea en vivo).
"""

from __future__ import annotations

import html
import json
import random
import re
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import quote

from . import apariencia as A
from .config import Config
from .db import DB, Invitacion, Jugador

Botones = list[list[tuple[str, str]]]


@dataclass
class Pantalla:
    texto: str
    botones: Botones = field(default_factory=list)
    es_sala: bool = False


@dataclass
class Aviso:
    para: int
    texto: str
    botones: Botones = field(default_factory=list)
    chat: bool = False  # mensaje del chat interno: si no se entrega, se avisa a quien lo mandó
    copiar: bool = False  # además, copiar el mensaje original (foto, sticker, nota de voz…)


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


ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para que no se confundan
LARGO_CODIGO = 8
NOMBRE_RE = re.compile(r"[^\W\d_][\w '.\-]{1,19}")
CODIGO_RE = re.compile(r"[A-Z0-9]{6,12}")
MINUTO = 60
DIA = 86400
AVISO_CONEXION_CADA = 30 * MINUTO
MAX_FALLOS_CODIGO = 5
VENTANA_FALLOS = 15 * MINUTO

SALA = ("🏠 Sala", "sala")


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


def normalizar_codigo(texto: str) -> str:
    return re.sub(r"[\s\-]", "", texto).upper()


def en_filas(botones: list[tuple[str, str]], por_fila: int = 2) -> Botones:
    return [botones[i:i + por_fila] for i in range(0, len(botones), por_fila)]


class Juego:
    def __init__(self, db: DB, cfg: Config, reloj=time.time, rng: random.Random | None = None):
        self.db = db
        self.cfg = cfg
        self.reloj = reloj
        self.rng = rng or random.Random()
        self.bot_usuario = "sims000bot"
        self._fallos: dict[int, list[float]] = {}

    # ------------------------------------------------------------------
    # Entradas desde Telegram
    # ------------------------------------------------------------------

    def inicio(self, uid: int, nombre_tg: str, carga: str | None = None) -> Resultado:
        """/start, con o sin código de invitación."""
        j = self.db.jugador(uid)
        if j is None:
            if carga:
                return self._entrar_con_codigo(uid, nombre_tg, carga)
            if uid in self.cfg.admins:
                return self._crear_jugador(uid, nombre_tg, None)
            return Resultado(pantalla=self._candado(uid), nuevo=True)
        if j.estado == "nombrando":
            return Resultado(pantalla=self._pedir_nombre(j), nuevo=True)
        if j.estado == "creando":
            return Resultado(pantalla=self._pantalla_creador(j), nuevo=True)
        if j.estado == "renombrando":
            j.estado = "activo"
        res = self._tocar(j)
        aviso = "ℹ️ Ya estás dentro del juego. Los enlaces de invitación son para gente nueva." if carga else None
        res.pantalla = self._pantalla_sala(j, aviso)
        res.nuevo = True
        return res

    def texto(self, uid: int, nombre_tg: str, texto: str) -> Resultado:
        j = self.db.jugador(uid)
        if j is None:
            if CODIGO_RE.fullmatch(normalizar_codigo(texto)):
                return self._entrar_con_codigo(uid, nombre_tg, texto)
            return Resultado(pantalla=self._candado(uid), nuevo=True)
        if j.estado in ("nombrando", "renombrando"):
            return self._recibir_nombre(j, texto)
        if j.estado == "creando":
            res = Resultado(pantalla=self._pantalla_creador(j), nuevo=True)
            res.pantalla.texto = "👇 Usa los botones para elegir.\n\n" + res.pantalla.texto
            return res
        return self._chat(j, texto)

    def media(self, uid: int) -> Resultado:
        """Foto, sticker, nota de voz, etc.: se reenvía a la sala como parte del chat."""
        j = self.db.jugador(uid)
        if j is None:
            return Resultado(pantalla=self._candado(uid), nuevo=True)
        if not j.activo:
            return Resultado(pantalla=Pantalla("✋ Primero termina de crear tu personaje."), nuevo=True)
        res = self._tocar(j, avisar_conexion=False)
        otros = self._companeros(j)
        if not otros:
            res.pantalla = self._sin_companeros()
            res.nuevo = True
            return res
        for o in otros:
            res.avisos.append(Aviso(o.id, f"💬 {self._firma(j)}:", chat=True, copiar=True))
        return res

    def boton(self, uid: int, nombre_tg: str, data: str) -> Resultado:
        j = self.db.jugador(uid)
        if j is None:
            return Resultado(pantalla=self._candado(uid))
        if j.estado == "nombrando":
            return Resultado(alerta="✍️ Primero escribe el nombre de tu personaje.")
        accion, _, arg = data.partition(":")
        if j.estado == "creando":
            if not accion.startswith("ap"):
                return Resultado(alerta="🧑‍🎨 Primero termina de crear tu personaje.")
            return self._creador(j, accion, arg, Resultado())
        if j.estado == "renombrando":
            j.estado = "activo"
        if accion == "salir":
            return self._salir(j)
        res = self._tocar(j)
        if accion.startswith("ap"):
            return self._creador(j, accion, arg, res)
        manejador = {
            "sala": self._b_sala,
            "act": self._b_actualizar,
            "invitar": self._b_invitar,
            "inv": self._b_generar,
            "ver": self._b_ver_invitacion,
            "invs": self._b_mis_invitaciones,
            "anular": self._b_anular,
            "pjs": self._b_personajes,
            "ajustes": self._b_ajustes,
            "avisos": self._b_avisos,
            "renombrar": self._b_renombrar,
        }.get(accion)
        if manejador is None:
            res.alerta = "Ese botón ya no funciona."
            res.pantalla = self._pantalla_sala(j)
            return res
        manejador(j, arg, res)
        return res

    def comando(self, uid: int, nombre_tg: str, nombre: str) -> Resultado:
        """Comandos de menú (/invitar, /sala, /ajustes…) que abren una pantalla en mensaje nuevo."""
        data = {"sala": "sala", "menu": "sala", "invitar": "invitar", "ajustes": "ajustes",
                "personajes": "pjs", "salir": "salir"}.get(nombre, "sala")
        res = self.boton(uid, nombre_tg, data)
        res.nuevo = True
        return res

    def unirme(self, uid: int, nombre_tg: str, codigo: str) -> Resultado:
        if self.db.jugador(uid) is not None:
            return self.inicio(uid, nombre_tg, codigo)
        return self._entrar_con_codigo(uid, nombre_tg, codigo)

    def ayuda(self) -> Pantalla:
        return Pantalla(
            f"❓ <b>{esc(self.cfg.nombre_juego)}: cómo funciona</b>\n\n"
            "🔐 Se entra <b>solo por invitación</b>: cada enlace sirve una vez.\n"
            "🧑‍🎨 Creas tu personaje: nombre, cuerpo, pelo, ojos, estilo…\n"
            "🎮 Puedes jugar sin compañía o 💌 invitar a tu pareja a tu sala.\n"
            "💬 En la sala, todo lo que escribas (texto, fotos, stickers, notas de voz) le llega a la otra persona.\n"
            "🟢 En la sala se ve quién está en línea, ausente o fuera de línea.\n\n"
            "Comandos: /start · /sala · /invitar · /personajes · /ajustes · /salir",
            [[SALA]],
        )

    def registrar_pantalla(self, uid: int, msg_id: int, es_sala: bool) -> None:
        """El bot avisa qué mensaje muestra la sala, para poder actualizarlo en vivo."""
        j = self.db.jugador(uid)
        if j is None:
            return
        if es_sala:
            j.msg_sala = msg_id
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
        """Se llama cada minuto: detecta quién pasó a ausente o fuera de línea."""
        ahora = self.reloj()
        res = Resultado()
        salas: set[int] = set()
        for j in self.db.jugadores_en_sala():
            estado = self._estado_presencia(j, ahora)
            if estado != j.presencia:
                j.presencia = estado
                self.db.guardar_jugador(j)
                salas.add(j.sala_id)
        for sala_id in salas:
            res.ediciones += self._refrescar_sala(sala_id)
        return res

    # ------------------------------------------------------------------
    # Entrada por invitación y creación del personaje
    # ------------------------------------------------------------------

    def _candado(self, uid: int) -> Pantalla:
        return Pantalla(
            f"🔒 <b>{esc(self.cfg.nombre_juego)} es solo por invitación.</b>\n\n"
            "Pídele a alguien que ya juega que te envíe su enlace de invitación y ábrelo.\n"
            "Si te dieron un código, escríbelo aquí.\n\n"
            f"🆔 Tu ID de Telegram: <code>{uid}</code>"
        )

    def _fallos_recientes(self, uid: int, ahora: float) -> list[float]:
        fallos = [t for t in self._fallos.get(uid, []) if ahora - t < VENTANA_FALLOS]
        self._fallos[uid] = fallos
        return fallos

    def _entrar_con_codigo(self, uid: int, nombre_tg: str, texto: str) -> Resultado:
        ahora = self.reloj()
        if len(self._fallos_recientes(uid, ahora)) >= MAX_FALLOS_CODIGO:
            return Resultado(
                pantalla=Pantalla("⏳ Demasiados intentos. Espera unos minutos y vuelve a probar."),
                nuevo=True,
            )
        inv = self.db.invitacion(normalizar_codigo(texto))
        creador = self.db.jugador(inv.creador) if inv else None
        if inv is None or not inv.vigente(ahora) or creador is None or not creador.activo:
            self._fallos[uid].append(ahora)
            return Resultado(
                pantalla=Pantalla(
                    "❌ Ese enlace o código no es válido, ya se usó o venció.\n"
                    "Pídele uno nuevo a quien te invitó."
                ),
                nuevo=True,
            )
        inv.usada_por = uid
        inv.usada_ts = ahora
        self.db.guardar_invitacion(inv)
        res = self._crear_jugador(uid, nombre_tg, inv)
        quien = esc(nombre_tg) if nombre_tg else "Alguien"
        res.avisos.append(Aviso(creador.id, f"🎟️ <b>{quien}</b> abrió tu invitación y está creando su personaje…"))
        return res

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
        )
        self.db.guardar_jugador(j)
        return Resultado(pantalla=self._pedir_nombre(j), nuevo=True)

    def _pedir_nombre(self, j: Jugador) -> Pantalla:
        texto = f"🎉 <b>¡Te damos la bienvenida a {esc(self.cfg.nombre_juego)}!</b>\n\n"
        anfitrion = self.db.jugador(j.invitado_por) if j.invitado_por else None
        if anfitrion:
            texto += f"Te invitó <b>{esc(anfitrion.personaje)}</b>.\n\n"
        texto += "Primero vas a crear tu personaje.\n✍️ <b>¿Cómo se llamará?</b> Escribe el nombre aquí abajo."
        return Pantalla(texto)

    def _recibir_nombre(self, j: Jugador, texto: str) -> Resultado:
        nombre = " ".join(texto.split())
        if not NOMBRE_RE.fullmatch(nombre):
            botones = [[("❌ Cancelar", "sala")]] if j.estado == "renombrando" else []
            return Resultado(
                pantalla=Pantalla(
                    "✋ Ese nombre no me sirve. Usa entre 2 y 20 caracteres, empezando por una letra "
                    "(puede llevar espacios). Prueba otra vez:",
                    botones,
                ),
                nuevo=True,
            )
        j.personaje = nombre
        if j.estado == "renombrando":
            j.estado = "activo"
            res = self._tocar(j)
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
            res.pantalla = self._pantalla_sala(j, f"✏️ Ahora tu personaje se llama <b>{esc(nombre)}</b>.")
            res.nuevo = True
            return res
        j.estado = "creando"
        j.borrador = "{}"
        self.db.guardar_jugador(j)
        return Resultado(pantalla=self._pantalla_creador(j), nuevo=True)

    # --- creador de personaje (sirve para crearlo y para cambiar la apariencia) ---

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
        if accion == "ap":
            campo, _, valor = arg.partition(":")
            c = A.POR_CLAVE.get(campo)
            if c is not None and not c.multiple:
                A.elegir(b, campo, A.al_azar(c, self.rng) if valor == "?" else valor)
        elif accion == "apd":
            if arg == "?":
                b["detalles"] = A.al_azar(A.POR_CLAVE["detalles"], self.rng)
                b.pop("_det", None)
            else:
                b["_det"] = A.alternar_detalle(b.get("_det", b.get("detalles", [])), arg)
                campo_actual = A.POR_CLAVE["detalles"]
        elif accion == "apdl":
            b["detalles"] = b.pop("_det", b.get("detalles", []))
        elif accion == "ape":
            campo_actual = A.POR_CLAVE.get(arg)
            if campo_actual is not None and campo_actual.multiple:
                b["_det"] = list(b.get("detalles", []))
        elif accion == "apr":
            b = A.todo_al_azar(self.rng)
        elif accion == "apx" and j.estado != "creando":
            j.borrador = None
            self.db.guardar_jugador(j)
            self._b_personajes(j, "", res)
            return res
        elif accion == "apok" and A.completa(b):
            return self._confirmar_apariencia(j, b, res)
        self._guardar_borrador(j, b)
        res.pantalla = self._pantalla_creador(j, campo_actual)
        return res

    def _pantalla_creador(self, j: Jugador, campo: A.Campo | None = None) -> Pantalla:
        b = self._borrador(j)
        campo = campo or A.siguiente_campo(b)
        if campo is None:
            return self._pantalla_ficha(j, b)
        visibles = A.campos_visibles(b)
        paso = next((i for i, c in enumerate(visibles) if c.clave == campo.clave), 0) + 1
        verbo = "Creando" if j.estado == "creando" else "Editando"
        texto = (
            f"🧑‍🎨 <b>{verbo} a {esc(j.personaje)}</b> {A.avatar(b)}\n"
            f"Paso {paso} de {len(visibles)} · {campo.emoji} {campo.titulo}\n\n"
            f"<b>{campo.pregunta}</b>"
        )
        if campo.multiple:
            elegidos = b.get("_det", b.get("detalles", []))
            opciones = [
                (("✅ " if o.clave in elegidos else "") + f"{o.emoji} {o.nombre}", f"apd:{o.clave}")
                for o in campo.opciones
            ]
            botones = en_filas(opciones) + [[("🎲 Al azar", "apd:?"), ("✅ Listo", "apdl")]]
        else:
            actual = b.get(campo.clave)
            opciones = [
                (("✅ " if o.clave == actual else "") + f"{o.emoji} {o.nombre}", f"ap:{campo.clave}:{o.clave}")
                for o in campo.opciones
            ]
            botones = en_filas(opciones) + [[("🎲 Al azar", f"ap:{campo.clave}:?")]]
        if A.completa(b):
            botones.append([("⬅️ Volver a la ficha", "apf")])
        elif paso > 1:
            botones.append([("⬅️ Atrás", f"ape:{visibles[paso - 2].clave}")])
        return Pantalla(texto, botones)

    def _pantalla_ficha(self, j: Jugador, b: dict) -> Pantalla:
        lineas = [f"🪪 <b>Ficha de {esc(j.personaje)}</b>  {A.avatar(b)}", ""]
        for c in A.campos_visibles(b):
            lineas.append(f"{c.emoji} {c.titulo}: <b>{A.etiqueta(b, c.clave)}</b>")
        lineas += ["", f"<i>{esc(A.descripcion(j.personaje, b))}</i>", "", "¿Te gusta cómo quedó?"]
        editar = [(f"✏️ {c.titulo}", f"ape:{c.clave}") for c in A.campos_visibles(b)]
        botones = en_filas(editar) + [
            [("🎲 Sorpréndeme (todo al azar)", "apr")],
            [("✅ ¡Listo, así me gusta!", "apok")],
        ]
        if j.estado != "creando":
            botones.append([("❌ Cancelar cambios", "apx")])
        return Pantalla("\n".join(lineas), botones)

    def _confirmar_apariencia(self, j: Jugador, b: dict, res: Resultado) -> Resultado:
        b.pop("_det", None)
        j.apariencia = json.dumps(b, ensure_ascii=False)
        j.borrador = None
        if j.estado != "creando":
            self.db.guardar_jugador(j)
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
            self._b_personajes(j, "", res)
            res.alerta = "✅ Apariencia guardada"
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
        res = self._tocar(j, avisar_conexion=False)
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
            f"✨ <b>¡Personaje creado!</b> {A.avatar(j.ap)} <b>{esc(j.personaje)}</b>",
            "",
            f"<i>{esc(A.descripcion(j.personaje, j.ap))}</i>",
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
            "🎮 <b>Jugar</b>: entra a tu sala y empieza, con o sin compañía.",
            "💌 <b>Invitar</b>: manda un enlace a tu pareja o a quien quieras.",
        ]
        return Pantalla("\n".join(lineas), [[("🎮 Jugar", "sala"), ("💌 Invitar", "invitar")]])

    # ------------------------------------------------------------------
    # Presencia (en línea / ausente / fuera de línea)
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

    def _texto_presencia(self, j: Jugador, ahora: float) -> str:
        estado = self._estado_presencia(j, ahora)
        hace = duracion(ahora - j.ultima_actividad)
        if estado == "en_linea":
            return "🟢 en línea"
        if estado == "ausente":
            return f"🟡 ausente · activo hace {hace}"
        if j.ultima_actividad:
            return f"⚫ fuera de línea · visto hace {hace}"
        return "⚫ fuera de línea"

    def _tocar(self, j: Jugador, avisar_conexion: bool = True) -> Resultado:
        """Marca actividad: quien usa el bot aparece en línea y su sala se actualiza."""
        ahora = self.reloj()
        estaba = self._estado_presencia(j, ahora)
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
        res = Resultado()
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
        j.salio = 1
        j.presencia = "fuera"
        self.db.guardar_jugador(j)
        res = Resultado(ediciones=self._refrescar_sala(j.sala_id, excepto=j.id))
        res.pantalla = Pantalla(
            "🚪 <b>Saliste de la sala.</b>\n"
            "Ahora apareces ⚫ fuera de línea.\n\n"
            "Los mensajes de tu sala te seguirán llegando aquí. "
            "Para volver, toca el botón o escribe /start.",
            [[("🏠 Volver a entrar", "sala")]],
        )
        return res

    # ------------------------------------------------------------------
    # Sala y chat interno
    # ------------------------------------------------------------------

    def _firma(self, j: Jugador) -> str:
        return f"{A.avatar(j.ap)} <b>{esc(j.personaje)}</b>"

    def _companeros(self, j: Jugador) -> list[Jugador]:
        return [m for m in self.db.miembros_sala(j.sala_id) if m.id != j.id]

    def _refrescar_sala(self, sala_id: int | None, excepto: int | None = None) -> list[Edicion]:
        return [
            Edicion(m.id, m.msg_sala, self._pantalla_sala(m))
            for m in self.db.miembros_sala(sala_id)
            if m.id != excepto and m.msg_sala and m.estado == "activo"
        ]

    def _pantalla_sala(self, j: Jugador, aviso: str | None = None) -> Pantalla:
        ahora = self.reloj()
        miembros = self.db.miembros_sala(j.sala_id)
        otros = [m for m in miembros if m.id != j.id]
        lineas = [aviso, ""] if aviso else []
        lineas += [f"🏠 <b>Sala de {esc(unir([m.personaje for m in miembros]))}</b>", ""]
        for m in miembros:
            yo = " (tú)" if m.id == j.id else ""
            lineas.append(f"{self._firma(m)}{yo} — {self._texto_presencia(m, ahora)}")
        lineas.append("")
        if otros:
            lineas.append(
                f"💬 Escribe aquí y le llegará a {esc(unir([o.personaje for o in otros]))}: "
                "texto, fotos, stickers o notas de voz."
            )
        else:
            lineas.append("🎮 Por ahora juegas sin compañía. Cuando quieras, invita a alguien con 💌.")
        lineas += ["", "🚧 <i>Próximamente: necesidades, casa, trabajo y citas.</i>"]
        botones = [
            [("💌 Invitar", "invitar"), ("🪪 Personajes", "pjs")],
            [("🔄 Actualizar", "act"), ("⚙️ Ajustes", "ajustes")],
            [("🚪 Salir", "salir")],
        ]
        return Pantalla("\n".join(lineas), botones, es_sala=True)

    def _sin_companeros(self) -> Pantalla:
        return Pantalla(
            "📭 Todavía no hay nadie más en tu sala que pueda leerte.\n"
            "Invita a tu pareja y lo que escribas le llegará al instante.",
            [[("💌 Invitar", "invitar"), SALA]],
        )

    def _chat(self, j: Jugador, texto: str) -> Resultado:
        res = self._tocar(j, avisar_conexion=False)
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
            res.avisos.append(Aviso(o.id, f"💬 {self._firma(j)}: {cuerpo}", chat=True))
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
            lineas += [f"{self._firma(m)}{yo}", f"<i>{esc(A.descripcion(m.personaje, m.ap))}</i>", ""]
        res.pantalla = Pantalla(
            "\n".join(lineas).rstrip(),
            [
                [("🪞 Cambiar mi apariencia", "apedit"), ("✏️ Cambiar nombre", "renombrar")],
                [SALA],
            ],
        )

    def _b_ajustes(self, j: Jugador, arg: str, res: Resultado) -> None:
        avisos = "Sí" if j.avisos_conexion else "No"
        res.pantalla = Pantalla(
            "⚙️ <b>Ajustes</b>\n\n"
            f"👤 Personaje: {self._firma(j)}\n"
            f"🔔 Avisarme cuando alguien entra a mi sala: <b>{avisos}</b>\n"
            f"🆔 Tu ID de Telegram: <code>{j.id}</code>",
            [
                [("🔕 Desactivar avisos" if j.avisos_conexion else "🔔 Activar avisos", "avisos")],
                [("🪞 Cambiar apariencia", "apedit"), ("✏️ Cambiar nombre", "renombrar")],
                [SALA],
            ],
        )

    def _b_avisos(self, j: Jugador, arg: str, res: Resultado) -> None:
        j.avisos_conexion = 0 if j.avisos_conexion else 1
        self.db.guardar_jugador(j)
        self._b_ajustes(j, arg, res)

    def _b_renombrar(self, j: Jugador, arg: str, res: Resultado) -> None:
        j.estado = "renombrando"
        self.db.guardar_jugador(j)
        res.pantalla = Pantalla(
            f"✏️ Tu personaje se llama <b>{esc(j.personaje)}</b>.\nEscribe el nuevo nombre:",
            [[("❌ Cancelar", "sala")]],
        )

    # --- invitaciones ---

    def _hay_lugar(self, j: Jugador) -> bool:
        return len(self.db.miembros_sala(j.sala_id)) < self.cfg.max_sala

    def _b_invitar(self, j: Jugador, arg: str, res: Resultado) -> None:
        botones = []
        if self._hay_lugar(j):
            botones.append([("💞 A mi pareja (entra a mi sala)", "inv:pareja")])
        botones.append([("👋 A otra persona (con su propia sala)", "inv:amigo")])
        botones.append([("📋 Mis invitaciones", "invs"), SALA])
        res.pantalla = Pantalla(
            "💌 <b>Invitar a un jugador</b>\n\n"
            "El juego es solo por invitación. Cada enlace sirve <b>una sola vez</b> "
            "y funciona en cualquier país donde haya Telegram.\n\n"
            "¿A quién quieres invitar?",
            botones,
        )

    def _b_generar(self, j: Jugador, tipo: str, res: Resultado) -> None:
        ahora = self.reloj()
        if tipo not in ("pareja", "amigo"):
            self._b_invitar(j, "", res)
            return
        if tipo == "pareja":
            if not self._hay_lugar(j):
                res.alerta = "Tu sala ya está completa."
                self._b_invitar(j, "", res)
                return
            pendientes = self.db.invitaciones_pareja_vigentes(j.sala_id, ahora)
            if len(self.db.miembros_sala(j.sala_id)) + len(pendientes) >= self.cfg.max_sala:
                res.pantalla = self._pantalla_invitacion(
                    pendientes[0], "ℹ️ Ya tenías esta invitación de pareja sin usar."
                )
                return
        activas = [i for i in self.db.invitaciones_de(j.id, 50) if i.vigente(ahora)]
        if len(activas) >= self.cfg.max_invitaciones_activas:
            res.alerta = f"Ya tienes {len(activas)} invitaciones sin usar. Anula alguna en 📋 Mis invitaciones."
            self._b_invitar(j, "", res)
            return
        inv = Invitacion(
            codigo=self._codigo_nuevo(),
            creador=j.id,
            tipo=tipo,
            sala_id=j.sala_id if tipo == "pareja" else None,
            creada=ahora,
            expira=ahora + self.cfg.invitacion_dias * DIA,
        )
        self.db.guardar_invitacion(inv)
        res.pantalla = self._pantalla_invitacion(inv)

    def _codigo_nuevo(self) -> str:
        while True:
            codigo = "".join(secrets.choice(ALFABETO) for _ in range(LARGO_CODIGO))
            if self.db.invitacion(codigo) is None:
                return codigo

    def enlace(self, codigo: str) -> str:
        return f"https://t.me/{self.bot_usuario}?start={codigo}"

    def _pantalla_invitacion(self, inv: Invitacion, nota: str | None = None) -> Pantalla:
        enlace = self.enlace(inv.codigo)
        pareja = inv.tipo == "pareja"
        mensaje = f"¡Te invito a jugar {self.cfg.nombre_juego} conmigo! 💞"
        compartir = f"https://t.me/share/url?url={quote(enlace, safe='')}&text={quote(mensaje)}"
        lineas = [nota, ""] if nota else []
        lineas += [
            f"{'💞' if pareja else '👋'} <b>Invitación lista</b>",
            "",
            f"Envíale este enlace a {'tu pareja' if pareja else 'esa persona'} "
            "por WhatsApp, SMS, correo o como prefieras:",
            "",
            enlace,
            "",
            f"Si el enlace no se abre, que busque <b>@{esc(self.bot_usuario)}</b> en Telegram, "
            f"toque <b>Iniciar</b> y escriba este código:",
            f"<code>{inv.codigo}</code>",
            "",
            f"🔐 Sirve una sola vez · ⏳ vence en {duracion(inv.expira - self.reloj() + MINUTO)}",
        ]
        if pareja:
            lineas.append("💞 Al entrar, su personaje aparecerá en tu sala.")
        return Pantalla(
            "\n".join(lineas),
            [[("📤 Compartir por Telegram", compartir)], [("📋 Mis invitaciones", "invs"), SALA]],
        )

    def _b_ver_invitacion(self, j: Jugador, codigo: str, res: Resultado) -> None:
        inv = self.db.invitacion(codigo)
        if inv is None or inv.creador != j.id or not inv.vigente(self.reloj()):
            res.alerta = "Esa invitación ya no está disponible."
            self._b_mis_invitaciones(j, "", res)
            return
        res.pantalla = self._pantalla_invitacion(inv)

    def _b_mis_invitaciones(self, j: Jugador, arg: str, res: Resultado) -> None:
        ahora = self.reloj()
        invs = self.db.invitaciones_de(j.id, 10)
        lineas = ["📋 <b>Mis invitaciones</b>", ""]
        botones: Botones = []
        if not invs:
            lineas.append("Todavía no has creado invitaciones.")
        for i in invs:
            tipo = "💞 pareja" if i.tipo == "pareja" else "👋 otra persona"
            if i.usada_por:
                quien = self.db.jugador(i.usada_por)
                nombre = (quien.personaje or quien.nombre_tg) if quien else ""
                lineas.append(f"✅ <code>{i.codigo}</code> · {tipo} · usada por {esc(nombre or 'alguien')}")
            elif i.anulada:
                lineas.append(f"🚫 <code>{i.codigo}</code> · {tipo} · anulada")
            elif i.expira <= ahora:
                lineas.append(f"⌛ <code>{i.codigo}</code> · {tipo} · vencida")
            else:
                lineas.append(f"🟢 <code>{i.codigo}</code> · {tipo} · vence en {duracion(i.expira - ahora + MINUTO)}")
                botones.append([(f"👁️ Ver {i.codigo}", f"ver:{i.codigo}"), (f"❌ Anular {i.codigo}", f"anular:{i.codigo}")])
        botones.append([("💌 Nueva invitación", "invitar"), SALA])
        res.pantalla = Pantalla("\n".join(lineas), botones)

    def _b_anular(self, j: Jugador, codigo: str, res: Resultado) -> None:
        inv = self.db.invitacion(codigo)
        if inv is not None and inv.creador == j.id and inv.vigente(self.reloj()):
            inv.anulada = 1
            self.db.guardar_invitacion(inv)
            res.alerta = "🚫 Invitación anulada"
        self._b_mis_invitaciones(j, "", res)
