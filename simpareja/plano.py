"""Plano de la casa en texto (actualización 2, parte 4). Lógica pura, sin Telegram ni base de datos.

Se dibuja con rayitas y letras en texto monoespaciado (<pre> en Telegram) para que no se deforme:
dentro del plano no hay emojis, porque cada teléfono los dibuja con un ancho distinto.
El cuarto va arriba a la izquierda; el clóset y el baño, a la derecha; la sala-cocina-comedor,
amplia, abajo. Cada Sim aparece con su inicial entre corchetes en la habitación donde está.
"""

from __future__ import annotations


def _c(texto: str, ancho: int) -> str:
    return texto[:ancho].ljust(ancho)


def iniciales(nombres: list[str]) -> list[str]:
    """La inicial de cada nombre; si dos empiezan igual, las dos primeras letras."""
    primeras = [(n.strip()[:1] or "?").upper() for n in nombres]
    return [
        (n.strip()[:2].title() or "?") if primeras.count(p) > 1 else p
        for n, p in zip(nombres, primeras)
    ]


def marcas(quienes: list[str]) -> str:
    """'[L][A]'; la mascota ya viene entre paréntesis: '(K)'."""
    return "".join(q if q.startswith("(") else f"[{q}]" for q in quienes)


def _sangria(texto: str, ancho: int) -> str:
    """Un espacio delante si cabe."""
    return " " + texto if texto and len(texto) < ancho else texto


def dibujar(zonas: tuple[str, ...], dentro: dict[str, list[str]], objetos: list[str] | tuple = ()) -> list[str]:
    """Las líneas del plano. `dentro`: habitación → marcas de quienes están ahí; `objetos`: lo comprado."""
    derecha = 8  # cabe "[Lu][Lu]": los dos en el baño
    m = {z: marcas(dentro.get(z, [])) for z in zonas}
    m["closet"], m["bano"] = _sangria(m.get("closet", ""), derecha), _sangria(m.get("bano", ""), derecha)
    if "extra" in zonas:
        cuarto, extra = 10, 10
        ancho = cuarto + 1 + extra + 1 + derecha
        arriba = [
            ("-" * cuarto, "-" * extra, "+", "-" * derecha),
            (" CUARTO", " CUARTO 2", "|", " CLÓSET"),
            ("", "", "|", m["closet"]),
            ("  cama", "", "+", "-" * derecha),
            ("", "", "|", " BAÑO"),
            (" " + m["cuarto"], " " + m["extra"], "|", " ducha"),
            ("", "", "|", m["bano"]),
        ]
        lineas = []
        for i, (a, b, union, c) in enumerate(arriba):
            borde, sep = ("+", "+") if i == 0 else ("|", "|")
            fin = "+" if c.startswith("-") else borde
            lineas.append(f"{borde}{_c(a, cuarto)}{sep}{_c(b, extra)}{union}{_c(c, derecha)}{fin}")
    else:
        cuarto = 17
        ancho = cuarto + 1 + derecha
        arriba = [
            ("-" * cuarto, "+", "-" * derecha),
            (" CUARTO", "|", " CLÓSET"),
            ("", "|", m["closet"]),
            ("  cama", "+", "-" * derecha),
            ("", "|", " BAÑO"),
            ("  " + m["cuarto"], "|", " ducha"),
            ("", "|", m["bano"]),
        ]
        lineas = []
        for i, (a, union, c) in enumerate(arriba):
            borde = "+" if i == 0 else "|"
            fin = "+" if c.startswith("-") else borde
            lineas.append(f"{borde}{_c(a, cuarto)}{union}{_c(c, derecha)}{fin}")
    division = "+" + "-" * cuarto + "+" + ("-" * extra + "+" if "extra" in zonas else "") + "-" * derecha + "+"
    lineas.append(division)
    comprado = "  " + "  ".join(objetos) if objetos else ""
    for texto in (" SALA · COCINA · COMEDOR", "", "  cocina  nevera   mesa", comprado, "  " + m["salon"]):
        lineas.append(f"|{_c(texto, ancho)}|")
    lineas.append("+" + "-" * ancho + "+")
    return lineas
