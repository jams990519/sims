"""Configuración leída de variables de entorno (o de un archivo .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _cargar_env(ruta: str = ".env") -> None:
    """Carga un .env sencillo (CLAVE=valor) sin pisar variables ya definidas."""
    p = Path(ruta)
    if not p.is_file():
        return
    for linea in p.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _ids(texto: str) -> frozenset[int]:
    return frozenset(int(x) for x in texto.replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    token: str = ""
    nombre_juego: str = "SimPareja"
    admins: frozenset[int] = field(default_factory=frozenset)
    db_ruta: str = "datos/simpareja.db"
    # Minutos sin jugar hasta que el Sim se congela (y deja de gastar necesidades).
    pausa_min: int = 5
    # Minutos sin actividad hasta pasar de "en línea" a "en pausa" y luego a "fuera de línea".
    en_linea_min: int = 5
    ausente_min: int = 60
    # Personas por sala (2 = una pareja).
    max_sala: int = 2
    invitacion_dias: int = 7
    max_invitaciones_activas: int = 5
    # Eventos sorpresa (uno o dos por semana); EVENTOS=0 los apaga.
    eventos: bool = True
    # ¿Se pueden crear personajes nuevos? En el servidor, cerrado (REGISTRO_ABIERTO=1 lo abre); un admin lo
    # cambia en ⚙️ Ajustes.
    registro_abierto: bool = True
    # Lugar cuya hora real (con horario de verano) sigue quien no eligió otro: "cuba", "miami"…
    zona_por_defecto: str = ""
    # Botones abajo, en el teclado de Telegram (siempre visibles); BOTONES_ABAJO=0 los deja en los mensajes.
    botones_abajo: bool = True
    # Fotos estilo anime de las acciones, hechas por una IA de imágenes (OpenAI). Sin clave, solo texto.
    openai_key: str = field(default="", repr=False)
    imagen_modelo: str = "gpt-image-2"
    imagen_calidad: str = "medium"  # low, medium o high
    imagenes_por_dia: int = 20  # fotos nuevas por día como máximo (las ya hechas se reusan gratis)
    # Opcionales, para servidores en países donde Telegram está bloqueado.
    proxy: str = ""
    api_url: str = ""

    @classmethod
    def desde_entorno(cls) -> "Config":
        _cargar_env()
        e = os.environ.get
        return cls(
            token=e("BOT_TOKEN", ""),
            nombre_juego=e("NOMBRE_JUEGO", cls.nombre_juego),
            admins=_ids(e("ADMIN_IDS", "")),
            db_ruta=e("DB_RUTA", cls.db_ruta),
            pausa_min=int(e("PAUSA_MIN", cls.pausa_min)),
            en_linea_min=int(e("EN_LINEA_MIN", cls.en_linea_min)),
            ausente_min=int(e("AUSENTE_MIN", cls.ausente_min)),
            max_sala=int(e("MAX_SALA", cls.max_sala)),
            invitacion_dias=int(e("INVITACION_DIAS", cls.invitacion_dias)),
            max_invitaciones_activas=int(e("MAX_INVITACIONES", cls.max_invitaciones_activas)),
            eventos=e("EVENTOS", "1") not in ("0", "no", "false"),
            botones_abajo=e("BOTONES_ABAJO", "1") not in ("0", "no", "false"),
            zona_por_defecto=e("ZONA_POR_DEFECTO", "cuba"),
            registro_abierto=e("REGISTRO_ABIERTO", "0") in ("1", "si", "sí", "true"),
            openai_key=e("OPENAI_API_KEY", "").strip(),
            imagen_modelo=e("IMAGEN_MODELO", cls.imagen_modelo),
            imagen_calidad=e("IMAGEN_CALIDAD", cls.imagen_calidad),
            imagenes_por_dia=int(e("IMAGENES_POR_DIA", cls.imagenes_por_dia)),
            proxy=e("TELEGRAM_PROXY", ""),
            api_url=e("TELEGRAM_API_URL", ""),
        )
