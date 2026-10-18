"""Narración de las acciones: mensajitos que llegan mientras el Sim hace algo (versión 0.34).

Lógica pura, sin Telegram ni base de datos. Cada acción con narración tiene sus etapas: en qué parte
de la acción llega (de 0 a 1) y qué dice, en singular y para cuando la hacen juntos. Algunas etapas
preguntan algo (la carta y el postre del restaurante).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Etapa:
    fraccion: float  # en qué parte de la acción llega (0 = al empezar, 1 = al terminar)
    solo: str
    juntos: str = ""
    pregunta: str = ""  # "carta" o "postre": el mensaje trae botones

    def texto(self, juntos: bool) -> str:
        return self.juntos if juntos and self.juntos else self.solo


def siguiente(etapas: tuple[Etapa, ...], enviadas: int, progreso: float) -> int | None:
    """La etapa que toca mandar ahora (si se juntaron varias, solo la última), o None."""
    alcanzadas = [i for i, e in enumerate(etapas) if e.fraccion <= progreso]
    if not alcanzadas or alcanzadas[-1] < enviadas:
        return None
    return alcanzadas[-1]


# --- 🍝 Restaurante -------------------------------------------------------------

RESTAURANTES = ("La Buena Mesa", "El Rincón Criollo", "Sabor de Casa", "La Terraza", "El Fogón")
PLATOS = {
    "pasta": ("🍝", "pasta a la boloñesa"),
    "cerdo": ("🍖", "cerdo asado con congrí"),
    "pollo": ("🍗", "pollo asado con papas"),
    "pescado": ("🐟", "pescado a la plancha"),
    "pizza": ("🍕", "pizza de la casa"),
    "ensalada": ("🥗", "ensalada fresca"),
}
DE_LA_CASA = "cerdo"
POSTRE = 5  # dólares
POSTRES = ("🍰 un pastel de chocolate", "🍮 un flan casero", "🍨 un helado de vainilla")

RESTAURANTE = (
    Etapa(0.03, "🚗 Llegas a <b>{lugar}</b>. Huele delicioso.",
          "🚗 Llegan juntos a <b>{lugar}</b>. Huele delicioso."),
    Etapa(0.10, "🤵 El mesero te recibe y te lleva a una mesa junto a la ventana.",
          "🤵 El mesero los recibe y los lleva a una mesa para dos junto a la ventana. 🕯️"),
    Etapa(0.18, "📜 Te presentan la carta. ¿Qué vas a pedir?",
          "📜 Les presentan la carta. ¿Qué vas a pedir tú?", pregunta="carta"),
    Etapa(0.32, "🍹 Mientras esperas, te traen algo de tomar. En la cocina preparan tu {plato}.",
          "🍹 Mientras esperan, les traen algo de tomar y conversan. 💬 En la cocina preparan tu {plato}."),
    Etapa(0.45, "🍽️ ¡Llega tu {plato}! Se ve increíble.",
          "🍽️ ¡Llegan los platos! Tu {plato} se ve increíble."),
    Etapa(0.60, "😋 Comiendo… está buenísimo.",
          "😋 Comen y se ríen entre bocado y bocado. 💞"),
    Etapa(0.75, "🥄 Último bocado. ¡Qué rico estuvo!",
          "🥄 Último bocado. Se miran: ¡qué rico estuvo!"),
    Etapa(0.82, f"🍰 El mesero pregunta: ¿algo de postre? (${POSTRE})",
          f"🍰 El mesero pregunta: ¿algo de postre? (${POSTRE})", pregunta="postre"),
    Etapa(0.95, "🧾 Pides la cuenta, dejas la propina y sales de {lugar}. ¡De vuelta a casa!",
          "🧾 Piden la cuenta, dejan la propina y salen de {lugar} de la mano. 💞 ¡De vuelta a casa!"),
)

ETAPAS: dict[str, tuple[Etapa, ...]] = {
    "restaurante": RESTAURANTE,
}
