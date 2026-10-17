"""Necesidades del Sim, acciones básicas y calendario.

Las necesidades van de 0 a 100 (la energía puede subir hasta 130 con constancia) y
cambian con el reloj de cada Sim, que solo corre mientras no está en pausa.
Todo aquí es lógica pura: no sabe nada de Telegram ni de la base de datos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MINUTO = 60
HORA = 3600
DIA = 86400

DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


# --- calendario: la hora local real de cada jugador ---------------------------------

def dia_semana(indice: int) -> str:
    """Nombre del día (0 = lunes … 6 = domingo)."""
    return DIAS_SEMANA[indice % 7]


def es_fin_de_semana(indice: int) -> bool:
    return indice % 7 >= 5


def hora_decimal(momento) -> float:
    return momento.hour + momento.minute / 60


def reloj_texto(momento, dia: int | None = None) -> str:
    """'Lunes 08:00 · día 1' a partir de la fecha y hora local."""
    texto = f"{dia_semana(momento.weekday())} {momento:%H:%M}"
    return f"{texto} · día {dia}" if dia is not None else texto


# --- necesidades ----------------------------------------------------------------

@dataclass(frozen=True)
class Necesidad:
    clave: str
    emoji: str
    nombre: str
    baja_por_hora: float


NECESIDADES = (
    Necesidad("hambre", "🍔", "Hambre", 6),
    Necesidad("energia", "⚡", "Energía", 3),  # así baja solo cuando el Sim no está haciendo nada
    Necesidad("higiene", "🚿", "Higiene", 4),
    Necesidad("diversion", "🎉", "Diversión", 5),
    Necesidad("social", "💬", "Social", 3),
)
POR_CLAVE_NECESIDAD = {n.clave: n for n in NECESIDADES}
INICIALES = {"hambre": 80, "energia": 90, "higiene": 80, "diversion": 70, "social": 60}

ENERGIA_MAX = 100
ENERGIA_TOPE = 130
SUBIDA_CONSTANCIA = 5
DIAS_CONSTANCIA = 3
ROJO = 25  # por debajo, la necesidad está "en rojo"
AMARILLO = 55
ALERTA = 15  # por debajo, se avisa al jugador
ROPA_LIMITE = 20  # prendas sucias a partir de las cuales no queda ropa limpia
SUCIO = 70  # suciedad de una zona a partir de la cual se nota


def nuevas_necesidades() -> dict:
    return dict(INICIALES)


def maximo(clave: str, energia_max: int) -> int:
    return energia_max if clave == "energia" else 100


def barra(valor: float, tope: int = 100) -> str:
    llenos = max(0, min(10, round(10 * valor / tope)))
    color = "🟩" if valor >= AMARILLO else "🟨" if valor > ROJO else "🟥"
    return color * llenos + "⬜" * (10 - llenos)


def en_rojo(nec: dict) -> list[str]:
    return [n.clave for n in NECESIDADES if nec.get(n.clave, 100) <= ROJO]


def de_mal_humor(nec: dict) -> bool:
    """Con alguna necesidad en 0, el Sim se pone de mal humor (y no podrá trabajar)."""
    return any(nec.get(n.clave, 100) < 1 for n in NECESIDADES)


def comida_del_momento(h: float) -> tuple[str, str, int]:
    """Según la hora local (en horas, p. ej. 13.5): (clave, nombre, cuánto quita el hambre)."""
    if 5 <= h < 11:
        return "desayuno", "Desayunar", 30
    if 11 <= h < 17:
        return "almuerzo", "Almorzar", 45
    return "cena", "Cenar", 40


# --- casa: zonas para limpiar --------------------------------------------------

# Las habitaciones de la casa; también son las zonas que se limpian.
ZONAS = {
    "salon": ("🛋️", "Sala-cocina-comedor"),
    "cuarto": ("🛏️", "Cuarto"),
    "bano": ("🚿", "Baño"),
    "closet": ("👗", "Clóset"),
    "extra": ("🧸", "Cuarto extra"),  # al mudarse a una casa más grande
}


HABITACION_INICIAL = "salon"


def nombre_habitacion(clave: str) -> str:
    if clave in ZONAS:
        emoji, nombre = ZONAS[clave]
        return f"{emoji} {nombre.lower() if clave != 'salon' else nombre}"
    return "📍 fuera de casa"


def estado_zona(suciedad: float) -> str:
    if suciedad < 30:
        return "✨ limpio"
    if suciedad < SUCIO:
        return "🫧 algo sucio"
    return "🪳 sucio"


# --- acciones ----------------------------------------------------------------------

SOLO, OPCIONAL, OBLIGATORIO = "solo", "opcional", "obligatorio"
FACTOR_JUNTOS = 0.7  # juntos terminan antes
BONO_SOCIAL_JUNTOS = 5
FUERA = "fuera"  # la acción se hace fuera de casa


@dataclass(frozen=True)
class Accion:
    clave: str
    emoji: str
    nombre: str
    verbo: str  # cómo se ve mientras la hace: "durmiendo"
    categoria: str
    minutos: int = 30
    efectos: dict = field(default_factory=dict)  # cambio total al completarla
    juntos: str = OPCIONAL
    nombre_juntos: str = ""
    nombre_solo: str = ""
    efectos_juntos: dict = field(default_factory=dict)  # reemplazan a `efectos` si la hacen juntos
    habitacion: str = ""  # dónde se hace: una habitación, FUERA o "" (en cualquier sitio)
    comida: bool = False  # quita el hambre según la comida del momento
    zona: str = ""  # zona de la casa que ensucia
    ensucia: int = 0
    ropa: int = 0  # prendas sucias que deja
    duerme: bool = False
    ejercicio: bool = False  # cuenta para la constancia
    necesita: str = ""  # necesidad que tiene que estar baja para hacerla

    def titulo(self, juntos: bool = False) -> str:
        if juntos and self.nombre_juntos:
            return self.nombre_juntos
        if not juntos and self.nombre_solo:
            return self.nombre_solo
        return self.nombre


# Submenús de ⚡ Acciones y de 📍 Lugares.
CATEGORIAS = (
    ("comer", "🍽️", "Comer"),
    ("higiene", "🚿", "Higiene"),
    ("descanso", "😴", "Descanso"),
    ("diversion", "🎉", "Diversión"),
    ("pareja", "💞", "Pareja"),
    ("limpieza", "🧹", "Limpieza"),
)
LUGARES = (
    ("super", "🛒", "Súper"),
    ("restaurante", "🍝", "Restaurante"),
    ("cine", "🎬", "Cine"),
    ("parque", "🌳", "Parque"),
    ("gimnasio", "🏋️", "Gimnasio"),
)

_ACCIONES = (
    # 🍽️ Comer
    Accion("comer", "🍽️", "Comer lo que hay", "comiendo", "comer", 30, comida=True, habitacion="salon",
           zona="salon", ensucia=5, nombre_juntos="Comer juntos", necesita="hambre"),
    # Cocinar es un minijuego por pasos; la duración real la marca la receta.
    Accion("cocinar", "🍳", "Preparar comida", "cocinando", "comer", 30, {"energia": -5}, habitacion="salon",
           zona="salon", ensucia=15, nombre_juntos="Cocinar juntos"),
    Accion("domicilio", "🛵", "Pedir a domicilio", "esperando el pedido y comiendo", "comer", 30, comida=True,
           habitacion="salon", zona="salon", ensucia=3, nombre_juntos="Pedir a domicilio para dos",
           necesita="hambre"),
    Accion("taper", "🥡", "Preparar un táper", "preparando un táper", "comer", 5, juntos=SOLO, habitacion="salon"),
    Accion("picar", "🍎", "Picar algo", "picando algo", "comer", 10, {"hambre": 10}, juntos=SOLO,
           habitacion="salon", necesita="hambre"),
    # 🚿 Higiene
    Accion("ducha", "🚿", "Ducharse", "duchándose", "higiene", 15, {"higiene": 60}, juntos=SOLO,
           habitacion="bano", zona="bano", ensucia=8, ropa=2, necesita="higiene"),
    Accion("banarse", "🛁", "Bañarse juntos", "bañándose", "higiene", 30, {"higiene": 80, "social": 10},
           juntos=OBLIGATORIO, habitacion="bano", zona="bano", ensucia=10, ropa=2, necesita="higiene"),
    Accion("dientes", "🪥", "Lavarse los dientes", "lavándose los dientes", "higiene", 5, {"higiene": 10},
           habitacion="bano", zona="bano", ensucia=2, nombre_juntos="Lavarse los dientes juntos"),
    # 😴 Descanso
    Accion("dormir", "😴", "Dormir", "durmiendo", "descanso", 8 * 60, habitacion="cuarto", zona="cuarto",
           ensucia=3, duerme=True, nombre_juntos="Dormir juntos", necesita="energia"),
    Accion("siesta", "💤", "Echar una siesta", "echando una siesta", "descanso", 60, {"energia": 15},
           habitacion="cuarto", duerme=True, nombre_juntos="Siesta juntos", necesita="energia"),
    # 🎉 Diversión (en pareja, compartir rinde más: +15 de social por hora)
    Accion("tele", "📺", "Ver la tele", "viendo la tele", "diversion", 60, {"diversion": 15, "social": 3},
           habitacion="salon", zona="salon", ensucia=2, nombre_juntos="Ver la tele juntos",
           efectos_juntos={"social": 15}),
    Accion("redes", "📱", "Ver redes o videos", "viendo redes", "diversion", 60, {"diversion": 10, "social": 5},
           nombre_juntos="Ver videos juntos", efectos_juntos={"social": 15}),
    Accion("telefono", "📞", "Hablar por teléfono", "hablando por teléfono", "diversion", 20, {"social": 20},
           juntos=SOLO, nombre_solo="Llamar a un amigo o a la familia"),
    # 💞 Pareja
    Accion("hablar", "💬", "Hablar", "hablando", "pareja", 15, {"social": 10}, juntos=OBLIGATORIO),
    Accion("abrazar", "🤗", "Abrazar", "abrazándose", "pareja", 5, {"social": 15}, juntos=OBLIGATORIO),
    Accion("besar", "💋", "Besar", "besándose", "pareja", 5, {"social": 10, "diversion": 5}, juntos=OBLIGATORIO),
    Accion("masaje", "💆", "Darse un masaje", "dándose un masaje", "pareja", 20,
           {"social": 10, "energia": 5, "diversion": 5}, juntos=OBLIGATORIO),
    # 🧹 Limpieza
    Accion("limpiar", "🧹", "Limpiar una zona", "limpiando", "limpieza", 30, {"energia": -10},
           nombre_juntos="Limpiar juntos"),
    Accion("lavar", "🧺", "Lavar la ropa", "lavando la ropa", "limpieza", 60, {"energia": -5},
           habitacion="bano", nombre_juntos="Lavar la ropa juntos"),
    # 📍 Lugares (fuera de casa; en pareja, una salida cuenta como cita)
    Accion("super", "🛒", "Hacer el súper", "en el súper", "super", 45, {"energia": -5},
           habitacion=FUERA, nombre_juntos="Ir al súper juntos"),
    Accion("restaurante", "🍝", "Ir al restaurante", "en el restaurante", "restaurante", 90,
           {"diversion": 20, "social": 5}, comida=True, habitacion=FUERA, nombre_juntos="Cita en el restaurante",
           efectos_juntos={"social": 50}),
    Accion("cine", "🎬", "Ir al cine", "en el cine", "cine", 120, {"diversion": 40, "social": 5},
           habitacion=FUERA, nombre_juntos="Cita en el cine", efectos_juntos={"social": 50}),
    Accion("parque", "🌳", "Pasear por el parque", "en el parque", "parque", 60,
           {"diversion": 20, "energia": -10, "social": 5}, habitacion=FUERA, ropa=1, ejercicio=True,
           nombre_juntos="Paseo juntos por el parque", efectos_juntos={"social": 30}),
    Accion("gimnasio", "🏋️", "Entrenar en el gimnasio", "en el gimnasio", "gimnasio", 60,
           {"energia": -25, "diversion": 5, "higiene": -15}, habitacion=FUERA, ropa=2, ejercicio=True,
           nombre_juntos="Entrenar juntos"),
    # Se empieza desde la pantalla de trabajo, no desde los menús de acciones.
    Accion("trabajar", "💼", "Trabajar", "trabajando", "trabajo", 8 * 60, juntos=SOLO, habitacion=FUERA, ropa=1),
)
ACCIONES: dict[str, Accion] = {a.clave: a for a in _ACCIONES}


def texto_efectos(efectos: dict) -> str:
    """'+10 🎉 diversión, +5 💬 social'."""
    partes = []
    for n in NECESIDADES:
        cambio = round(efectos.get(n.clave, 0))
        if cambio:
            partes.append(f"{'+' if cambio > 0 else '−'}{abs(cambio)} {n.emoji} {n.nombre.lower()}")
    return ", ".join(partes) or "sin cambios en las necesidades"


ENERGIA_POR_HORA_DORMIDO = 12
ENERGIA_TRABAJO_POR_HORA = 8
HORAS_DESMAYO = 6  # si la energía llega a 0, se duerme donde esté


def horas_para_descansar(energia: float, energia_max: int) -> int:
    return max(1, min(12, math.ceil((energia_max - energia) / ENERGIA_POR_HORA_DORMIDO)))


def preparar(
    a: Accion, segundos: float, nec: dict, energia_max: int, extra: str = "", juntos: bool = False,
    hora: float = 8.0,
) -> dict:
    """La acción tal como va a hacerse: duración y efectos totales, en segundos del reloj del Sim.

    `hora` es la hora local (decide si la comida es desayuno, almuerzo o cena).
    """
    minutos = a.minutos
    efectos = dict(a.efectos)
    if a.clave == "dormir":
        horas = (
            horas_para_descansar(nec.get("energia", 0), energia_max)
            if extra in ("", "max") else max(1, min(12, int(extra)))
        )
        minutos = horas * 60
        efectos["energia"] = ENERGIA_POR_HORA_DORMIDO * horas
    if a.clave == "trabajar":
        horas = max(1, min(12, int(extra or 8)))
        minutos = horas * 60
        efectos["energia"] = -ENERGIA_TRABAJO_POR_HORA * horas
    if a.comida:
        efectos["hambre"] = efectos.get("hambre", 0) + comida_del_momento(hora)[2]
    if juntos:
        minutos = max(1, round(minutos * FACTOR_JUNTOS))
        if a.efectos_juntos:
            efectos.update(a.efectos_juntos)
        elif a.categoria != "pareja":
            efectos["social"] = efectos.get("social", 0) + BONO_SOCIAL_JUNTOS
    return {
        "k": a.clave, "x": extra, "ini": segundos, "fin": segundos + minutos * MINUTO,
        "ef": efectos, "duerme": a.duerme,
    }


def no_hace_falta(a: Accion, nec: dict, energia_max: int) -> str | None:
    """Motivo para no dejar hacer una acción que no se necesita (p. ej. dormir con la energía llena)."""
    if not a.necesita:
        return None
    tope = maximo(a.necesita, energia_max)
    if nec.get(a.necesita, 0) >= tope - 5:
        nombre = POR_CLAVE_NECESIDAD[a.necesita].nombre.lower()
        return f"Tu Sim no lo necesita ahora: tiene la {nombre} casi al máximo."
    return None


def avanzar(nec: dict, desde: float, hasta: float, accion: dict | None, energia_max: int,
            multiplicadores: dict | None = None) -> bool:
    """Aplica el paso del tiempo del Sim entre `desde` y `hasta` (segundos de su reloj).

    La acción en curso suma sus efectos en proporción a lo hecho; las necesidades bajan
    por hora (la energía solo cuando no hace nada). Devuelve True si la acción terminó.
    """
    if hasta <= desde:
        return bool(accion) and hasta >= accion["fin"]
    multiplicadores = multiplicadores or {}
    horas = (hasta - desde) / HORA
    horas_ocupado = 0.0
    if accion:
        ini, fin = accion["ini"], accion["fin"]
        a0, a1 = max(desde, ini), min(hasta, fin)
        if a1 > a0 and fin > ini:
            fraccion = (a1 - a0) / (fin - ini)
            for clave, cambio in accion["ef"].items():
                nec[clave] = nec.get(clave, 0) + cambio * fraccion
            horas_ocupado = (a1 - a0) / HORA
    extra_accion = (accion or {}).get("mult", {})  # p. ej. más hambre trabajando sin táper
    for n in NECESIDADES:
        if n.clave == "energia":
            baja = n.baja_por_hora * max(0.0, horas - horas_ocupado)
        else:
            horas_efectivas = horas + horas_ocupado * (extra_accion.get(n.clave, 1.0) - 1)
            baja = n.baja_por_hora * horas_efectivas * multiplicadores.get(n.clave, 1.0)
        nec[n.clave] = max(0.0, min(maximo(n.clave, energia_max), nec.get(n.clave, 0) - baja))
    return bool(accion) and hasta >= accion["fin"]


def registrar_ejercicio(racha: dict, dia: int, energia_max: int) -> tuple[dict, int, bool]:
    """Cuenta días seguidos de ejercicio. Cada 3 días, la energía máxima sube 5 (hasta 130)."""
    if racha.get("ultimo") == dia:
        return racha, energia_max, False
    dias = racha.get("dias", 0) + 1 if racha.get("ultimo") == dia - 1 else 1
    racha = {"ultimo": dia, "dias": dias}
    if dias % DIAS_CONSTANCIA == 0 and energia_max < ENERGIA_TOPE:
        return racha, min(ENERGIA_TOPE, energia_max + SUBIDA_CONSTANCIA), True
    return racha, energia_max, False
