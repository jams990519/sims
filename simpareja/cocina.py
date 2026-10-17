"""Súper, ingredientes y recetas (parte 7). Lógica pura, sin Telegram ni base de datos."""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import vida as V

OFERTA_FIN_DE_SEMANA = 0.20  # el súper tiene ofertas los sábados y domingos
OFERTA_SORPRESA = 0.5  # evento sorpresa: la compra a mitad de precio ese día
FACTOR_JUNTOS = V.FACTOR_JUNTOS
MARGEN_MINIMO = 2  # minutos de margen para tocar "listo" antes de que se queme


@dataclass(frozen=True)
class Ingrediente:
    clave: str
    emoji: str
    nombre: str
    paquete: str  # cómo se vende
    unidades: int  # cuántas unidades trae el paquete
    precio: float
    lugar: str  # 'nevera' | 'despensa'
    nivel: int = 1  # el súper lo trae a partir de este nivel


INGREDIENTES: dict[str, Ingrediente] = {i.clave: i for i in (
    Ingrediente("huevos", "🥚", "Huevos", "docena", 12, 3.0, "nevera"),
    Ingrediente("pan", "🍞", "Pan", "bolsa de 10 rebanadas", 10, 2.5, "despensa"),
    Ingrediente("cafe", "☕", "Café", "paquete para 10 tazas", 10, 4.0, "despensa"),
    Ingrediente("mantequilla", "🧈", "Mantequilla", "barra (8 usos)", 8, 2.5, "nevera"),
    Ingrediente("arroz", "🍚", "Arroz", "bolsa de 5 raciones", 5, 2.5, "despensa"),
    Ingrediente("pollo", "🍗", "Pollo", "bandeja de 2 raciones", 2, 5.0, "nevera"),
    Ingrediente("pasta", "🍝", "Pasta", "paquete de 4 raciones", 4, 2.0, "despensa"),
    Ingrediente("tomate", "🥫", "Salsa de tomate", "frasco de 2 raciones", 2, 2.0, "despensa"),
    Ingrediente("verduras", "🥕", "Verduras", "bolsa de 2 raciones", 2, 3.0, "nevera"),
    Ingrediente("jamon", "🥓", "Jamón", "paquete de 4 lonchas", 4, 3.0, "nevera"),
    Ingrediente("queso", "🧀", "Queso", "paquete de 4 lonchas", 4, 3.0, "nevera"),
    # El súper crece: llegan con más recetas cocinadas.
    Ingrediente("carne", "🥩", "Carne", "bandeja de 2 bistecs", 2, 6.0, "nevera", nivel=2),
    Ingrediente("papas", "🥔", "Papas", "bolsa de 4 raciones", 4, 2.5, "despensa", nivel=2),
    Ingrediente("leche", "🥛", "Leche", "litro (4 vasos)", 4, 1.5, "nevera", nivel=2),
    Ingrediente("harina", "🌾", "Harina", "paquete de 6 usos", 6, 2.0, "despensa", nivel=2),
    Ingrediente("pescado", "🐟", "Pescado", "filetes para 2", 2, 7.0, "nevera", nivel=3),
    Ingrediente("frutas", "🍓", "Frutas", "bolsa para 4 batidos", 4, 4.0, "nevera", nivel=3),
)}


@dataclass(frozen=True)
class Receta:
    clave: str
    emoji: str
    nombre: str
    comida: str  # 'desayuno' | 'almuerzo' | 'cena'
    ingredientes: dict  # unidades por porción
    pasos: tuple[tuple[str, int], ...]  # (qué hacer, minutos)
    nivel: int = 1  # aparece en el recetario a partir de este nivel del súper

    @property
    def minutos(self) -> int:
        return sum(m for _, m in self.pasos)


RECETAS: dict[str, Receta] = {r.clave: r for r in (
    Receta("huevos", "🍳", "Huevos revueltos con pan", "desayuno", {"huevos": 2, "pan": 1}, (
        ("🥣 Batir los huevos", 2),
        ("🍳 Cocinarlos removiendo en la sartén", 4),
        ("🍞 Tostar el pan y servir", 2),
    )),
    Receta("tostadas", "☕", "Café con tostadas", "desayuno", {"cafe": 1, "pan": 2, "mantequilla": 1}, (
        ("☕ Preparar el café", 4),
        ("🍞 Tostar el pan", 2),
        ("🧈 Untar la mantequilla y servir", 1),
    )),
    Receta("arroz_pollo", "🍛", "Arroz con pollo", "almuerzo", {"arroz": 1, "pollo": 1}, (
        ("🍗 Dorar el pollo", 6),
        ("🧅 Sofreír y añadir el arroz", 3),
        ("🔥 Cocer a fuego lento", 12),
        ("🍽️ Reposar y servir", 2),
    )),
    Receta("pasta", "🍝", "Pasta con salsa de tomate", "almuerzo", {"pasta": 1, "tomate": 1}, (
        ("💧 Hervir el agua", 5),
        ("🍝 Cocer la pasta", 9),
        ("🥫 Calentar la salsa y mezclar", 3),
    )),
    Receta("sopa", "🥣", "Sopa de verduras", "cena", {"verduras": 1}, (
        ("🔪 Picar las verduras", 5),
        ("🔥 Hervir la sopa", 15),
        ("🧂 Sazonar y servir", 2),
    )),
    Receta("sandwich", "🥪", "Sándwich de jamón y queso", "cena", {"pan": 2, "jamon": 1, "queso": 1}, (
        ("🥪 Armar el sándwich", 2),
        ("🔥 Dorarlo en la sartén", 4),
    )),
    Receta("panqueques", "🥞", "Panqueques", "desayuno", {"harina": 1, "leche": 1, "huevos": 1}, (
        ("🥣 Mezclar la masa", 3),
        ("🍳 Cocinar los panqueques", 8),
        ("🍯 Servir con miel", 1),
    ), nivel=2),
    Receta("bistec", "🥩", "Bistec con papas", "cena", {"carne": 1, "papas": 1}, (
        ("🥔 Pelar y cortar las papas", 5),
        ("🍟 Freír las papas", 8),
        ("🥩 Asar el bistec", 6),
        ("🍽️ Servir", 1),
    ), nivel=2),
    Receta("batido", "🥤", "Batido de frutas", "desayuno", {"frutas": 1, "leche": 1}, (
        ("🍓 Cortar las frutas", 3),
        ("🌀 Licuar", 2),
    ), nivel=3),
    Receta("pescado", "🐟", "Pescado con verduras", "almuerzo", {"pescado": 1, "verduras": 1}, (
        ("🔪 Limpiar el pescado", 5),
        ("🥕 Saltear las verduras", 6),
        ("🐟 Cocinar el pescado", 8),
        ("🍋 Servir con limón", 1),
    ), nivel=3),
)}
# Recetas cocinadas que hacen falta para que el súper suba de nivel.
NIVELES_SUPER = {2: 5, 3: 15}


def nivel_super(cocinadas: int) -> int:
    return max([1] + [n for n, hacen_falta in NIVELES_SUPER.items() if cocinadas >= hacen_falta])


def siguiente_nivel(cocinadas: int) -> int | None:
    """Cuántas recetas cocinadas hacen falta para el próximo nivel (None si ya está al máximo)."""
    faltan = [hacen_falta for hacen_falta in NIVELES_SUPER.values() if cocinadas < hacen_falta]
    return min(faltan) if faltan else None

COMIDAS = (("desayuno", "🌅 Desayunos"), ("almuerzo", "☀️ Almuerzos"), ("cena", "🌙 Cenas"))


def precio(ingrediente: str, finde: bool, oferta: bool = False) -> float:
    """Precio de un paquete: con oferta (evento sorpresa) a mitad de precio; el fin de semana, −20 %."""
    base = INGREDIENTES[ingrediente].precio
    if oferta:
        return round(base * OFERTA_SORPRESA, 2)
    return round(base * (1 - OFERTA_FIN_DE_SEMANA), 2) if finde else base


def total_carrito(carrito: dict, finde: bool, oferta: bool = False) -> float:
    return round(sum(precio(i, finde, oferta) * n for i, n in carrito.items() if i in INGREDIENTES), 2)


def guardar_compra(despensa: dict, carrito: dict) -> dict:
    """Suma los paquetes comprados (en unidades) a la nevera y despensa."""
    despensa = dict(despensa)
    for i, paquetes in carrito.items():
        if i in INGREDIENTES:
            despensa[i] = despensa.get(i, 0) + paquetes * INGREDIENTES[i].unidades
    return despensa


def faltan(despensa: dict, receta: Receta, porciones: int) -> dict:
    """Ingredientes que faltan para cocinar esas porciones (vacío si alcanza)."""
    return {
        i: n * porciones - despensa.get(i, 0)
        for i, n in receta.ingredientes.items() if despensa.get(i, 0) < n * porciones
    }


def usar(despensa: dict, receta: Receta, porciones: int) -> dict:
    despensa = dict(despensa)
    for i, n in receta.ingredientes.items():
        despensa[i] = despensa.get(i, 0) - n * porciones
        if despensa[i] <= 0:
            despensa.pop(i)
    return despensa


def minutos_paso(minutos: int, juntos: bool) -> int:
    return max(1, round(minutos * FACTOR_JUNTOS)) if juntos else minutos


def margen(minutos: int) -> int:
    """Minutos de gracia después de que el paso está listo; si se pasan, se quema."""
    return max(MARGEN_MINIMO, math.ceil(minutos * 0.5))


def duracion_maxima(receta: Receta, juntos: bool) -> int:
    """Minutos que dura la acción de cocinar si se toca cada paso en el último momento."""
    return sum(minutos_paso(m, juntos) + margen(minutos_paso(m, juntos)) for _, m in receta.pasos)


def texto_ingredientes(ingredientes: dict, porciones: int = 1) -> str:
    return ", ".join(
        f"{INGREDIENTES[i].emoji} {INGREDIENTES[i].nombre.lower()} ×{n * porciones}" for i, n in ingredientes.items()
    )
