"""Almacenamiento en SQLite: un solo archivo, fácil de respaldar y de mover de servidor."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import astuple, dataclass, fields
from pathlib import Path

# Estados de quien ya terminó de crear su personaje y está en una sala.
EN_JUEGO = ("activo", "renombrando")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS salas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    creador INTEGER NOT NULL,
    creada  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jugadores (
    id                INTEGER PRIMARY KEY,      -- id de usuario de Telegram
    estado            TEXT NOT NULL,            -- 'nombrando' | 'creando' | 'renombrando' | 'activo'
    nombre_tg         TEXT NOT NULL DEFAULT '',
    personaje         TEXT NOT NULL DEFAULT '',
    apariencia        TEXT NOT NULL DEFAULT '{}',   -- JSON con lo elegido en el creador
    borrador          TEXT,                         -- JSON mientras se crea o edita la apariencia
    sala_id           INTEGER REFERENCES salas(id),
    invitado_por      INTEGER,
    inv_codigo        TEXT,
    ultima_actividad  REAL NOT NULL DEFAULT 0,
    salio             INTEGER NOT NULL DEFAULT 0,
    presencia         TEXT NOT NULL DEFAULT 'fuera',
    msg_sala          INTEGER,                  -- mensaje con la sala abierta (se actualiza en vivo)
    aviso_conexion_ts REAL NOT NULL DEFAULT 0,
    avisos_conexion   INTEGER NOT NULL DEFAULT 1,
    creado            REAL NOT NULL,
    -- Reloj propio del Sim: corre como un día real y se congela tras unos minutos sin jugar.
    reloj_juego       REAL NOT NULL DEFAULT 0,  -- segundos de juego acumulados
    reloj_desde       REAL,                     -- desde cuándo corre (NULL = congelado)
    ultima_jugada     REAL NOT NULL DEFAULT 0   -- última acción de juego (el chat no cuenta)
);
CREATE INDEX IF NOT EXISTS jugadores_sala ON jugadores(sala_id);

-- Personas que abrieron el bot pero todavía no juegan: cada una tiene su código personal.
CREATE TABLE IF NOT EXISTS visitantes (
    id        INTEGER PRIMARY KEY,              -- id de usuario de Telegram
    codigo    TEXT NOT NULL UNIQUE,
    nombre_tg TEXT NOT NULL DEFAULT '',
    creado    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS invitaciones (
    codigo    TEXT PRIMARY KEY,
    creador   INTEGER NOT NULL,
    tipo      TEXT NOT NULL,                    -- 'pareja' (entra a tu sala) | 'amigo' (sala propia)
    sala_id   INTEGER,
    creada    REAL NOT NULL,
    expira    REAL NOT NULL,
    usada_por INTEGER,
    usada_ts  REAL,
    anulada   INTEGER NOT NULL DEFAULT 0,
    para_id   INTEGER                           -- la única persona que puede usarla
);
CREATE INDEX IF NOT EXISTS invitaciones_creador ON invitaciones(creador);

-- Solo la ÚLTIMA conexión de cada jugador (se sobrescribe): dónde estaba y qué hacía,
-- para devolverle al mismo sitio cuando vuelva.
CREATE TABLE IF NOT EXISTS ultima_conexion (
    jugador_id       INTEGER PRIMARY KEY,
    pantalla         TEXT NOT NULL DEFAULT 'sala',  -- clave para reconstruir la pantalla
    lugar            TEXT NOT NULL DEFAULT '',
    actividad        TEXT NOT NULL DEFAULT '',
    estado           TEXT NOT NULL DEFAULT '',
    sala_id          INTEGER,
    conectado_desde  REAL NOT NULL DEFAULT 0,
    ultima_actividad REAL NOT NULL DEFAULT 0,
    desconectado     REAL
);

CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

# Columnas añadidas después de la primera versión: se agregan a bases de datos ya existentes.
COLUMNAS_NUEVAS = [
    ("invitaciones", "para_id", "INTEGER"),
    ("jugadores", "reloj_juego", "REAL NOT NULL DEFAULT 0"),
    ("jugadores", "reloj_desde", "REAL"),
    ("jugadores", "ultima_jugada", "REAL NOT NULL DEFAULT 0"),
]


@dataclass
class Jugador:
    id: int
    estado: str
    nombre_tg: str = ""
    personaje: str = ""
    apariencia: str = "{}"
    borrador: str | None = None
    sala_id: int | None = None
    invitado_por: int | None = None
    inv_codigo: str | None = None
    ultima_actividad: float = 0.0
    salio: int = 0
    presencia: str = "fuera"
    msg_sala: int | None = None
    aviso_conexion_ts: float = 0.0
    avisos_conexion: int = 1
    creado: float = 0.0
    reloj_juego: float = 0.0
    reloj_desde: float | None = None
    ultima_jugada: float = 0.0

    @property
    def activo(self) -> bool:
        return self.estado in EN_JUEGO

    @property
    def ap(self) -> dict:
        return json.loads(self.apariencia or "{}")


@dataclass
class Visitante:
    id: int
    codigo: str
    nombre_tg: str = ""
    creado: float = 0.0


@dataclass
class Invitacion:
    codigo: str
    creador: int
    tipo: str
    sala_id: int | None
    creada: float
    expira: float
    usada_por: int | None = None
    usada_ts: float | None = None
    anulada: int = 0
    para_id: int | None = None

    def vigente(self, ahora: float) -> bool:
        return not self.anulada and self.usada_por is None and self.expira > ahora


@dataclass
class UltimaConexion:
    jugador_id: int
    pantalla: str = "sala"
    lugar: str = ""
    actividad: str = ""
    estado: str = ""
    sala_id: int | None = None
    conectado_desde: float = 0.0
    ultima_actividad: float = 0.0
    desconectado: float | None = None


def _sql_upsert(tabla: str, cls: type) -> str:
    cols = [f.name for f in fields(cls)]
    return (
        f"INSERT OR REPLACE INTO {tabla} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )


class DB:
    def __init__(self, ruta: str = ":memory:"):
        if ruta != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        with self.con:
            self.con.executescript(ESQUEMA)
            self._migrar()

    def _migrar(self) -> None:
        for tabla, columna, tipo in COLUMNAS_NUEVAS:
            existentes = {f["name"] for f in self.con.execute(f"PRAGMA table_info({tabla})")}
            if columna not in existentes:
                self.con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        self.con.execute("CREATE INDEX IF NOT EXISTS invitaciones_para ON invitaciones(para_id)")

    # --- jugadores -------------------------------------------------------

    def jugador(self, uid: int) -> Jugador | None:
        fila = self.con.execute("SELECT * FROM jugadores WHERE id = ?", (uid,)).fetchone()
        return Jugador(**fila) if fila else None

    def guardar_jugador(self, j: Jugador) -> None:
        with self.con:
            self.con.execute(_sql_upsert("jugadores", Jugador), astuple(j))

    def contar_jugadores(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM jugadores").fetchone()[0]

    def todos_los_jugadores(self) -> list[Jugador]:
        return [Jugador(**f) for f in self.con.execute("SELECT * FROM jugadores").fetchall()]

    def miembros_sala(self, sala_id: int | None) -> list[Jugador]:
        if sala_id is None:
            return []
        filas = self.con.execute(
            "SELECT * FROM jugadores WHERE sala_id = ? AND estado IN (?, ?) ORDER BY creado",
            (sala_id, *EN_JUEGO),
        ).fetchall()
        return [Jugador(**f) for f in filas]

    def jugadores_en_sala(self) -> list[Jugador]:
        filas = self.con.execute(
            "SELECT * FROM jugadores WHERE sala_id IS NOT NULL AND estado IN (?, ?)", EN_JUEGO
        ).fetchall()
        return [Jugador(**f) for f in filas]

    # --- visitantes ------------------------------------------------------

    def visitante(self, uid: int) -> Visitante | None:
        fila = self.con.execute("SELECT * FROM visitantes WHERE id = ?", (uid,)).fetchone()
        return Visitante(**fila) if fila else None

    def visitante_por_codigo(self, codigo: str) -> Visitante | None:
        fila = self.con.execute("SELECT * FROM visitantes WHERE codigo = ?", (codigo,)).fetchone()
        return Visitante(**fila) if fila else None

    def guardar_visitante(self, v: Visitante) -> None:
        with self.con:
            self.con.execute(_sql_upsert("visitantes", Visitante), astuple(v))

    # --- salas -----------------------------------------------------------

    def crear_sala(self, creador: int, ahora: float) -> int:
        with self.con:
            cur = self.con.execute(
                "INSERT INTO salas (creador, creada) VALUES (?, ?)", (creador, ahora)
            )
        return int(cur.lastrowid)

    # --- invitaciones ----------------------------------------------------

    def invitacion(self, codigo: str) -> Invitacion | None:
        fila = self.con.execute(
            "SELECT * FROM invitaciones WHERE codigo = ?", (codigo,)
        ).fetchone()
        return Invitacion(**fila) if fila else None

    def guardar_invitacion(self, inv: Invitacion) -> None:
        with self.con:
            self.con.execute(_sql_upsert("invitaciones", Invitacion), astuple(inv))

    def invitaciones_de(self, creador: int, limite: int = 15) -> list[Invitacion]:
        filas = self.con.execute(
            "SELECT * FROM invitaciones WHERE creador = ? ORDER BY creada DESC LIMIT ?",
            (creador, limite),
        ).fetchall()
        return [Invitacion(**f) for f in filas]

    def invitaciones_para(self, uid: int, ahora: float) -> list[Invitacion]:
        """Invitaciones vigentes dirigidas a esta persona, la más reciente primero."""
        filas = self.con.execute(
            "SELECT * FROM invitaciones WHERE para_id = ? AND anulada = 0 "
            "AND usada_por IS NULL AND expira > ? ORDER BY creada DESC",
            (uid, ahora),
        ).fetchall()
        return [Invitacion(**f) for f in filas]

    # --- última conexión -------------------------------------------------

    def ultima_conexion(self, uid: int) -> UltimaConexion | None:
        fila = self.con.execute(
            "SELECT * FROM ultima_conexion WHERE jugador_id = ?", (uid,)
        ).fetchone()
        return UltimaConexion(**fila) if fila else None

    def guardar_ultima_conexion(self, uc: UltimaConexion) -> None:
        with self.con:
            self.con.execute(_sql_upsert("ultima_conexion", UltimaConexion), astuple(uc))

    # --- meta ------------------------------------------------------------

    def meta(self, clave: str) -> str | None:
        fila = self.con.execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
        return fila[0] if fila else None

    def guardar_meta(self, clave: str, valor: str) -> None:
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)", (clave, valor))
