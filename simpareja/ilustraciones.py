"""Fotos de las acciones (versión 0.43): imágenes estilo serie de anime hechas por una IA de imágenes.

Lógica pura, sin Telegram ni red. Arma la descripción en inglés de cada imagen para la IA (la escena, la luz
según la hora real y los rasgos de cada personaje) y deja la imagen lista para Telegram: pequeña (un JPEG de
unos 60 KB) y, en los momentos íntimos, pixelada abajo (los besos se ven). Quien se la pide a la IA es `imagenes_ia.py`.

Cada imagen tiene su clave "escena:momento:figuras":
- escena: "parque_banca", "masaje", "cocina.pasta", "pasear.perro.3" (la mascota y su color)…
- momento: manana, tarde, atardecer o noche (bajo techo basta con dia, atardecer o noche);
- figuras: el aspecto de cada uno (`figura`), separados por "|" y en orden, para que la misma escena de los
  dos sea una sola imagen.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

ANCHO, ALTO = 768, 512  # lo que llega a Telegram (la IA la hace más grande y aquí se reduce)
CALIDAD_JPEG = 78
PIXEL = 18  # tamaño de los cuadritos del pixelado


@dataclass(frozen=True)
class Escena:
    solo: str  # en inglés: qué está haciendo el personaje
    juntos: str = ""  # en pareja (si no, la de solo con los dos)
    afuera: bool = False  # al aire libre: la luz cambia con las cuatro partes del día
    ropa: str = ""  # la ropa que toca en la escena (si no, la de su estilo)
    intimo: bool = False  # nada explícito y con la parte de abajo pixelada
    romance: bool = False  # de cerca, como en una serie de anime romántica (besos, abrazos, momento íntimo)


E = Escena
PARQUE = "a beautiful tropical city park with palm trees, a ceiba tree and winding paths"
INTIMO = ("Tasteful and non-explicit: fully clothed, only kisses and affection, their faces in the upper "
          "half of the frame")
ESCENAS: dict[str, Escena] = {
    # 🌳 Parque: una foto en cada mensajito
    "parque_llegada": E(f"walking into {PARQUE}, smiling", f"a couple walking hand in hand into {PARQUE}",
                        afuera=True),
    "parque_patos": E(f"standing by a small pond in {PARQUE}, tossing bread crumbs to the ducks",
                      f"a couple standing together by a small pond in {PARQUE}, watching the ducks", afuera=True),
    "parque_banca": E(f"sitting on a wooden bench in {PARQUE}, relaxed, looking up at the sky",
                      f"a couple sitting close together on a wooden bench in {PARQUE}, talking and smiling at "
                      "each other", afuera=True),
    "parque_regreso": E(f"walking home along a path of {PARQUE}", f"a couple walking home hand in hand along a "
                        f"path of {PARQUE}", afuera=True),
    # 📍 Salidas
    "restaurante": E("dining at a cozy restaurant table by the window, a candle and a delicious plate of food",
                     "a couple on a dinner date at a cozy restaurant table for two by the window, candlelight, "
                     "plates of food, smiling at each other", ropa="nice going-out clothes"),
    "super": E("pushing a shopping cart down a colorful supermarket aisle, reading a shopping list",
               "a couple pushing a shopping cart together down a colorful supermarket aisle, one of them "
               "reading the shopping list"),
    "cine": E("watching a movie in a dark cinema, face lit by the big screen, holding a bucket of popcorn",
              "a couple in a dark cinema holding hands, faces lit by the big screen, sharing a bucket of popcorn"),
    "gimnasio": E("working out with dumbbells in a bright modern gym", "a couple working out together in a "
                  "bright modern gym, cheering each other on", ropa="sportswear"),
    # 🎉 Diversión
    "tele": E("relaxing on a living-room sofa watching TV, a bowl of snacks", "a couple cuddled on a "
              "living-room sofa under a blanket, watching TV with a bowl of snacks", ropa="comfy home clothes"),
    "consola": E("playing video games on the living-room sofa, gripping a game controller, focused",
                 "a couple on the living-room sofa playing video games with controllers, laughing and competing",
                 ropa="comfy home clothes"),
    "redes": E("lounging on the sofa scrolling a smartphone and laughing", "a couple on the sofa watching funny "
               "videos on one phone, laughing out loud", ropa="comfy home clothes"),
    "telefono": E("talking happily on the phone at home, sitting by the window", ropa="comfy home clothes"),
    # 🚿 Higiene
    "ducha": E("in a steamy bathroom, wrapped in a fluffy towel, singing into a shampoo bottle like a microphone",
               ropa="a fluffy white bath towel"),
    "banarse": E("in a fluffy bathrobe sitting on the edge of a bathtub overflowing with bubbles",
                 "a couple in fluffy bathrobes sitting on the edge of a bathtub overflowing with bubbles, "
                 "playing with the foam and laughing", ropa="fluffy white bathrobes"),
    "dientes": E("brushing teeth in front of the bathroom mirror with a big foamy smile", "a couple brushing "
                 "their teeth side by side in front of the bathroom mirror, making funny faces",
                 ropa="pajamas"),
    # 🍽️ Comer
    "comer": E("eating a home-cooked meal at the dining table", "a couple eating a home-cooked meal together "
               "at the dining table, chatting"),
    "domicilio": E("eating delivery food from takeout boxes on the sofa", "a couple eating takeout food "
                   "(pizza and noodle boxes) together on the living-room sofa", ropa="comfy home clothes"),
    "picar": E("grabbing a snack from the open fridge in the kitchen, the fridge light on the face"),
    "taper": E("packing food into a lunchbox container in the kitchen"),
    "cocina": E("cooking {plato} in a cozy home kitchen, steam rising from the pan", "a couple cooking {plato} "
                "together in a cozy home kitchen, one stirring the pot and the other chopping vegetables",
                ropa="their clothes and a kitchen apron"),
    # 😴 Descanso
    "siesta": E("napping on the sofa under a soft blanket, peaceful", "a couple napping cuddled together on the "
                "sofa under a soft blanket", ropa="comfy home clothes"),
    "dormir": E("sleeping peacefully in bed under the covers, a cozy bedroom", "a couple sleeping cuddled "
                "together in bed under the covers, a cozy bedroom", ropa="pajamas"),
    # 💞 Pareja
    "hablar": E("a couple sitting face to face on the sofa, deep in a happy conversation"),
    "abrazar": E("a couple sharing a long, warm hug in the living room, eyes closed, smiling", romance=True),
    "besar": E("a couple kissing tenderly on the living-room sofa, eyes closed, one gently holding the other's "
               "face", romance=True),
    "masaje": E("a couple at home, one giving the other a relaxing shoulder massage on the sofa, scented "
                "candles, a calm atmosphere", ropa="comfy home clothes"),
    # 🧹 Limpieza
    "limpiar": E("cleaning the house with a broom in a sunny room", "a couple cleaning the house together, "
                 "one sweeping and the other mopping, having fun", ropa="old comfy clothes"),
    "lavar": E("hanging laundry on a clothesline in a small backyard, white sheets in the breeze",
               "a couple hanging laundry together on a clothesline in a small backyard, white sheets in the "
               "breeze", afuera=True),
    # 🐾 Mascota
    "pasear": E("walking {mascota} on a leash along a quiet neighborhood street with palm trees", "a couple "
                "walking {mascota} on a leash along a quiet neighborhood street with palm trees", afuera=True),
    "jugar_mascota": E("playing with {mascota} on the living-room floor with a ball", "a couple playing with "
                       "{mascota} on the living-room floor with a ball"),
    "banar_mascota": E("giving {mascota} a bath in a tub full of foam, the pet looks grumpy, water splashing",
                       "a couple giving {mascota} a bath in a tub full of foam, the pet looks grumpy, water "
                       "splashing everywhere"),
    "dar_comida": E("pouring food into the bowl of {mascota} in the kitchen, the pet waiting excitedly"),
    # 📱 Influencer y 📚 estudios
    "grabar": E("recording a video for social media with a phone on a tripod and a ring light, posing",
                "a couple recording a fun video for social media with a phone on a tripod and a ring light"),
    "editar": E("editing a video on a laptop at a desk, wearing headphones", "a couple editing a video together "
                "on a laptop at a desk"),
    "aprender_redes": E("watching a tutorial on a laptop and taking notes in a notebook"),
    "guion": E("writing a video script in a notebook at a desk, thinking with the pen on the lips"),
    "estudiar": E("studying at a desk full of books and notes", "a couple studying together at a desk full of "
                  "books, helping each other"),
    # 🔥 Momento íntimo: según el lugar de la casa
    "intimo_cuarto": E("a couple kissing in bed, cuddled up under the sheets, candles in the bedroom",
                       ropa="pajamas", intimo=True, romance=True),
    "intimo_bano": E("a couple hugging and kissing in a steamy bathroom, candles around the bathtub",
                     ropa="fluffy white bath towels", intimo=True, romance=True),
    "intimo_salon": E("a couple on the living-room sofa, one sitting on the other's lap, kissing deeply, hands "
                      "on each other's face and shoulders", ropa="comfy home clothes", intimo=True, romance=True),
    "intimo_cocina": E("a couple kissing against the kitchen counter, two glasses of wine nearby",
                       ropa="comfy home clothes", intimo=True, romance=True),
    "intimo_closet": E("a couple kissing and laughing among the hanging clothes of a walk-in closet",
                       intimo=True, romance=True),
    "intimo_extra": E("a couple slow dancing and kissing in a cozy spare room with fairy lights",
                      intimo=True, romance=True),
}

PLATOS = {
    "huevos": "scrambled eggs", "tostadas": "coffee and toast", "arroz_pollo": "Cuban chicken and rice",
    "pasta": "pasta with tomato sauce", "sopa": "a vegetable soup", "sandwich": "ham and cheese sandwiches",
    "panqueques": "pancakes", "bistec": "steak and fries", "batido": "a fruit smoothie",
    "pescado": "fish with vegetables",
}
MASCOTAS = {"perro": "dog", "gato": "cat"}
# Los colores en el mismo orden que mascota_juego.ASPECTOS.
COLORES_MASCOTA = ("brown", "black", "white", "orange", "gray", "spotted")

LUZ_AFUERA = {
    "manana": "early morning, soft golden sunlight, fresh air, pale blue sky",
    "tarde": "bright sunny afternoon, vivid blue sky with big fluffy white clouds",
    "atardecer": "sunset golden hour, orange and pink sky, long warm shadows",
    "noche": "night, deep blue starry sky with a crescent moon, warm glowing street lamps",
}
LUZ_ADENTRO = {
    "dia": "warm daylight streaming through the windows",
    "atardecer": "orange sunset light coming through the windows",
    "noche": "night, cozy warm lamp light inside, dark blue night sky outside the window",
}
ADENTRO = {"manana": "dia", "tarde": "dia", "atardecer": "atardecer", "noche": "noche"}

# --- rasgos de cada personaje (personaje.CAMPOS) en inglés ------------------------------------------
CAMPOS_FIGURA = ("genero", "etapa", "piel", "cuerpo", "estatura", "peinado", "pelo", "ojos", "estilo", "detalles")
PERSONA = {"mujer": ("woman", "her"), "hombre": ("man", "his"), "nobinario": ("androgynous person", "their")}
EDAD = {"joven": ("young", "twenties"), "adulta": ("", "forties"), "mayor": ("elderly", "sixties")}
PIEL = {"muy_clara": "very fair skin", "clara": "fair skin", "triguena": "light olive-brown skin",
        "morena": "brown skin", "oscura": "dark brown skin"}
CUERPO = {"delgada": "slim build", "promedio": "average build", "atletica": "athletic build",
          "musculosa": "muscular build", "curvas": "curvy figure", "robusta": "sturdy, heavyset build"}
ESTATURA = {"baja": "short", "media": "medium height", "alta": "tall"}
COLOR_PELO = {"negro": "black", "castano_oscuro": "dark brown", "castano_claro": "light brown",
              "rubio": "blonde", "rojizo": "bright red", "canoso": "gray", "rosa": "pink", "azul": "blue",
              "morado": "purple", "verde": "green"}
PEINADO = {"rapado": "buzz-cut {c} hair", "corto": "short {c} hair", "melena": "shoulder-length {c} hair",
           "largo": "long {c} hair", "rizado": "curly {c} hair", "afro": "voluminous {c} afro hair",
           "trenzas": "{c} hair in braids", "rastas": "{c} dreadlocks", "mono": "{c} hair tied up in a bun",
           "sin": "a shaved bald head"}
OJOS = {"marrones": "brown eyes", "negros": "dark eyes", "miel": "honey-amber eyes", "avellana": "hazel eyes",
        "verdes": "green eyes", "azules": "bright blue eyes", "grises": "gray eyes"}
ESTILO = {"casual": "casual clothes (t-shirt and jeans)", "elegante": "elegant clothes",
          "deportivo": "sporty clothes", "urbano": "streetwear", "rock": "rock style clothes and a leather jacket",
          "bohemio": "bohemian clothes", "clasico": "classic smart clothes", "playero": "light beach clothes"}
DETALLES = {"lentes": "glasses", "pecas": "freckles", "barba": "a beard", "bigote": "a mustache",
            "tatuajes": "tattoos on the arms", "piercings": "small piercings", "lunar": "a beauty mark",
            "hoyuelos": "dimples"}

ESTILO_SERIE = (
    "A frame from a Japanese anime TV series, in the hand-drawn style of Studio Ghibli films: soft cel shading, "
    "clean line art, a lush painted watercolor background, warm gentle colors and expressive anime faces."
)
ESTILO_ROMANCE = (
    "A close-up frame from a romance anime series, in a modern shoujo and webtoon style: clean line art, soft "
    "cel shading, warm colors, rosy blushing cheeks, sparkles and small floating hearts, a cozy blurred "
    "background, an intimate and tender mood."
)
FINAL = ("Landscape 3:2 image with the characters clearly visible and on-model. No text, no letters, no "
         "captions, no watermark, no speech bubbles.")


def figura(ap: dict) -> str:
    """El aspecto de un personaje en una clave corta: 'mujer,joven,clara,…,pecas+lentes'."""
    valores = [str(ap.get(c) or "") for c in CAMPOS_FIGURA[:-1]]
    return ",".join(valores + ["+".join(sorted(ap.get("detalles") or []))])


def clave(escena: str, momento: str, figuras: list[str]) -> str | None:
    """La clave de la imagen (o None si esa escena no tiene foto). Bajo techo, mañana y tarde son «dia»."""
    e = ESCENAS.get(escena.split(".")[0])
    if e is None or not figuras or momento not in ADENTRO:
        return None
    if not e.afuera:
        momento = ADENTRO[momento]
    return f"{escena}:{momento}:{'|'.join(sorted(figuras))}"


def es_intima(clave_imagen: str) -> bool:
    e = ESCENAS.get(clave_imagen.split(":")[0].split(".")[0])
    return e is not None and e.intimo


def _persona(codigo: str, ropa: str) -> str:
    """'a young woman in her twenties, fair skin, …, long bright red hair, bright blue eyes, wearing …'."""
    ap = dict(zip(CAMPOS_FIGURA, codigo.split(",")))
    quien, suyo = PERSONA.get(ap.get("genero", ""), ("person", "their"))
    edad, decada = EDAD.get(ap.get("etapa", ""), ("young", "twenties"))
    nombre = f"{edad} {quien}".strip()
    partes = [f"{'an' if nombre[0] in 'aeiou' else 'a'} {nombre} in {suyo} {decada}"]
    partes += [d[ap[c]] for c, d in (("piel", PIEL), ("cuerpo", CUERPO), ("estatura", ESTATURA)) if ap.get(c) in d]
    if ap.get("peinado") in PEINADO:
        partes.append(PEINADO[ap["peinado"]].format(c=COLOR_PELO.get(ap.get("pelo", ""), "dark")))
    elif ap.get("pelo") in COLOR_PELO:
        partes.append(f"{COLOR_PELO[ap['pelo']]} hair")
    if ap.get("ojos") in OJOS:
        partes.append(OJOS[ap["ojos"]])
    partes += [DETALLES[d] for d in ap.get("detalles", "").split("+") if d in DETALLES]
    partes.append(f"wearing {ropa or ESTILO.get(ap.get('estilo', ''), 'casual clothes')}")
    return ", ".join(partes)


def _mascota(detalle: list[str]) -> str:
    """'their orange cat' a partir de ["gato", "3"]."""
    animal = MASCOTAS.get(detalle[0] if detalle else "", "pet")
    color = int(detalle[1]) if len(detalle) > 1 and detalle[1].isdigit() else -1
    return f"their {COLORES_MASCOTA[color] + ' ' if 0 <= color < len(COLORES_MASCOTA) else ''}{animal}"


def prompt(clave_imagen: str) -> str:
    """La descripción en inglés que se le da a la IA para hacer la imagen."""
    partes = clave_imagen.split(":")
    if len(partes) != 3:
        raise ValueError(f"Clave de imagen no válida: {clave_imagen!r}")
    escena, momento, figuras = partes
    base, *detalle = escena.split(".")
    e = ESCENAS.get(base)
    luz = (LUZ_AFUERA if e and e.afuera else LUZ_ADENTRO).get(momento)
    codigos = [f for f in figuras.split("|") if f]
    if e is None or luz is None or not 1 <= len(codigos) <= 2:
        raise ValueError(f"Clave de imagen no válida: {clave_imagen!r}")
    que = e.juntos if len(codigos) == 2 and e.juntos else e.solo
    que = que.format(plato=PLATOS.get(detalle[0] if detalle else "", "a home-cooked meal"),
                     mascota=_mascota(detalle))
    if len(codigos) == 1:
        if not que.startswith(("a ", "an ")):
            que = f"the character {que}"
        quienes = f"The character: {_persona(codigos[0], e.ropa)}."
    else:
        quienes = (f"The two characters are a couple: (1) {_persona(codigos[0], e.ropa)}; "
                   f"(2) {_persona(codigos[1], e.ropa)}.")
    lineas = [ESTILO_ROMANCE if e.romance else ESTILO_SERIE, f"Scene: {que}.", f"Lighting: {luz}.", quienes]
    if e.intimo:
        lineas.append(INTIMO + ".")
    lineas.append(FINAL)
    return "\n".join(lineas)


def procesar(datos: bytes, clave_imagen: str) -> bytes:
    """La imagen de la IA lista para Telegram: 768×512, JPEG liviano y, si es íntima, pixelada abajo."""
    from PIL import Image  # solo aquí: armar las claves no necesita Pillow

    img = Image.open(io.BytesIO(datos)).convert("RGB")
    ancho, alto = img.size
    if ancho * ALTO > alto * ANCHO:  # más ancha que 3:2: se recortan los lados
        nuevo = alto * ANCHO // ALTO
        img = img.crop(((ancho - nuevo) // 2, 0, (ancho + nuevo) // 2, alto))
    elif ancho * ALTO < alto * ANCHO:  # más alta: se recorta arriba y abajo
        nuevo = ancho * ALTO // ANCHO
        img = img.crop((0, (alto - nuevo) // 2, ancho, (alto + nuevo) // 2))
    img = img.resize((ANCHO, ALTO), Image.LANCZOS)
    if es_intima(clave_imagen):
        _pixelar(img, (int(ANCHO * 0.12), int(ALTO * 0.62), int(ANCHO * 0.88), ALTO))
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True)
    return salida.getvalue()


def _pixelar(img, caja: tuple[int, int, int, int]) -> None:
    """Cuadritos grandes en esa zona de la imagen (como en la tele)."""
    from PIL import Image

    zona = img.crop(caja)
    w, h = zona.size
    zona = zona.resize((max(1, w // PIXEL), max(1, h // PIXEL)), Image.BILINEAR).resize((w, h), Image.NEAREST)
    img.paste(zona, caja[:2])
