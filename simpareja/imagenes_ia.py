"""Fotos estilo serie de anime hechas por una IA de imágenes (OpenAI), con caché y un tope diario (versión 0.43).

La primera vez que hace falta una foto (una escena, a una hora del día, con unos personajes) se le pide a la
IA, se deja pequeña (ilustraciones.procesar) y se guarda en disco; después se reusa gratis. Se pueden pedir
por adelantado (`pedir`) para que estén listas cuando llegue el mensajito. Sin OPENAI_API_KEY no hace nada:
los mensajitos llegan solo con texto.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from . import ilustraciones as IL
from .db import DB

log = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/images/generations"
REINTENTAR = 6 * 3600  # una foto que falló no se vuelve a pedir hasta dentro de 6 horas
A_LA_VEZ = 2  # fotos haciéndose a la vez

Generador = Callable[[str], Awaitable[bytes]]  # descripción → imagen (PNG o JPEG)


def generador_openai(clave_api: str, modelo: str, calidad: str) -> Generador:
    """Pide la imagen a la API de OpenAI (gpt-image-2 o el modelo que diga IMAGEN_MODELO)."""
    import httpx  # viene con python-telegram-bot

    async def generar(descripcion: str) -> bytes:
        cuerpo = {"model": modelo, "prompt": descripcion, "n": 1}
        if modelo.startswith("dall-e"):
            cuerpo.update(size="1792x1024", quality="hd" if calidad == "high" else "standard",
                          response_format="b64_json")
        else:
            cuerpo.update(size="1536x1024", quality=calidad, output_format="jpeg")
        async with httpx.AsyncClient(timeout=240) as cliente:
            r = await cliente.post(URL, headers={"Authorization": f"Bearer {clave_api}"}, json=cuerpo)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI respondió {r.status_code}: {r.text[:300]}")
        return base64.b64decode(r.json()["data"][0]["b64_json"])

    return generar


class ImagenesIA:
    def __init__(self, db: DB, carpeta: str | Path, por_dia: int = 20, generar: Generador | None = None,
                 reloj=time.time):
        self.db = db
        self.carpeta = Path(carpeta)
        self.por_dia = por_dia
        self._generar = generar
        self.reloj = reloj
        self.tareas: dict[str, asyncio.Task] = {}
        self.fallos: dict[str, float] = {}
        self._turno: asyncio.Semaphore | None = None

    @property
    def activa(self) -> bool:
        return self._generar is not None

    def ruta(self, clave: str) -> Path:
        return self.carpeta / f"{hashlib.sha1(clave.encode()).hexdigest()}.jpg"

    def lista(self, clave: str) -> bytes | None:
        """La foto ya hecha (o None)."""
        ruta = self.ruta(clave)
        return ruta.read_bytes() if ruta.is_file() else None

    def pedir(self, clave: str) -> asyncio.Task | None:
        """Empieza a hacerla en segundo plano y devuelve la tarea (o None si ya está, falló hace poco o se
        acabó el tope del día)."""
        if clave in self.tareas:
            return self.tareas[clave]
        if not self.activa or self.ruta(clave).is_file():
            return None
        if self.reloj() - self.fallos.get(clave, -REINTENTAR) < REINTENTAR:
            return None
        if not self._gastar():
            log.info("Se acabaron las %d fotos nuevas de hoy: %s irá sin foto", self.por_dia, clave)
            return None
        tarea = asyncio.get_running_loop().create_task(self._hacer(clave))
        self.tareas[clave] = tarea
        tarea.add_done_callback(lambda _: self.tareas.pop(clave, None))
        return tarea

    async def _hacer(self, clave: str) -> bytes | None:
        if self._turno is None:
            self._turno = asyncio.Semaphore(A_LA_VEZ)
        try:
            async with self._turno:
                datos = await self._generar(IL.prompt(clave))
            jpeg = IL.procesar(datos, clave)
            ruta = self.ruta(clave)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = ruta.with_suffix(".tmp")
            temporal.write_bytes(jpeg)
            temporal.replace(ruta)
            log.info("Foto nueva lista: %s (%d KB)", clave.split(":")[0], len(jpeg) // 1024)
            return jpeg
        except Exception as e:  # la IA rechazó la escena, no hubo red, la imagen vino rota…
            self.fallos[clave] = self.reloj()
            log.warning("No se pudo hacer la foto %s: %s", clave.split(":")[0], e)
            return None

    def _gastar(self) -> bool:
        """Cuenta una foto nueva del día (UTC); False si ya se llegó al tope."""
        hoy = datetime.fromtimestamp(self.reloj(), timezone.utc).strftime("%Y-%m-%d")
        cuenta = json.loads(self.db.meta("imagenes_dia") or "{}")
        hechas = cuenta.get("n", 0) if cuenta.get("dia") == hoy else 0
        if hechas >= self.por_dia:
            return False
        self.db.guardar_meta("imagenes_dia", json.dumps({"dia": hoy, "n": hechas + 1}))
        return True
