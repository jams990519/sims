"""Plano de la casa en texto (actualización 2, parte 4). Lógica pura, sin Telegram ni base de datos.

Se dibuja con rayitas y letras en texto monoespaciado (<pre> en Telegram) y cabe en la pantalla de un
teléfono pequeño (ANCHO columnas). Solo marca dónde está cada jugador: su inicial entre corchetes y, al
lado, el ícono de lo que hace. En la sala-cocina-comedor se pone debajo de la parte donde hace la acción
(📺 en la sala, 🍳 en la cocina, 🍴 en el comedor). Telegram dibuja cada ícono con el ancho de dos letras, así que se cuenta
así y solo se usan íconos de un solo carácter (los que llevan un selector de variación tienen reemplazo).
El cuarto va arriba a la izquierda; el clóset y el baño, a la derecha; la sala-cocina-comedor, abajo.
"""

from __future__ import annotations

import unicodedata

IZQUIERDA = 11  # el cuarto (y el cuarto 2): caben "[L]😴 [A]😴"
DERECHA = 8  # el clóset y el baño: caben "[Lu][Lu]"
ANCHO = 1 + IZQUIERDA + 1 + DERECHA + 1  # 22 columnas: cabe en un teléfono pequeño

SALON = " SALA·COCINA·COMEDOR"
RINCONES = ("sala", "cocina", "comedor")  # las partes de la sala-cocina-comedor, de izquierda a derecha

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


def _opciones(quienes: list[tuple[str, str]]) -> list[str]:
    """'[L]😴 [A]🚿' (inicial e ícono) y, para cuando no cabe, cada vez más junto y al final sin íconos."""
    return [
        " ".join(f"[{letra}]{ico}" for letra, ico in quienes),
        "".join(f"[{letra}]{ico}" for letra, ico in quienes),
        "".join(f"[{letra}]" for letra, _ in quienes),
        "".join(letra for letra, _ in quienes),
    ]


def marcas(quienes: list[tuple[str, str]], columnas: int = ANCHO) -> str:
    opciones = _opciones(quienes)
    return next((o for o in opciones if ancho(o) <= columnas), _c(opciones[-1], columnas))


def _fila_salon(dentro: dict[str, list[tuple[str, str]]]) -> str:
    """Las marcas de la sala-cocina-comedor, cada una debajo de su parte ('salon' cuenta como la sala)."""
    columnas = ANCHO - 2
    fila = ""
    for rincon in RINCONES:
        quienes = dentro.get(rincon, []) + (dentro.get("salon", []) if rincon == "sala" else [])
        if not quienes:
            continue
        minimo = ancho(fila) + 1 if fila else 0
        for texto in _opciones(quienes):
            inicio = max(min(SALON.index(rincon.upper()), columnas - ancho(texto)), minimo)
            if inicio + ancho(texto) <= columnas:
                fila += " " * (inicio - ancho(fila)) + texto
                break
    return fila


def _sangria(texto: str, columnas: int) -> str:
    """Un espacio delante si cabe."""
    return " " + texto if texto and ancho(texto) < columnas else texto


def dibujar(zonas: tuple[str, ...], dentro: dict[str, list[tuple[str, str]]]) -> list[str]:
    """Las líneas del plano. `dentro`: habitación → (inicial, ícono) de quienes están ahí; en la
    sala-cocina-comedor, la parte ('sala', 'cocina' o 'comedor') en vez de 'salon'."""
    m = {}
    for zona in zonas:
        if zona != "salon":
            columnas = DERECHA if zona in ("closet", "bano") else IZQUIERDA
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
            (m["cuarto"], "|", m["closet"]),
            ("", "+", raya_der),
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
    for texto in (SALON, _fila_salon(dentro), ""):  # cada uno justo debajo de su parte
        lineas.append(f"|{_c(texto, ANCHO - 2)}|")
    lineas.append("+" + "-" * (ANCHO - 2) + "+")
    return lineas
