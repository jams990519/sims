"""Creador de personajes: aspecto, personalidad, aspiración y estado de ánimo.

También genera el avatar en emoji y la descripción en texto de cada personaje.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Opcion:
    clave: str
    emoji: str
    nombre: str  # forma masculina o invariable
    fem: str | None = None  # forma femenina, si cambia
    neutro: str | None = None  # forma para personajes no binarios, si cambia
    color: str = ""  # color de los estados de ánimo
    frase: str = ""  # frase de las aspiraciones

    def texto(self, genero: str | None = None) -> str:
        if genero == "mujer" and self.fem:
            return self.fem
        if genero == "nobinario" and self.neutro:
            return self.neutro
        return self.nombre

    def boton(self, genero: str | None = None) -> str:
        return f"{self.color + ' ' if self.color else ''}{self.emoji} {self.texto(genero)}"


@dataclass(frozen=True)
class Campo:
    clave: str
    emoji: str
    titulo: str
    pregunta: str
    opciones: tuple[Opcion, ...]
    seccion: str = "Aspecto"
    multiple: bool = False
    minimo: int = 0
    maximo: int = 0  # 0 = sin límite

    def opcion(self, clave: str | None) -> Opcion | None:
        return next((o for o in self.opciones if o.clave == clave), None)


def _ops(*filas: tuple) -> tuple[Opcion, ...]:
    return tuple(Opcion(*f) for f in filas)


ASPECTO = "Aspecto"
PERSONALIDAD = "Personalidad"

CAMPOS: tuple[Campo, ...] = (
    Campo("genero", "🚻", "Género", "¿Cuál es el género de tu personaje?", _ops(
        ("mujer", "👩", "Mujer"),
        ("hombre", "👨", "Hombre"),
        ("nobinario", "🧑", "No binario"),
    )),
    Campo("etapa", "🎂", "Edad", "¿En qué etapa de la vida está?", _ops(
        ("joven", "🌱", "Juventud (18-30)"),
        ("adulta", "🌳", "Adultez (30-55)"),
        ("mayor", "🍂", "Mayor (55+)"),
    )),
    Campo("piel", "🎨", "Piel", "Elige el tono de piel:", _ops(
        ("muy_clara", "👋🏻", "Muy clara"),
        ("clara", "👋🏼", "Clara"),
        ("triguena", "👋🏽", "Trigueña"),
        ("morena", "👋🏾", "Morena"),
        ("oscura", "👋🏿", "Oscura"),
    )),
    Campo("cuerpo", "🧍", "Cuerpo", "¿Qué forma de cuerpo tiene?", _ops(
        ("delgada", "🌾", "Delgada"),
        ("promedio", "🧍", "Promedio"),
        ("atletica", "🏃", "Atlética"),
        ("musculosa", "💪", "Musculosa"),
        ("curvas", "⌛", "Con curvas"),
        ("robusta", "🛡️", "Robusta"),
    )),
    Campo("estatura", "📏", "Estatura", "¿Qué estatura tiene?", _ops(
        ("baja", "🔽", "Baja"),
        ("media", "↕️", "Media"),
        ("alta", "🔼", "Alta"),
    )),
    Campo("peinado", "💇", "Peinado", "Elige el peinado:", _ops(
        ("rapado", "💈", "Rapado"),
        ("corto", "✂️", "Corto"),
        ("melena", "💇", "Media melena"),
        ("largo", "💁", "Largo"),
        ("rizado", "🌀", "Rizado"),
        ("afro", "☁️", "Afro"),
        ("trenzas", "🪢", "Trenzas"),
        ("rastas", "🧶", "Rastas"),
        ("mono", "🎀", "Moño"),
        ("sin", "🥚", "Sin pelo"),
    )),
    Campo("pelo", "🖌️", "Color de pelo", "¿De qué color es el pelo?", _ops(
        ("negro", "⚫", "Negro"),
        ("castano_oscuro", "🟤", "Castaño oscuro"),
        ("castano_claro", "🟫", "Castaño claro"),
        ("rubio", "🟡", "Rubio"),
        ("rojizo", "🟠", "Rojizo"),
        ("canoso", "⚪", "Canoso"),
        ("rosa", "🌸", "Rosa"),
        ("azul", "🔵", "Azul"),
        ("morado", "🟣", "Morado"),
        ("verde", "🟢", "Verde"),
    )),
    Campo("ojos", "👁️", "Ojos", "¿De qué color son los ojos?", _ops(
        ("marrones", "🟤", "Marrones"),
        ("negros", "⚫", "Negros"),
        ("miel", "🍯", "Miel"),
        ("avellana", "🌰", "Avellana"),
        ("verdes", "🟢", "Verdes"),
        ("azules", "🔵", "Azules"),
        ("grises", "🔘", "Grises"),
    )),
    Campo("detalles", "✨", "Detalles", "Toca los detalles que quieras (varios o ninguno):", _ops(
        ("lentes", "👓", "Lentes"),
        ("pecas", "✨", "Pecas"),
        ("barba", "🧔", "Barba"),
        ("bigote", "🥸", "Bigote"),
        ("tatuajes", "🐉", "Tatuajes"),
        ("piercings", "💎", "Piercings"),
        ("lunar", "🔹", "Lunar"),
        ("hoyuelos", "😊", "Hoyuelos"),
    ), multiple=True),
    Campo("estilo", "👕", "Estilo", "¿Cómo le gusta vestir?", _ops(
        ("casual", "👕", "Casual"),
        ("elegante", "👔", "Elegante"),
        ("deportivo", "👟", "Deportivo"),
        ("urbano", "🧢", "Urbano"),
        ("rock", "🎸", "Rock"),
        ("bohemio", "🌻", "Bohemio"),
        ("clasico", "🧥", "Clásico"),
        ("playero", "🩴", "Playero"),
    )),
    Campo("rasgos", "🧠", "Rasgos", "Elige hasta 3 rasgos de personalidad:", _ops(
        ("romantico", "💘", "Romántico", "Romántica", "Alma romántica"),
        ("divertido", "😂", "Divertido", "Divertida", "Alma divertida"),
        ("alegre", "😄", "Alegre"),
        ("ordenado", "🧹", "Ordenado", "Ordenada", "Amante del orden"),
        ("desordenado", "🌪️", "Desordenado", "Desordenada", "Espíritu caótico"),
        ("activo", "⚡", "Activo", "Activa", "Pura energía"),
        ("perezoso", "🦥", "Perezoso", "Perezosa", "Amante del sofá"),
        ("gloton", "🍔", "Glotón", "Glotona", "Buen diente"),
        ("cocinillas", "🍳", "Cocinillas"),
        ("creativo", "🎨", "Creativo", "Creativa", "Mente creativa"),
        ("cerebrito", "🤓", "Cerebrito"),
        ("sociable", "🗣️", "Sociable"),
        ("timido", "🙈", "Tímido", "Tímida", "Alma tímida"),
        ("detallista", "🎁", "Detallista"),
        ("celoso", "😒", "Celoso", "Celosa", "Corazón celoso"),
        ("grunon", "😤", "Gruñón", "Gruñona", "Mal genio"),
    ), seccion=PERSONALIDAD, multiple=True, minimo=1, maximo=3),
    Campo("aspiracion", "🌟", "Aspiración", "¿Cuál es su gran sueño en la vida?", (
        Opcion("amor", "💞", "Amor eterno", frase="Sueña con un amor para toda la vida."),
        Opcion("familia", "🏡", "Gran familia", frase="Sueña con formar una familia grande."),
        Opcion("fortuna", "💰", "Fortuna", frase="Sueña con tener mucho dinero."),
        Opcion("hogar", "🛋️", "Hogar de ensueño", frase="Sueña con tener la casa perfecta."),
        Opcion("chef", "🍽️", "Maestría culinaria", frase="Sueña con cocinar como en un gran restaurante."),
        Opcion("arte", "🎭", "Arte y fama", frase="Sueña con que el mundo conozca su arte."),
        Opcion("saber", "📚", "Conocimiento", frase="Sueña con saber de todo."),
        Opcion("social", "🎉", "Vida social", frase="Sueña con tener amistades por todas partes."),
        Opcion("deporte", "🏆", "Cuerpo de atleta", frase="Sueña con estar en plena forma."),
    ), seccion=PERSONALIDAD),
    Campo("animo", "🎭", "Ánimo", "¿Cómo se siente ahora mismo?", _ops(
        ("feliz", "😊", "Feliz", None, None, "🟢"),
        ("coqueto", "😏", "Coqueto", "Coqueta", "Con ganas de coquetear", "🌸"),
        ("triste", "😢", "Triste", None, None, "🔵"),
        ("enojado", "😠", "Enojado", "Enojada", "Con enojo", "🔴"),
        ("energia", "⚡", "Con energía", None, None, "🟡"),
        ("cansado", "😴", "Cansado", "Cansada", "Con sueño", "🔘"),
        ("inspirado", "✨", "Inspirado", "Inspirada", "Con inspiración", "🟣"),
    ), seccion=PERSONALIDAD),
)

POR_CLAVE: dict[str, Campo] = {c.clave: c for c in CAMPOS}
SIN_PELO = "sin"
ANIMO = POR_CLAVE["animo"]


def campos_visibles(ap: dict) -> list[Campo]:
    """Campos que aplican a este personaje (sin pelo no hay color de pelo)."""
    return [c for c in CAMPOS if not (c.clave == "pelo" and ap.get("peinado") == SIN_PELO)]


def siguiente_campo(ap: dict) -> Campo | None:
    return next((c for c in campos_visibles(ap) if c.clave not in ap), None)


def completa(ap: dict) -> bool:
    return siguiente_campo(ap) is None


def elegir(ap: dict, campo: str, valor: str) -> bool:
    """Guarda una opción de un campo simple. Devuelve False si no es válida."""
    c = POR_CLAVE.get(campo)
    if c is None or c.multiple or c.opcion(valor) is None:
        return False
    ap[campo] = valor
    if campo == "peinado" and valor == SIN_PELO:
        ap.pop("pelo", None)
    return True


def alternar(campo: Campo, seleccion: list[str], valor: str) -> tuple[list[str], str | None]:
    """Marca o desmarca una opción de un campo múltiple. Devuelve la selección y un aviso si no se pudo."""
    if campo.opcion(valor) is None:
        return seleccion, None
    if valor in seleccion:
        return [s for s in seleccion if s != valor], None
    if campo.maximo and len(seleccion) >= campo.maximo:
        return seleccion, f"Puedes elegir como máximo {campo.maximo}. Quita uno primero."
    return seleccion + [valor], None


def al_azar(campo: Campo, rng: random.Random) -> str | list[str]:
    if campo.multiple:
        cuantos = campo.maximo if campo.minimo else rng.randint(0, 2)
        return [o.clave for o in rng.sample(campo.opciones, cuantos)]
    return rng.choice(campo.opciones).clave


def todo_al_azar(rng: random.Random) -> dict:
    ap: dict = {}
    for c in CAMPOS:
        if c.clave == "pelo" and ap.get("peinado") == SIN_PELO:
            continue
        ap[c.clave] = al_azar(c, rng)
    return ap


def etiqueta(ap: dict, campo: str) -> str:
    """Texto legible del valor elegido, p. ej. '🟡 Rubio' o 'Lentes, Pecas'."""
    c = POR_CLAVE[campo]
    valor = ap.get(campo)
    genero = ap.get("genero")
    if c.multiple:
        nombres = [o.texto(genero) for o in c.opciones if o.clave in (valor or [])]
        return ", ".join(nombres) if nombres else "Ninguno"
    o = c.opcion(valor) if isinstance(valor, str) else None
    return o.boton(genero) if o else "—"


def animo(ap: dict) -> str:
    """Estado de ánimo con su color, p. ej. '🌸 😏 Coqueta'."""
    o = ANIMO.opcion(ap.get("animo"))
    return o.boton(ap.get("genero")) if o else ""


def color_animo(ap: dict) -> str:
    """Solo el color del ánimo, p. ej. '🌸' ('' si no eligió ninguno)."""
    o = ANIMO.opcion(ap.get("animo"))
    return o.color if o else ""


# --- avatar en emoji --------------------------------------------------------

_TONOS = {
    "muy_clara": "\U0001F3FB",
    "clara": "\U0001F3FC",
    "triguena": "\U0001F3FD",
    "morena": "\U0001F3FE",
    "oscura": "\U0001F3FF",
}
_ZWJ = "‍"
_FEM = _ZWJ + "♀️"
_MASC = _ZWJ + "♂️"


def avatar(ap: dict) -> str:
    """Emoji que se parece al personaje (género, tono de piel, pelo y barba)."""
    g = ap.get("genero")
    tono = _TONOS.get(ap.get("piel", ""), "")
    sufijo = {"mujer": _FEM, "hombre": _MASC}.get(g, "")
    if ap.get("etapa") == "mayor":
        return {"mujer": "👵", "hombre": "👴"}.get(g, "🧓") + tono
    if "barba" in (ap.get("detalles") or []):
        return "\U0001F9D4" + tono + sufijo
    base = {"mujer": "\U0001F469", "hombre": "\U0001F468"}.get(g, "\U0001F9D1")
    peinado, pelo = ap.get("peinado"), ap.get("pelo")
    if peinado == SIN_PELO:
        return base + tono + _ZWJ + "\U0001F9B2"
    if peinado in ("rizado", "afro"):
        return base + tono + _ZWJ + "\U0001F9B1"
    if pelo == "rojizo":
        return base + tono + _ZWJ + "\U0001F9B0"
    if pelo == "canoso":
        return base + tono + _ZWJ + "\U0001F9B3"
    if pelo == "rubio":
        return "\U0001F471" + tono + sufijo
    return base + tono


# --- descripción en texto ---------------------------------------------------

_SUJETO = {"mujer": "una mujer", "hombre": "un hombre", "nobinario": "una persona"}
_EDAD = {
    "joven": {"mujer": "joven", "hombre": "joven", "nobinario": "joven"},
    "adulta": {"mujer": "adulta", "hombre": "adulto", "nobinario": "adulta"},
    "mayor": {"mujer": "mayor", "hombre": "mayor", "nobinario": "mayor"},
}
_CUERPO = {
    "delgada": "de complexión delgada", "promedio": "de complexión promedio",
    "atletica": "de complexión atlética", "musculosa": "de complexión musculosa",
    "curvas": "de cuerpo curvilíneo", "robusta": "de complexión robusta",
}
_PIEL = {
    "muy_clara": "muy clara", "clara": "clara", "triguena": "trigueña",
    "morena": "morena", "oscura": "oscura",
}
_PEINADO = {
    "rapado": "el pelo rapado", "corto": "el pelo corto", "melena": "media melena",
    "largo": "el pelo largo", "rizado": "el pelo rizado", "afro": "un afro",
    "trenzas": "trenzas", "rastas": "rastas", "mono": "un moño",
}
_COLOR = {
    "negro": "negro", "castano_oscuro": "castaño oscuro", "castano_claro": "castaño claro",
    "rubio": "rubio", "rojizo": "rojizo", "canoso": "canoso", "rosa": "rosa",
    "azul": "azul", "morado": "morado", "verde": "verde",
}
_OJOS = {
    "marrones": "ojos marrones", "negros": "ojos negros", "miel": "ojos color miel",
    "avellana": "ojos color avellana", "verdes": "ojos verdes", "azules": "ojos azules",
    "grises": "ojos grises",
}
_ESTILO = {
    "casual": "casual", "elegante": "elegante", "deportivo": "deportivo", "urbano": "urbano",
    "rock": "rock", "bohemio": "bohemio", "clasico": "clásico", "playero": "playero",
}
_DETALLE = {
    "lentes": "usa lentes", "pecas": "tiene pecas", "barba": "tiene barba",
    "bigote": "tiene bigote", "tatuajes": "tiene tatuajes", "piercings": "lleva piercings",
    "lunar": "tiene un lunar", "hoyuelos": "tiene hoyuelos",
}


def _unir(partes: list[str]) -> str:
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def descripcion(nombre: str, ap: dict) -> str:
    g = ap.get("genero", "nobinario")
    frases = []
    edad = _EDAD.get(ap.get("etapa", ""), {}).get(g, "")
    frases.append(
        f"{nombre} es {_SUJETO.get(g, 'una persona')} {edad} "
        f"{_CUERPO.get(ap.get('cuerpo', ''), 'de complexión promedio')} "
        f"y estatura {ap.get('estatura', 'media')}."
    )
    frases.append(
        f"Tiene la piel {_PIEL.get(ap.get('piel', ''), 'trigueña')} "
        f"y {_OJOS.get(ap.get('ojos', ''), 'ojos marrones')}."
    )
    if ap.get("peinado") == SIN_PELO:
        frases.append("No tiene pelo.")
    else:
        frases.append(
            f"Lleva {_PEINADO.get(ap.get('peinado', ''), 'el pelo')} "
            f"de color {_COLOR.get(ap.get('pelo', ''), 'castaño')}."
        )
    detalles = [_DETALLE[d] for d in ap.get("detalles") or [] if d in _DETALLE]
    if detalles:
        frases.append(f"Además, {_unir(detalles)}.")
    if ap.get("estilo") in _ESTILO:
        frases.append(f"Viste con estilo {_ESTILO[ap['estilo']]}.")
    rasgos = [o.texto(g).lower() for o in POR_CLAVE["rasgos"].opciones if o.clave in (ap.get("rasgos") or [])]
    if rasgos:
        if g == "nobinario":
            frases.append(f"Su personalidad: {_unir(rasgos)}.")
        else:
            frases.append(f"Es {_unir(rasgos)}.")
    aspiracion = POR_CLAVE["aspiracion"].opcion(ap.get("aspiracion"))
    if aspiracion:
        frases.append(aspiracion.frase)
    estado = ANIMO.opcion(ap.get("animo"))
    if estado:
        frases.append(f"Ahora mismo se siente {estado.texto(g).lower()} {estado.color}.")
    return " ".join(frases)
