"""Trabajos, horarios y ascensos (parte 6). Lógica pura, sin Telegram ni base de datos."""

from __future__ import annotations

import random
from dataclasses import dataclass

TRANSPORTE = 4  # por día trabajado
ENERGIA_POR_HORA = 8
MAX_HORAS = 8  # como mucho 8 horas al día
HORAS_POSIBLES = (4, 5, 6, 7, 8)
INICIOS = ("06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00")
DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
# Días trabajados (sin necesidades en rojo) que hacen falta para subir desde cada nivel.
DIAS_PARA_ASCENDER = {1: 5, 2: 10}

LUNES_A_VIERNES, CON_SABADOS, ROTATIVO = "semana", "sabados", "rotativo"
HORARIOS = {
    LUNES_A_VIERNES: "De lunes a viernes",
    CON_SABADOS: "De lunes a sábado",
    ROTATIVO: "Rotativo: incluye fines de semana, con dos días libres entre semana",
}


@dataclass(frozen=True)
class Puesto:
    masculino: str
    femenino: str
    neutro: str
    por_hora: int

    def nombre(self, genero: str | None) -> str:
        return {"mujer": self.femenino, "nobinario": self.neutro}.get(genero or "", self.masculino)


@dataclass(frozen=True)
class Trabajo:
    clave: str
    emoji: str
    nombre: str
    horario: str
    niveles: tuple[Puesto, Puesto, Puesto]


def _p(m: str, f: str | None, n: str | None, sueldo: int) -> Puesto:
    return Puesto(m, f or m, n or m, sueldo)


TRABAJOS: dict[str, Trabajo] = {t.clave: t for t in (
    Trabajo("manicura", "💅", "Manicurista", CON_SABADOS, (
        _p("Manicurista", None, None, 10),
        _p("Técnico de uñas", "Técnica de uñas", "Especialista en uñas", 14),
        _p("Dueño de salón", "Dueña de salón", "A cargo de su propio salón", 22),
    )),
    Trabajo("foto", "📸", "Estudio de fotografía", LUNES_A_VIERNES, (
        _p("Asistente de estudio", None, None, 11),
        _p("Fotógrafo", "Fotógrafa", "Profesional de la fotografía", 16),
        _p("Director del estudio", "Directora del estudio", "A cargo del estudio", 24),
    )),
    Trabajo("super", "🛒", "Supermercado", ROTATIVO, (
        _p("Cajero de súper", "Cajera de súper", "En la caja del súper", 10),
        _p("Encargado", "Encargada", "Persona encargada", 14),
        _p("Gerente", None, None, 20),
    )),
    Trabajo("reparto", "🚚", "Reparto", ROTATIVO, (
        _p("Repartidor", "Repartidora", "Reparto a domicilio", 11),
        _p("Camionero", "Camionera", "Transportista", 16),
        _p("Jefe de logística", "Jefa de logística", "Responsable de logística", 22),
    )),
    Trabajo("cocina", "🍳", "Cocina de restaurante", ROTATIVO, (
        _p("Ayudante de cocina", None, None, 10),
        _p("Cocinero", "Cocinera", "Profesional de cocina", 15),
        _p("Chef", None, None, 25),
    )),
    Trabajo("recepcion", "🛎️", "Oficina", LUNES_A_VIERNES, (
        _p("Recepcionista", None, None, 11),
        _p("Administrativo", "Administrativa", "Personal administrativo", 16),
        _p("Gerente", None, None, 26),
    )),
    Trabajo("taller", "🔧", "Taller mecánico", CON_SABADOS, (
        _p("Ayudante de mecánico", "Ayudante de mecánica", "Ayudante de taller", 12),
        _p("Mecánico", "Mecánica", "Profesional de mecánica", 17),
        _p("Jefe de taller", "Jefa de taller", "Responsable del taller", 24),
    )),
)}


def dias_sugeridos(horario: str, rng: random.Random) -> list[int]:
    """Días de trabajo que sugiere el tipo de horario (0 = lunes … 6 = domingo)."""
    if horario == LUNES_A_VIERNES:
        return [0, 1, 2, 3, 4]
    if horario == CON_SABADOS:
        return [0, 1, 2, 3, 4, 5]
    libre = rng.randint(0, 3)  # rotativo: dos días libres seguidos entre semana
    return [d for d in range(7) if d not in (libre, libre + 1)]


def horario_nuevo(trabajo: str, rng: random.Random) -> dict:
    return {"dias": dias_sugeridos(TRABAJOS[trabajo].horario, rng), "inicio": "09:00", "horas": MAX_HORAS}


def trabaja(horario: dict, dia_semana: int) -> bool:
    return dia_semana in horario.get("dias", [])


def hora_salida(horario: dict) -> str:
    h, m = (int(x) for x in horario["inicio"].split(":"))
    total = h * 60 + m + horario["horas"] * 60
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def texto_dias(dias: list[int]) -> str:
    dias = sorted(dias)
    if dias == [0, 1, 2, 3, 4]:
        return "de lunes a viernes"
    if dias == [0, 1, 2, 3, 4, 5]:
        return "de lunes a sábado"
    if dias == list(range(7)):
        return "todos los días"
    return ", ".join(DIAS_CORTOS[d] for d in dias) if dias else "ningún día"


def texto_horario(horario: dict) -> str:
    """'de lunes a viernes, de 09:00 a 17:00 (8 h)'."""
    return f"{texto_dias(horario['dias'])}, de {horario['inicio']} a {hora_salida(horario)} ({horario['horas']} h)"


def puede_ascender(nivel: int, dias: int) -> bool:
    return nivel in DIAS_PARA_ASCENDER and dias >= DIAS_PARA_ASCENDER[nivel]


def sueldo(trabajo: str, nivel: int, horas: float) -> int:
    return round(TRABAJOS[trabajo].niveles[nivel - 1].por_hora * horas)
