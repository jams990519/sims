"""Eventos sorpresa (actualización 2, parte 9). Lógica pura, sin Telegram ni base de datos.

Uno o dos por semana, al azar: buenos, malos y de pareja. Reemplazan a los imprevistos diarios
de antes (averías y multas).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

DIA = 24 * 60 * 60
DIAS_ENTRE = (3.0, 5.0)  # entre un evento y el siguiente: uno o dos por semana
SIN_JUGAR = 3 * DIA  # si nadie juega hace más de esto, no se acumulan eventos

BONO = (100, 200)
VIRAL = (500, 2000)  # seguidores de golpe
AVERIA = (150, 300)
MULTA = (50, 100)
APAGON_HORAS = (2, 4)
RESFRIADO_DIAS = (1, 2)
RESFRIADO_ENERGIA = 30
REGALO = {"diversion": 20, "social": 10}
VISITA_HORAS = 24
ANTOJO_HORAS = 24
ANTOJO_RELACION = 5
VISITA_BIEN = {"social": 10, "diversion": 5}
VISITA_MAL = {"diversion": -10}

AVERIAS = {
    "nevera": ("🧊", "la nevera", ("comer", "cocinar"), "no se puede comer de la nevera ni cocinar"),
    "ducha": ("🚿", "la ducha", ("ducha", "banarse"), "no se pueden duchar ni bañar"),
}
MULTAS = (
    "🚓 Una multa de tránsito",
    "📢 Una multa por ruido",
    "🦷 Una visita al dentista",
    "📱 Se rompió la pantalla del móvil",
    "🧾 Un cobro inesperado del banco",
)
SALIDAS = ("parque", "cine", "restaurante", "gimnasio")  # lo que cancela la lluvia
APAGON = ("tele", "redes", "lavar", "consola")  # sin luz ni internet


@dataclass(frozen=True)
class Evento:
    clave: str
    tipo: str  # "bueno" | "malo" | "pareja"
    peso: int
    pareja: bool = False  # solo si juegan en pareja
    trabajo: bool = False  # solo si alguien tiene trabajo
    influencer: bool = False  # solo si alguien publica videos


EVENTOS = (
    Evento("bono", "bueno", 2, trabajo=True),
    Evento("oferta", "bueno", 2),
    Evento("regalo", "bueno", 2),
    Evento("viral", "bueno", 2, influencer=True),
    Evento("averia", "malo", 2),
    Evento("resfriado", "malo", 1),
    Evento("apagon", "malo", 2),
    Evento("multa", "malo", 2),
    Evento("lluvia", "pareja", 1, pareja=True),
    Evento("visita", "pareja", 1, pareja=True),
    Evento("antojo", "pareja", 2, pareja=True),
    Evento("pregunta", "pareja", 2, pareja=True),
)
POR_CLAVE = {e.clave: e for e in EVENTOS}


def siguiente(ahora: float, rng: random.Random) -> float:
    return ahora + rng.uniform(*DIAS_ENTRE) * DIA


def elegir(rng: random.Random, en_pareja: bool, con_trabajo: bool, con_videos: bool = False) -> Evento:
    posibles = [e for e in EVENTOS if (en_pareja or not e.pareja) and (con_trabajo or not e.trabajo)
                and (con_videos or not e.influencer)]
    return rng.choices(posibles, weights=[e.peso for e in posibles])[0]
