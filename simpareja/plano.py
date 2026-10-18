"""Plano de la casa en texto (actualización 2, parte 4). Lógica pura, sin Telegram ni base de datos.

Se dibuja con rayitas y letras en texto monoespaciado (<pre> en Telegram) y cabe en la pantalla de un
teléfono pequeño (ANCHO columnas). Solo marca dónde está cada jugador: su inicial entre corchetes y, al
lado, el ícono de lo que hace. Telegram dibuja cada ícono con el ancho de dos letras, así que se cuenta
así y solo se usan íconos de un solo carácter (los que llevan un selector de variación tienen reemplazo).
El cuarto va arriba a la izquierda; el clóset y el baño, a la derecha; la sala-cocina-comedor, abajo.
"""

from __future__ import annotations

import unicodedata

IZQUIERDA = 11  # el cuarto (y el cuarto 2): caben "[L]😴 [A]😴"
DERECHA = 8  # el clóset y el baño: caben "[Lu][Lu]"
ANCHO = 1 + IZQUIERDA + 1 + DERECHA + 1  # 22 columnas: cabe en un teléfono pequeño

# Íconos que no son de un solo carácter: su reemplazo en el plano.
REEMPLAZOS = {"🍽️": "🍴", "✂️": "💻", "✍️": "📝", "🏋️": "💪"}


def ancho(texto: str) -> int:
    """Las columnas que ocupa en Telegram: cada ícono, dos (también los que llevan selector de variación)."""
    total = 0
    for i, c in enumerate(texto):
        if c != "️":
            icono_ = unicodedata.east_asian_width(c) == "W" or texto[i + 1:i + 2] == "️"
            total += 2 if icono_ else 1
    return total


def icono(emoji: str) -> str:
    """El ícono tal como va en el plano, o '' si no hay uno que se vea igual en todos los teléfonos."""
    emoji = REEMPLAZOS.get(emoji, emoji)
    return emoji if len(emoji) == 1 and ancho(emoji) == 2 else ""


def _c(texto: str, columnas: int) -> str:
    while ancho(texto) > columnas:
        texto = texto[:-1]
    return texto + " " * (columnas - ancho(texto))


def iniciales(nombres: list[str]) -> list[str]:
    """La inicial de cada nombre; si dos empiezan igual, las dos primeras letras."""
    primeras = [(n.strip()[:1] or "?").upper() for n in nombres]
    return [
        (n.strip()[:2].title() or "?") if primeras.count(p) > 1 else p
        for n, p in zip(nombres, primeras)
    ]


def marcas(quienes: list[tuple[str, str]], columnas: int = ANCHO) -> str:
    """'[L]😴 [A]🚿' (inicial e ícono); si no cabe, más junto y, si hace falta, sin íconos."""
    opciones = [
        " ".join(f"[{letra}]{ico}" for letra, ico in quienes),
        "".join(f"[{letra}]{ico}" for letra, ico in quienes),
        "".join(f"[{letra}]" for letra, _ in quienes),
        "".join(letra for letra, _ in quienes),
    ]
    return next((o for o in opciones if ancho(o) <= columnas), _c(opciones[-1], columnas))


def _sangria(texto: str, columnas: int) -> str:
    """Un espacio delante si cabe."""
    return " " + texto if texto and ancho(texto) < columnas else texto


def dibujar(zonas: tuple[str, ...], dentro: dict[str, list[tuple[str, str]]]) -> list[str]:
    """Las líneas del plano. `dentro`: habitación → (inicial, ícono) de quienes están ahí."""
    m = {}
    for zona in zonas:
        columnas = DERECHA if zona in ("closet", "bano") else IZQUIERDA if zona != "salon" else ANCHO - 2
        m[zona] = _sangria(marcas(dentro.get(zona, []), columnas), columnas)
    raya_izq, raya_der = "-" * IZQUIERDA, "-" * DERECHA
    if "extra" in zonas:
        arriba = [
            (" CUARTO", "|", " CLÓSET"),
            (m["cuarto"], "|", m["closet"]),
            (raya_izq, "+", raya_der),
            (" CUARTO 2", "|", " BAÑO"),
            (m["extra"], "|", m["bano"]),
        ]
    else:
        arriba = [
            (" CUARTO", "|", " CLÓSET"),
            ("", "|", m["closet"]),
            (m["cuarto"], "+", raya_der),
            ("", "|", " BAÑO"),
            ("", "|", m["bano"]),
        ]
    division = f"+{raya_izq}+{raya_der}+"
    lineas = [division]
    for izq, union, der in arriba:
        borde = "+" if izq.startswith("-") else "|"
        fin = "+" if der.startswith("-") else "|"
        lineas.append(f"{borde}{_c(izq, IZQUIERDA)}{union}{_c(der, DERECHA)}{fin}")
    lineas.append(division)
    for texto in (" SALA·COCINA·COMEDOR", "", m["salon"]):
        lineas.append(f"|{_c(texto, ANCHO - 2)}|")
    lineas.append("+" + "-" * (ANCHO - 2) + "+")
    return lineas
