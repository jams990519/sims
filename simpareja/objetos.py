"""Objetos de la casa y tiendas que crecen (actualización 2, parte 13). Lógica pura.

Con la casa vienen la cama, la estufa, la nevera, la ducha y un móvil básico; lo demás se compra
en la tienda de muebles o en la de electrónica. Las tiendas sacan más cosas según el progreso
(los hitos que han celebrado). En casa propia, además, se puede remodelar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

INCLUIDOS = ("🛏️ cama", "🔥 estufa", "🧊 nevera", "🚿 ducha", "📱 móvil básico")
LAVANDERIA = 8  # lavar la ropa sin lavadora


@dataclass(frozen=True)
class Objeto:
    clave: str
    emoji: str
    nombre: str
    precio: int
    tienda: str  # "muebles" | "electronica" | "reforma"
    efecto: str
    nivel: int = 1  # hitos celebrados que hacen falta para que la tienda lo saque
    bonos: dict = field(default_factory=dict)  # acción → {necesidad: multiplicador del efecto}
    extra: dict = field(default_factory=dict)  # acción → {necesidad: puntos de más}
    en_plano: str = ""  # cómo se ve en el plano (sin emojis)


OBJETOS: dict[str, Objeto] = {o.clave: o for o in (
    # 📺 Electrónica
    Objeto("tv", "📺", "Televisión", 300, "electronica", "Sin ella no se puede ver la tele.", en_plano="tele"),
    Objeto("lavadora", "🧺", "Lavadora", 350, "electronica",
           f"Sin ella hay que ir a la lavandería (${LAVANDERIA} cada vez).", en_plano="lavadora"),
    Objeto("movil", "📱", "Móvil mejor", 200, "electronica", "Las redes rinden un 50 % más.",
           bonos={"redes": {"diversion": 1.5, "social": 1.5}, "telefono": {"social": 1.25}}),
    Objeto("camara", "📷", "Cámara", 250, "electronica", "Equipo de influencer: mejor calidad de video."),
    Objeto("aro", "💡", "Aro de luz", 60, "electronica", "Equipo de influencer: mejor calidad de video."),
    Objeto("micro", "🎙️", "Micrófono", 80, "electronica", "Equipo de influencer: mejor calidad de video."),
    Objeto("consola", "🎮", "Consola de videojuegos", 400, "electronica", "Nueva acción: jugar a la consola.",
           nivel=2, en_plano="consola"),
    # 🛋️ Muebles
    Objeto("sofa", "🛋️", "Sofá", 400, "muebles", "Ver la tele o redes divierte un 25 % más.",
           bonos={"tele": {"diversion": 1.25}, "redes": {"diversion": 1.25}, "consola": {"diversion": 1.25}},
           en_plano="sofá"),
    Objeto("cama", "🛏️", "Cama grande", 600, "muebles", "Dormir recupera un 15 % más de energía.",
           bonos={"dormir": {"energia": 1.15}, "siesta": {"energia": 1.15}}),
    Objeto("plantas", "🪴", "Plantas", 60, "muebles", "La diversión baja un 10 % más lento.", nivel=2),
    Objeto("cuadros", "🖼️", "Cuadros", 120, "muebles", "La diversión baja un 10 % más lento.", nivel=2),
    Objeto("banera", "🛁", "Bañera grande", 900, "muebles", "Bañarse juntos: más higiene y +10 de social.",
           nivel=4, bonos={"banarse": {"higiene": 1.2}}, extra={"banarse": {"social": 10}}),
    # 🔨 Reformas (solo en casa propia)
    Objeto("pintar", "🎨", "Pintar y decorar", 400, "reforma", "La casa se ensucia la mitad."),
    Objeto("bano", "🚿", "Baño nuevo", 1500, "reforma", "Ducharse da +10 de higiene.", extra={"ducha": {"higiene": 10}}),
)}
TIENDAS = {
    "muebles": "🛋️ Tienda de muebles",
    "electronica": "📺 Tienda de electrónica",
    "reforma": "🔨 Remodelar",
}
DECORACION = ("plantas", "cuadros")  # cada uno: la diversión baja un 10 % más lento


def del_nivel(tienda: str, nivel: int) -> tuple[list[Objeto], list[Objeto]]:
    """Lo que la tienda tiene a la venta con ese progreso, y lo que todavía no saca."""
    todos = [o for o in OBJETOS.values() if o.tienda == tienda]
    return [o for o in todos if o.nivel <= nivel], [o for o in todos if o.nivel > nivel]


def aplicar_bonos(accion: str, efectos: dict, tienen: set[str]) -> dict:
    """Los efectos de una acción con los objetos que tienen."""
    efectos = dict(efectos)
    for clave in tienen:
        o = OBJETOS.get(clave)
        if o is None:
            continue
        for necesidad, factor in o.bonos.get(accion, {}).items():
            if efectos.get(necesidad, 0) > 0:
                efectos[necesidad] = round(efectos[necesidad] * factor, 1)
        for necesidad, puntos in o.extra.get(accion, {}).items():
            efectos[necesidad] = efectos.get(necesidad, 0) + puntos
    return efectos
