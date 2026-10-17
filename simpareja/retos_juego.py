"""Retos semanales de pareja (actualización 2, parte 11).

`RetosMixin` se mezcla con `Juego`. Cada semana (de lunes a domingo) toca un reto para hacer
juntos, por ejemplo cocinar juntos tres veces o tener una cita el fin de semana. Al cumplirlo
ganan dinero o relación (los objetos llegarán con las tiendas).

En `extras` del hogar: "reto" {semana, clave, meta, progreso, premio, valor, hecho, contados}
y "retos_hechos" (los cumplidos).
"""

from __future__ import annotations

from . import dinero as D
from .db import Hogar, Jugador

RETOS = {
    "cocinar": ("🍳 Cocinar juntos 3 veces", 3),
    "cita_finde": ("🌹 Tener una cita el fin de semana (restaurante, cine o parque)", 1),
    "abrazos": ("🤗 Darse 5 abrazos", 5),
    "limpiar": ("🧹 Limpiar juntos 2 zonas de la casa", 2),
    "preguntas": ("❓ Responder los dos 2 preguntas de pareja", 2),
    "comer": ("🍽️ Comer juntos 4 veces", 4),
    "parque": ("🌳 Pasear juntos por el parque 2 veces", 2),
    "tele": ("📺 Ver la tele juntos 3 veces", 3),
}
# Qué acción hecha juntos cuenta para cada reto.
POR_ACCION = {"abrazar": "abrazos", "limpiar": "limpiar", "comer": "comer", "parque": "parque", "tele": "tele"}
SALIDAS = ("restaurante", "cine", "parque")
DINERO = (100, 200)
RELACION = 5
HISTORIAL = 20


class RetosMixin:
    def _lunes(self, j: Jugador) -> int:
        local = self._local(j)
        return local.toordinal() - local.weekday()

    def _reto(self, h: Hogar) -> dict | None:
        return self._extras_hogar(h).get("reto")

    def _nuevo_reto(self, h: Hogar, semana: int) -> dict:
        ex = self._extras_hogar(h)
        anterior = (ex.get("reto") or {}).get("clave")
        clave = self.rng.choice([c for c in RETOS if c != anterior])
        premio = self.rng.choice(("dinero", "relacion"))
        valor = self.rng.randint(*DINERO) if premio == "dinero" else RELACION
        reto = {"semana": semana, "clave": clave, "meta": RETOS[clave][1], "progreso": 0, "premio": premio,
                "valor": valor, "hecho": False, "contados": []}
        ex["reto"] = reto
        self._guardar_extras_hogar(h, ex)
        return reto

    def _texto_premio(self, reto: dict) -> str:
        return D.dinero(reto["valor"]) + " para la cuenta compartida" if reto["premio"] == "dinero" \
            else f"+{reto['valor']} en el medidor de los dos"

    def _avanzar_reto(self, h: Hogar, clave: str, ref=None) -> None:
        """Suma un paso al reto de la semana si es de ese tipo (`ref` evita contar dos veces lo mismo)."""
        ex = self._extras_hogar(h)
        reto = ex.get("reto")
        if not reto or reto["hecho"] or reto["clave"] != clave:
            return
        if ref is not None:
            if ref in reto["contados"]:
                return
            reto["contados"].append(ref)
        reto["progreso"] = min(reto["meta"], reto["progreso"] + 1)
        self._guardar_extras_hogar(h, ex)

    def _reto_accion(self, j: Jugador, accion: dict) -> None:
        """Al terminar una acción hecha juntos, cuenta para el reto que corresponda."""
        if not accion.get("con"):
            return
        h = self._hogar(j.sala_id)
        if accion["k"] in POR_ACCION:
            self._avanzar_reto(h, POR_ACCION[accion["k"]], accion["rini"])
        if accion["k"] in SALIDAS and self._finde(j, accion["rini"]):
            self._avanzar_reto(h, "cita_finde", accion["rini"])

    def _b_retos(self, j: Jugador, arg: str, res) -> None:
        """💕 Pareja → 🎯 Retos."""
        from .juego import Pantalla

        if self._pareja_en_sala(j) is None:
            res.alerta = "Los retos son para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        h = self._hogar(j.sala_id)
        reto = self._reto(h)
        if reto is None or reto["semana"] != self._lunes(j):
            reto = self._nuevo_reto(h, self._lunes(j))
        nombre, meta = RETOS[reto["clave"]]
        dias = reto["semana"] + 7 - self._hoy(j)
        lineas = [
            "🎯 <b>Reto de la semana</b>",
            "",
            f"{nombre}",
            f"{'🟩' * reto['progreso']}{'⬜' * (meta - reto['progreso'])} {reto['progreso']}/{meta}",
            f"🏆 Premio: {self._texto_premio(reto)}",
        ]
        if reto["hecho"]:
            lineas.append("✅ ¡Cumplido! El lunes llega un reto nuevo.")
        else:
            lineas.append(f"⏳ Les queda{'n' if dias != 1 else ''} {dias} día(s).")
        hechos = self._extras_hogar(h).get("retos_hechos", [])
        if hechos:
            lineas += ["", f"🏅 Retos cumplidos: {len(hechos)}"]
            lineas += [f"✅ {RETOS[r['clave']][0]}" for r in reversed(hechos[-3:]) if r["clave"] in RETOS]
        res.pantalla = Pantalla("\n".join(lineas), [[("⬅️ Atrás", "mpar")]], clave="retos")

    def _tick_retos(self, res) -> None:
        """Reto nuevo cada lunes y el premio en cuanto lo cumplen."""
        from .juego import Aviso

        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if len(miembros) < 2 or not h.casa:
                continue
            h = self._hogar(h.sala_id)
            reto = self._reto(h)
            lunes = self._lunes(miembros[0])
            if reto and reto["progreso"] >= reto["meta"] and not reto["hecho"]:
                texto = self._premiar_reto(h, reto, miembros)
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("🎯 Retos", "retos")]]))
            elif reto is None or reto["semana"] != lunes:
                reto = self._nuevo_reto(h, lunes)
                texto = (f"🎯 <b>Reto de la semana</b>: {RETOS[reto['clave']][0]}.\n"
                         f"🏆 Premio: {self._texto_premio(reto)}.")
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("🎯 Retos", "retos")]]))

    def _premiar_reto(self, h: Hogar, reto: dict, miembros: list[Jugador]) -> str:
        if reto["premio"] == "dinero":
            h.cuenta += reto["valor"]
            self.db.guardar_hogar(h)
            self._anotar_movimiento(h.sala_id, None, "compartida", reto["valor"], "🎯 Premio del reto de la semana")
        else:
            for m in miembros:
                self._cambiar_relacion(m, reto["valor"], "🎯 Cumplimos el reto de la semana", auto=True)
        h = self._hogar(h.sala_id)
        ex = self._extras_hogar(h)
        ex["reto"]["hecho"] = True
        ex["retos_hechos"] = (ex.get("retos_hechos", []) + [{"clave": reto["clave"], "ts": self.reloj()}])[-HISTORIAL:]
        self._guardar_extras_hogar(h, ex)
        return f"🎯🏆 <b>¡Reto cumplido!</b> {RETOS[reto['clave']][0]}. Ganaron {self._texto_premio(reto)}."
