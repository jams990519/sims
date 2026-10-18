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

E = Etapa

ETAPAS: dict[str, tuple[Etapa, ...]] = {
    "restaurante": RESTAURANTE,
    # 📍 Lugares
    "super": (
        E(0.10, "🛒 Llegas al súper y agarras un carrito.", "🛒 Llegan al súper y agarran un carrito."),
        E(0.45, "🥫 Recorres los pasillos buscando lo de la lista.",
          "🥫 Recorren los pasillos: uno lee la lista y el otro busca."),
        E(0.80, "🧾 Haces la fila en la caja… ¡ya casi!", "🧾 Hacen la fila en la caja mientras conversan."),
    ),
    "cine": (
        E(0.04, "🎟️ Llegas al cine y compras la entrada.", "🎟️ Llegan al cine y compran las entradas para los dos."),
        E(0.10, "🍿 Palomitas y refresco en mano. ¡A la sala!", "🍿 Comparten unas palomitas grandes. ¡A la sala!"),
        E(0.20, "🎬 Se apagan las luces: empieza la película."),
        E(0.50, "😮 ¡Qué giro! Nadie se lo esperaba.", "😮 ¡Qué giro! Se miran sin poder creerlo."),
        E(0.80, "😢 Llega la parte más emocionante…", "🤝 En la parte más emocionante, se toman de la mano."),
        E(0.96, "👏 Salen los créditos. ¡Buena película!",
          "👏 Salen los créditos. De camino a casa comentan la película."),
    ),
    "parque": (
        E(0.10, "🌳 Llegas al parque: hace un día bonito.", "🌳 Llegan al parque de la mano: hace un día bonito."),
        E(0.40, "🦆 Ves los patos del estanque y les tiras unas migas.", "🦆 Se paran a ver los patos del estanque."),
        E(0.70, "🪑 Te sientas en una banca a descansar un rato.",
          "🪑 Se sientan en una banca y conversan un rato. 💬"),
        E(0.92, "🌇 Cae la tarde: es hora de volver.", "🌇 Cae la tarde: vuelven a casa caminando."),
    ),
    "gimnasio": (
        E(0.08, "🏋️ Llegas al gimnasio y calientas un poco.", "🏋️ Llegan al gimnasio y calientan juntos."),
        E(0.35, "💪 Toca pesas: una serie más… ¡tú puedes!", "💪 Toca pesas: se animan el uno al otro en cada serie."),
        E(0.65, "🏃 Ahora cardio: la cinta no perdona.", "🏃 Cardio lado a lado en las cintas."),
        E(0.90, "🧘 Estiramientos para terminar. ¡Buen entrenamiento!", "🧘 Estiran juntos. ¡Buen entrenamiento!"),
    ),
    # 🎉 Diversión
    "tele": (
        E(0.10, "📺 Enciendes la tele y buscas algo que ver.", "📺 Se acomodan en el sofá y buscan algo que ver."),
        E(0.50, "📢 Anuncios… aprovechas para ir por agua.", "📢 Anuncios… uno va por algo de picar."),
        E(0.90, "🎞️ Termina el capítulo con un final de suspenso.",
          "🎞️ ¡Final de capítulo! «Uno más», dicen los dos."),
    ),
    "consola": (
        E(0.10, "🎮 Enciendes la consola. ¡A jugar!", "🎮 Toman los controles. ¡Que empiece la partida!"),
        E(0.50, "😤 Un nivel difícil… lo intentas otra vez.", "😂 Uno le gana al otro y pide la revancha."),
        E(0.90, "🏆 ¡Lo pasaste! Guardas la partida.", "🏆 Última partida: ¡empate! Hasta la próxima."),
    ),
    "redes": (
        E(0.15, "📱 Revisas las redes: memes, fotos y noticias.", "📱 Se ponen a ver videos juntos en el sofá."),
        E(0.60, "😂 Un video te hace reír a carcajadas.", "😂 Un video los hace reír a carcajadas."),
    ),
    "telefono": (
        E(0.15, "📞 Llamas a alguien de la familia: ¡qué alegría oír su voz!"),
        E(0.70, "💬 Se ponen al día con todas las novedades."),
    ),
    # 🚿 Higiene
    "ducha": (
        E(0.20, "🚿 Abres el agua caliente… ¡qué rico!"),
        E(0.70, "🎶 Cantas en la ducha como si fuera un concierto."),
    ),
    "banarse": (
        E(0.15, "🛁 Llenan la bañera con agua tibia y mucha espuma."),
        E(0.60, "🫧 Burbujas, risas y relax."),
    ),
    # 🍽️ Comer
    "comer": (
        E(0.10, "🍽️ Sirves la comida y te sientas a la mesa.", "🍽️ Sirven la comida y se sientan a la mesa juntos."),
        E(0.50, "😋 Comiendo tranquilamente…", "😋 Comen y se cuentan cómo les fue el día. 💬"),
        E(0.90, "🥄 Último bocado. ¡Qué rico!"),
    ),
    "domicilio": (
        E(0.10, "📱 Haces el pedido por teléfono.", "📱 Eligen juntos qué pedir."),
        E(0.35, "🛵 El repartidor viene en camino…"),
        E(0.55, "🔔 ¡Ding dong! Llegó el pedido."),
        E(0.75, "😋 A comer: está calentito.", "😋 Comen en el sofá: ¡está calentito!"),
    ),
    # 😴 Descanso
    "siesta": (
        E(0.15, "💤 Cierras los ojos un ratito…", "💤 Se acurrucan para una siestecita."),
        E(0.90, "😌 Te estiras: ¡qué bien te sentó!", "😌 Se despiertan descansados."),
    ),
    # 💞 Pareja
    "hablar": (
        E(0.30, "💬 Se cuentan cómo les fue el día."),
        E(0.75, "😄 Terminan riéndose de una tontería."),
    ),
    "masaje": (
        E(0.20, "💆 Aceite tibio y música suave…"),
        E(0.70, "😌 Toda la tensión del día se va."),
    ),
    # 🧹 Limpieza
    "limpiar": (
        E(0.15, "🧹 Barres el piso de punta a punta.", "🧹 Uno barre y el otro trapea."),
        E(0.55, "🧽 Ahora a fregar y sacudir el polvo.", "🧽 Fregar, sacudir… ¡trabajo en equipo!"),
        E(0.90, "✨ ¡Todo brilla!"),
    ),
    "lavar": (
        E(0.10, "🧺 Separas la ropa blanca de la de color.", "🧺 Separan la ropa entre los dos."),
        E(0.40, "🌀 La ropa da vueltas y vueltas…"),
        E(0.75, "👕 Tiendes la ropa al sol.", "👕 Tienden la ropa al sol."),
        E(0.95, "🧦 Doblas la ropa… ¿dónde está el otro calcetín?", "🧦 Doblan la ropa… ¿dónde está el otro calcetín?"),
    ),
    # 🐾 Mascota
    "pasear": (
        E(0.10, "🐕 Sales con el perro: mueve la cola feliz.", "🐕 Salen con el perro: mueve la cola feliz."),
        E(0.45, "🌳 Olfatea cada árbol del camino."),
        E(0.75, "🐶 Juega un rato con otro perrito del barrio."),
        E(0.93, "🏠 De vuelta a casa: el perro está cansado y contento."),
    ),
    "jugar_mascota": (
        E(0.20, "🎾 Le tiras la pelota… ¡y la trae de vuelta!", "🎾 Se turnan para tirarle la pelota."),
        E(0.70, "🐾 Se revuelca feliz esperando cariño."),
    ),
    "banar_mascota": (
        E(0.25, "🛁 Al agua… a la mascota no le hace mucha gracia."),
        E(0.75, "🫧 ¡Espuma por todos lados! Al final queda reluciente."),
    ),
    # 📱 Influencer y 📚 estudios
    "grabar": (
        E(0.10, "🎥 Preparas la cámara y la luz.", "🎥 Preparan la cámara: uno graba y el otro sale."),
        E(0.45, "🎬 Toma 1… toma 2… ¡toma 5!"),
        E(0.85, "✅ ¡Esta toma quedó perfecta!"),
    ),
    "editar": (
        E(0.20, "✂️ Cortas las partes aburridas."),
        E(0.60, "🎶 Le pones música y textos."),
        E(0.90, "📤 Exportando el video…"),
    ),
    "aprender_redes": (
        E(0.15, "📚 Ves un tutorial sobre cómo crecer en redes."),
        E(0.60, "📝 Tomas apuntes de los mejores trucos."),
    ),
    "estudiar": (
        E(0.10, "📚 Abres los libros y repasas los apuntes.", "📚 Abren los libros y se toman la lección."),
        E(0.45, "🤯 Un ejercicio difícil… lo lees otra vez.", "🤔 Un ejercicio difícil: lo resuelven entre los dos."),
        E(0.85, "💡 ¡Lo entendiste!", "💡 ¡Lo entendieron! Chocan los cinco."),
    ),
}

# --- 🍳 Cocina: qué vas haciendo a mitad de cada paso (receta → número de paso → texto) ---
COCINA_DESDE = 2  # minutos: los pasos más cortos no tienen mensajito
COCINA: dict[str, dict[int, str]] = {
    "huevos": {1: "🍳 Los huevos chisporrotean; los mueves con la espátula para que queden cremosos."},
    "tostadas": {0: "☕ El café empieza a gotear… ¡qué aroma!"},
    "arroz_pollo": {
        0: "🍗 El pollo se dora en el aceite caliente; le das la vuelta para que quede parejo.",
        1: "🧅 La cebolla y el ajo se sofríen… huele a casa.",
        2: "🔥 El arroz hierve suavecito: tapas la olla y bajas el fuego.",
    },
    "pasta": {
        0: "💧 Pones el agua a hervir con una pizca de sal.",
        1: "🍝 Remueves la pasta para que no se pegue: ya casi está al dente.",
        2: "🥫 La salsa burbujea; la mezclas con la pasta.",
    },
    "sopa": {
        0: "🔪 Picas las verduras en cuadritos: zanahoria, papa, calabaza…",
        1: "🔥 La sopa hierve despacio y llena la cocina de vapor.",
    },
    "sandwich": {1: "🔥 El queso empieza a derretirse mientras el pan se dora."},
    "panqueques": {
        0: "🥣 Mezclas harina, leche y huevo hasta que no queden grumos.",
        1: "🍳 Cuando salen burbujitas, volteas el panqueque… ¡arriba!",
    },
    "bistec": {
        0: "🥔 Pelas las papas y las cortas en bastones.",
        1: "🍟 Las papas se fríen y se ponen doraditas.",
        2: "🥩 El bistec chisporrotea en la plancha; lo volteas una vez.",
    },
    "batido": {0: "🍓 Cortas las frutas en trocitos."},
    "pescado": {
        0: "🔪 Limpias el pescado con cuidado y lo sazonas.",
        1: "🥕 Las verduras se saltean con un poquito de aceite.",
        2: "🐟 El pescado se cocina a fuego medio: la piel queda crujiente.",
    },
}


def texto_cocina(receta: str, paso: int, texto_paso: str) -> str:
    """Lo que estás haciendo a mitad del paso (o, si no hay uno escrito, el paso mismo)."""
    return COCINA.get(receta, {}).get(paso) or f"👩‍🍳 {texto_paso}…"
