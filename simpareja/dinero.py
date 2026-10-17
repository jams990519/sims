"""Casa, dinero y gastos (parte 5). Todo en dólares; lógica pura, sin Telegram ni base de datos."""

from __future__ import annotations

import random
from dataclasses import dataclass

DINERO_INICIAL = 3000  # lo que tienen entre los dos al empezar
ENTRADA_CASA = 1500
DIAS_POR_MES = 30
RECARGO = 0.10  # por pagar tarde
PROBABILIDAD_IMPREVISTO = 0.08  # por día

CASA_INICIAL = {
    "nombre": "Casita",
    "emoji": "🏡",
    "descripcion": "Una casa pequeña con baño, clóset, un cuarto y una sala-cocina-comedor grande.",
}


@dataclass(frozen=True)
class Factura:
    clave: str
    emoji: str
    nombre: str
    base: int  # al mes
    sin_servicio: str  # qué pasa si se corta


FACTURAS = (
    Factura("hipoteca", "🔑", "Hipoteca", 700, ""),
    Factura("luz", "💡", "Luz", 90, "no hay tele, redes ni lavadora"),
    Factura("agua", "🚰", "Agua", 40, "no se pueden duchar, bañar, lavar los dientes ni la ropa"),
    Factura("internet", "🌐", "Internet", 50, "no hay redes ni videos"),
    Factura("gas", "🔥", "Gas", 30, "no se puede cocinar"),
)
POR_CLAVE_FACTURA = {f.clave: f for f in FACTURAS}
SERVICIOS = ("luz", "agua", "internet", "gas")

# Lo que cuesta cada comida por persona.
PRECIO_COMIDA = {"desayuno": 3, "almuerzo": 5, "cena": 4}
PRECIO_PICAR = 1

# Servicios que necesita cada acción.
NECESITA_SERVICIO = {
    "tele": ("luz",),
    "redes": ("luz", "internet"),
    "lavar": ("luz", "agua"),
    "cocinar": ("gas",),
    "ducha": ("agua",),
    "banarse": ("agua",),
    "dientes": ("agua",),
}

# Consumo que suma cada acción a la factura del mes (en dólares).
CONSUMO = {
    "tele": {"luz": 0.30},
    "redes": {"luz": 0.15},
    "lavar": {"luz": 1.00, "agua": 1.50},
    "cocinar": {"luz": 0.20},
    "ducha": {"agua": 0.60},
    "banarse": {"agua": 1.20},
    "dientes": {"agua": 0.05},
    "limpiar": {"agua": 0.30},
}

IMPREVISTOS = (
    ("🔧", "Se rompió la lavadora", 150, 300),
    ("🚿", "Hubo una fuga de agua en el baño", 150, 280),
    ("🧊", "Se dañó la nevera", 180, 300),
    ("🔌", "Se quemó un enchufe y hubo que llamar al electricista", 150, 220),
    ("🚓", "Les pusieron una multa de tránsito", 60, 150),
    ("📢", "Les pusieron una multa por ruido", 50, 120),
)


def dinero(cantidad: float) -> str:
    """'$3.000' con punto de miles (y '−$50' si es negativo)."""
    signo = "−" if cantidad < 0 else ""
    return f"{signo}${abs(round(cantidad)):,}".replace(",", ".")


def factura_del_mes(consumo: dict) -> list[tuple[Factura, int]]:
    """Cada factura con lo que toca pagar este mes: base más lo consumido."""
    return [(f, round(f.base + consumo.get(f.clave, 0))) for f in FACTURAS]


def total_mes(consumo: dict) -> int:
    return sum(monto for _, monto in factura_del_mes(consumo))


def precio_comida(comida: str) -> int:
    return PRECIO_COMIDA.get(comida, 4)


def servicios_cortados(pendientes: list[dict]) -> set[str]:
    return {p["clave"] for p in pendientes if p["clave"] in SERVICIOS}


def falta_servicio(accion: str, cortados: set[str]) -> str | None:
    """Mensaje si la acción necesita un servicio cortado."""
    for servicio in NECESITA_SERVICIO.get(accion, ()):
        if servicio in cortados:
            f = POR_CLAVE_FACTURA[servicio]
            return f"{f.emoji} Les cortaron la {f.nombre.lower()}: {f.sin_servicio}. Paguen la factura en 💰 Dinero."
    return None


def imprevisto(rng: random.Random) -> tuple[str, int] | None:
    """Con cierta probabilidad, una avería o una multa: (descripción, costo)."""
    if rng.random() >= PROBABILIDAD_IMPREVISTO:
        return None
    emoji, texto, minimo, maximo = rng.choice(IMPREVISTOS)
    return f"{emoji} {texto}", rng.randint(minimo, maximo)


def cobrar_mes(cuenta: int, consumo: dict) -> tuple[int, list[tuple[str, int]], list[dict]]:
    """Cobra las facturas del mes desde la cuenta compartida, en orden.

    Devuelve la cuenta restante, lo pagado [(concepto, monto)] y lo que no se pudo pagar,
    ya con el recargo del 10 % [{"clave", "monto"}].
    """
    pagado, impagos = [], []
    for f, monto in factura_del_mes(consumo):
        if cuenta >= monto:
            cuenta -= monto
            pagado.append((f.clave, monto))
        else:
            impagos.append({"clave": f.clave, "monto": round(monto * (1 + RECARGO))})
    return cuenta, pagado, impagos
