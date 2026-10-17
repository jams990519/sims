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
HORA_INICIAL = 8 * HORA  # el día 1 empieza un lunes a las 08:00

DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


# --- calendario ---------------------------------------------------------------

def dia_de_juego(segundos: float) -> int:
    return 1 + int((HORA_INICIAL + segundos) // DIA)


def hora_del_dia(segundos: float) -> float:
    return ((HORA_INICIAL + segundos) % DIA) / HORA


def dia_semana(dia: int) -> str:
    return DIAS_SEMANA[(dia - 1) % 7]


def es_fin_de_semana(dia: int) -> bool:
    return (dia - 1) % 7 >= 5


def hora_texto(segundos: float) -> str:
    s = int(HORA_INICIAL + segundos) % DIA
    return f"{s // HORA:02d}:{s % HORA // MINUTO:02d}"


def reloj_texto(segundos: float) -> str:
    """'Lunes 08:00 · día 1'."""
    dia = dia_de_juego(segundos)
    return f"{dia_semana(dia)} {hora_texto(segundos)} · día {dia}"


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


def comida_del_momento(segundos: float) -> tuple[str, str, int]:
    """Según la hora del Sim: (clave, nombre, cuánto quita el hambre)."""
    h = hora_del_dia(segundos)
    if 5 <= h < 11:
        return "desayuno", "Desayunar", 30
    if 11 <= h < 17:
        return "almuerzo", "Almorzar", 45
    return "cena", "Cenar", 40


# --- casa: zonas para limpiar --------------------------------------------------

ZONAS = {
    "salon": ("🛋️", "Sala-cocina-comedor"),
    "cuarto": ("🛏️", "Cuarto"),
    "bano": ("🚿", "Baño"),
    "closet": ("👗", "Clóset"),
}


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


CATEGORIAS = (
    ("comer", "🍽️", "Comer"),
    ("descansar", "😴", "Descansar"),
    ("higiene", "🚿", "Higiene"),
    ("diversion", "🎉", "Diversión"),
    ("social", "💬", "Social"),
    ("casa", "🧹", "Casa"),
)

_ACCIONES = (
    Accion("comer", "🍽️", "Comer", "comiendo", "comer", 30, comida=True, zona="salon", ensucia=5,
           nombre_juntos="Comer juntos", necesita="hambre"),
    Accion("cocinar", "🍳", "Cocinar y comer", "cocinando", "comer", 60, {"energia": -5, "hambre": 10},
           comida=True, zona="salon", ensucia=15, nombre_juntos="Cocinar juntos", necesita="hambre"),
    Accion("picar", "🍎", "Picar algo", "picando algo", "comer", 10, {"hambre": 10}, juntos=SOLO,
           necesita="hambre"),
    Accion("dormir", "😴", "Dormir", "durmiendo", "descansar", 8 * 60, zona="cuarto", ensucia=3,
           duerme=True, nombre_juntos="Dormir juntos", necesita="energia"),
    Accion("siesta", "💤", "Echar una siesta", "echando una siesta", "descansar", 60, {"energia": 15},
           zona="salon", duerme=True, nombre_juntos="Siesta juntos", necesita="energia"),
    Accion("ducha", "🚿", "Ducharse", "duchándose", "higiene", 15, {"higiene": 60}, juntos=SOLO,
           zona="bano", ensucia=8, ropa=2, necesita="higiene"),
    Accion("banarse", "🛁", "Bañarse juntos", "bañándose", "higiene", 30, {"higiene": 80, "social": 10},
           juntos=OBLIGATORIO, zona="bano", ensucia=10, ropa=2, necesita="higiene"),
    Accion("dientes", "🪥", "Lavarse los dientes", "lavándose los dientes", "higiene", 5, {"higiene": 10},
           zona="bano", ensucia=2, nombre_juntos="Lavarse los dientes juntos"),
    Accion("tele", "📺", "Ver la tele", "viendo la tele", "diversion", 60, {"diversion": 15},
           zona="salon", ensucia=2, nombre_juntos="Ver la tele juntos"),
    Accion("redes", "📱", "Ver redes o videos", "viendo videos", "diversion", 60, {"diversion": 10},
           nombre_juntos="Ver videos juntos"),
    Accion("parque", "🌳", "Ir al parque", "en el parque", "diversion", 60,
           {"diversion": 20, "energia": -10, "social": 5}, ropa=1, ejercicio=True,
           nombre_juntos="Ir al parque juntos"),
    Accion("hablar", "💬", "Hablar", "hablando", "social", 15, {"social": 10},
           nombre_solo="Llamar a alguien por teléfono", nombre_juntos="Hablar juntos"),
    Accion("abrazar", "🤗", "Abrazar", "abrazándose", "social", 5, {"social": 15}, juntos=OBLIGATORIO),
    Accion("besar", "💋", "Besar", "besándose", "social", 5, {"social": 10, "diversion": 5}, juntos=OBLIGATORIO),
    Accion("masaje", "💆", "Darse un masaje", "dándose un masaje", "social", 20,
           {"social": 10, "energia": 5, "diversion": 5}, juntos=OBLIGATORIO),
    Accion("cita", "🌹", "Tener una cita", "en una cita", "social", 120,
           {"social": 50, "diversion": 25, "energia": -5}, juntos=OBLIGATORIO),
    Accion("limpiar", "🧹", "Limpiar", "limpiando", "casa", 30, {"energia": -10},
           nombre_juntos="Limpiar juntos"),
    Accion("lavar", "🧺", "Lavar la ropa", "lavando la ropa", "casa", 60, {"energia": -5},
           nombre_juntos="Lavar la ropa juntos"),
    # Se empieza desde la pantalla de trabajo, no desde las categorías.
    Accion("trabajar", "💼", "Trabajar", "trabajando", "trabajo", 8 * 60, juntos=SOLO, ropa=1),
)
ACCIONES: dict[str, Accion] = {a.clave: a for a in _ACCIONES}

ENERGIA_POR_HORA_DORMIDO = 12
ENERGIA_TRABAJO_POR_HORA = 8
HORAS_DESMAYO = 6  # si la energía llega a 0, se duerme donde esté


def horas_para_descansar(energia: float, energia_max: int) -> int:
    return max(1, min(12, math.ceil((energia_max - energia) / ENERGIA_POR_HORA_DORMIDO)))


def preparar(
    a: Accion, segundos: float, nec: dict, energia_max: int, extra: str = "", juntos: bool = False
) -> dict:
    """La acción tal como va a hacerse: duración y efectos totales, en segundos del reloj del Sim."""
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
        efectos["hambre"] = efectos.get("hambre", 0) + comida_del_momento(segundos)[2]
    if juntos:
        minutos = max(1, round(minutos * FACTOR_JUNTOS))
        if a.categoria != "social":
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
    for n in NECESIDADES:
        if n.clave == "energia":
            baja = n.baja_por_hora * max(0.0, horas - horas_ocupado)
        else:
            baja = n.baja_por_hora * horas * multiplicadores.get(n.clave, 1.0)
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
