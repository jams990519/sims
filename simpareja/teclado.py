"""Botones abajo, en el teclado de Telegram (versión 0.37). Lógica pura, sin Telegram.

Los botones de cada pantalla se muestran debajo de la barra de escribir y quedan siempre visibles.
Al tocar uno, Telegram manda su texto como un mensaje: se busca qué botón era y se hace lo mismo que
con los botones dentro del mensaje. Lo que no es un botón sigue siendo chat con la pareja.

Estado de cada jugador (en `meta`, clave "teclado:<id>"): "filas" (los botones de la última pantalla),
"extra" (los de un aviso que pregunta algo, que van arriba hasta la próxima pantalla) y "msg" (el
mensaje de esa pantalla, que se borra al mostrar la siguiente para que el chat quede limpio).
"""

from __future__ import annotations

import html

Fila = list[list[str]]  # [[texto, dato], …]
MENU = ["🎮 Menú", "menu"]


def es_enlace(dato: str) -> bool:
    return dato.startswith(("https://", "http://"))


def separar(botones) -> tuple[list[Fila], list[tuple[str, str]]]:
    """Las filas de botones normales y, aparte, los botones con enlace (abajo no puede haber enlaces)."""
    filas, enlaces = [], []
    for fila in botones:
        normales = [[texto, dato] for texto, dato in fila if not es_enlace(dato)]
        enlaces += [(texto, dato) for texto, dato in fila if es_enlace(dato)]
        if normales:
            filas.append(normales)
    return filas, enlaces


def texto_con_enlaces(texto: str, enlaces: list[tuple[str, str]]) -> str:
    """Los botones con enlace pasan al texto como enlaces que se tocan."""
    if not enlaces:
        return texto
    return texto + "\n\n" + "\n".join(
        f'👉 <a href="{html.escape(dato)}">{html.escape(boton)}</a>' for boton, dato in enlaces
    )


def mostrar(extra: list[Fila], filas: list[Fila]) -> list[Fila]:
    """Lo que se ve abajo: primero lo del aviso (si hay) y después la pantalla, sin textos repetidos."""
    vistos, salida = set(), []
    for fila in list(extra) + list(filas):
        nueva = [b for b in fila if b[0] not in vistos]
        vistos.update(b[0] for b in nueva)
        if nueva:
            salida.append(nueva)
    if extra and not any(b[1] == MENU[1] for fila in salida for b in fila):
        salida.append([MENU])  # con un aviso arriba, siempre se puede volver al menú
    return salida


def buscar(estado: dict, texto: str) -> str | None:
    """El dato del botón que tiene ese texto (entre los que se ven abajo), o None si es chat."""
    for fila in mostrar(estado.get("extra", []), estado.get("filas", [])):
        for boton, dato in fila:
            if boton == texto:
                return dato
    return None
