"""Casa, dinero y gastos (parte 5 y actualización 2, parte 3: casa en renta). Todo en dólares;
lógica pura, sin Telegram ni base de datos."""

from __future__ import annotations

from dataclasses import dataclass

DINERO_INICIAL = 3000  # lo que tienen entre los dos al empezar
DIAS_POR_MES = 30
RECARGO = 0.10  # por pagar tarde
CAMION = 150  # lo que cuesta cada mudanza
ENTRADA_ANTIGUA = 1500  # lo que pagaban antes por la casita (para devolver la diferencia)


@dataclass(frozen=True)
class Casa:
    clave: str
    emoji: str
    nombre: str
    descripcion: str
    zonas: tuple[str, ...]  # habitaciones
    mensual: int  # renta, o hipoteca si es propia
    propia: bool = False
    deposito: int = 0  # renta: se paga al entrar y se devuelve al irse
    entrada: int = 0  # compra
    ahorro: int = 0  # lo que hace falta tener ahorrado para mudarse

    @property
    def pago(self) -> str:
        return "hipoteca" if self.propia else "renta"


CASAS: dict[str, Casa] = {c.clave: c for c in (
    Casa("casita", "🏡", "Casita en renta",
         "Una casa pequeña con baño, clóset, un cuarto y una sala-cocina-comedor grande.",
         ("cuarto", "closet", "bano", "salon"), 900, deposito=900),
    Casa("apartamento", "🏢", "Apartamento grande",
         "Más amplio, en renta, con un cuarto extra.",
         ("cuarto", "extra", "closet", "bano", "salon"), 1300, deposito=1300, ahorro=3900),
    Casa("propia", "🏠", "Nuestra casa",
         "¡Suya! Dos cuartos, baño, clóset y una sala-cocina-comedor amplia. Se puede remodelar.",
         ("cuarto", "extra", "closet", "bano", "salon"), 1200, propia=True, entrada=15000, ahorro=15000),
)}
CASA_INICIAL = "casita"
META_CASA = CASAS["propia"].entrada  # la meta de ahorro: "nuestra casa"


@dataclass(frozen=True)
class Factura:
    clave: str
    emoji: str
    nombre: str
    base: int  # al mes
    sin_servicio: str  # qué pasa si se corta
    con_articulo: str = ""  # "la luz", "el agua"…


VIVIENDA = (
    Factura("renta", "🔑", "Renta", 0, ""),
    Factura("hipoteca", "🏦", "Hipoteca", 0, ""),
)
FACTURAS = (
    Factura("luz", "💡", "Luz", 90, "no hay tele, redes ni lavadora", "la luz"),
    Factura("agua", "🚰", "Agua", 40, "no se pueden duchar, bañar, lavar los dientes ni la ropa", "el agua"),
    Factura("internet", "🌐", "Internet", 50, "no hay redes ni videos", "el internet"),
    Factura("gas", "🔥", "Gas", 30, "no se puede cocinar", "el gas"),
)
POR_CLAVE_FACTURA = {f.clave: f for f in VIVIENDA + FACTURAS}
SERVICIOS = ("luz", "agua", "internet", "gas")

# Lo que cuesta cada comida por persona.
PRECIO_COMIDA = {"desayuno": 3, "almuerzo": 5, "cena": 4}
PRECIO_PICAR = 1
DOMICILIO = 2  # pedir a domicilio cuesta el doble

# Salidas: (solo, en pareja). Los fines de semana salen más caras.
PRECIO_SALIDA = {"restaurante": (20, 40), "cine": (13, 25)}
RECARGO_FIN_DE_SEMANA = 0.25
GIMNASIO_MES = 30

# Servicios que necesita cada acción.
NECESITA_SERVICIO = {
    "tele": ("luz",),
    "consola": ("luz",),
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
    "consola": {"luz": 0.20},
    "redes": {"luz": 0.15},
    "lavar": {"luz": 1.00, "agua": 1.50},
    "cocinar": {"luz": 0.20},
    "ducha": {"agua": 0.60},
    "banarse": {"agua": 1.20},
    "dientes": {"agua": 0.05},
    "limpiar": {"agua": 0.30},
}

def dinero(cantidad: float) -> str:
    """'$3.000' con punto de miles (y '−$50' si es negativo)."""
    signo = "−" if cantidad < 0 else ""
    return f"{signo}${abs(round(cantidad)):,}".replace(",", ".")


def factura_del_mes(consumo: dict, casa: Casa) -> list[tuple[Factura, int]]:
    """Cada factura con lo que toca pagar este mes: la renta (o hipoteca) y los servicios, base más lo consumido."""
    vivienda = POR_CLAVE_FACTURA[casa.pago]
    return [(vivienda, casa.mensual)] + [(f, round(f.base + consumo.get(f.clave, 0))) for f in FACTURAS]


def total_mes(consumo: dict, casa: Casa) -> int:
    return sum(monto for _, monto in factura_del_mes(consumo, casa))


def costo_mudanza(actual: Casa, nueva: Casa) -> int:
    """Lo que sale de la cuenta al mudarse: entrada o depósito nuevo y camión, menos el depósito que les devuelven."""
    return nueva.entrada + nueva.deposito + CAMION - actual.deposito


def barra_ahorro(tienen: int, meta: int, largo: int = 10) -> str:
    llenos = max(0, min(largo, int(largo * tienen / meta))) if meta else largo
    return "🟩" * llenos + "⬜" * (largo - llenos)


def precio_comida(comida: str) -> int:
    return PRECIO_COMIDA.get(comida, 4)


def servicios_cortados(pendientes: list[dict]) -> set[str]:
    return {p["clave"] for p in pendientes if p["clave"] in SERVICIOS}


def falta_servicio(accion: str, cortados: set[str]) -> str | None:
    """Mensaje si la acción necesita un servicio cortado."""
    for servicio in NECESITA_SERVICIO.get(accion, ()):
        if servicio in cortados:
            f = POR_CLAVE_FACTURA[servicio]
            return f"{f.emoji} Les cortaron {f.con_articulo}: {f.sin_servicio}. Paguen la factura en 💰 Dinero."
    return None


def cobrar_mes(cuenta: int, consumo: dict, casa: Casa) -> tuple[int, list[tuple[str, int]], list[dict]]:
    """Cobra las facturas del mes desde la cuenta compartida, en orden.

    Devuelve la cuenta restante, lo pagado [(concepto, monto)] y lo que no se pudo pagar,
    ya con el recargo del 10 % [{"clave", "monto"}].
    """
    pagado, impagos = [], []
    for f, monto in factura_del_mes(consumo, casa):
        if cuenta >= monto:
            cuenta -= monto
            pagado.append((f.clave, monto))
        else:
            impagos.append({"clave": f.clave, "monto": round(monto * (1 + RECARGO))})
    return cuenta, pagado, impagos
