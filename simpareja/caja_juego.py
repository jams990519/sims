"""Caja de ahorros (versión 0.31).

`CajaMixin` se mezcla con `Juego`. En 💰 Dinero → 🐷 Caja de ahorros:
- Se abre cuando la pareja lo decide: uno lo propone y el otro acepta (sin pareja, se abre al momento).
- Cualquiera de los dos pone dinero, de su cartera o de la cuenta compartida.
- Lo que está en la caja no se gasta en facturas ni compras, y gana un 1 % cada mes (al cobrarse las facturas).
- Sacar dinero (a la cuenta compartida) también lo deciden los dos.

En `extras` del hogar: "caja" {saldo, desde (día)} y "caja_prop" {que: "abrir" o "sacar", de, monto, ts}.
"""

from __future__ import annotations

import json

from . import dinero as D
from .db import Hogar, Jugador

INTERES = 0.01  # al mes
MONTOS = (20, 50, 100, 500)
PROPUESTA_VENCE = 24 * 60 * 60  # un día para responder


class CajaMixin:
    def _caja(self, h: Hogar) -> dict | None:
        return self._extras_hogar(h).get("caja")

    def _propuesta_caja(self, h: Hogar) -> dict | None:
        prop = self._extras_hogar(h).get("caja_prop")
        return prop if prop and self.reloj() - prop["ts"] <= PROPUESTA_VENCE else None

    def _interes_caja(self, h: Hogar) -> str | None:
        """Al cobrarse las facturas del mes, la caja gana su 1 %. Quien llama guarda el hogar."""
        extras = self._extras_hogar(h)
        caja = extras.get("caja")
        interes = int(caja["saldo"] * INTERES) if caja else 0
        if interes <= 0:
            return None
        caja["saldo"] += interes
        h.extras = json.dumps(extras)
        self._anotar_movimiento(h.sala_id, None, "caja", interes, "📈 Intereses de la caja")
        return f"🐷 La caja de ahorros ganó {D.dinero(interes)}: ahora tiene {D.dinero(caja['saldo'])}."

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_caja(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """caja · caja:abrir · caja:poner:c|h (de la cartera o de la compartida) · caja:sacar."""
        que, _, donde = arg.partition(":")
        if que == "abrir":
            self._caja_abrir(j, res)
        elif que in ("poner", "sacar"):
            self._caja_montos(j, que, donde, res)
        else:
            self._pantalla_caja(j, res, aviso)

    def _pantalla_caja(self, j: Jugador, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        caja = self._caja(h)
        pareja = self._pareja_en_sala(j)
        prop = self._propuesta_caja(h) if pareja else None
        lineas = [aviso, ""] if aviso else []
        lineas += ["🐷 <b>Caja de ahorros</b>", ""]
        botones = []
        if caja is None:
            lineas += [
                "Una caja aparte para ahorrar juntos:",
                "🔒 Lo que pongan no se gasta en facturas ni compras.",
                "📈 Gana un 1 % cada mes.",
            ]
            if pareja:
                lineas.append("🤝 Se abre, y se saca dinero, solo si los dos están de acuerdo.")
            if prop and prop["que"] == "abrir" and prop["de"] == j.id:
                lineas += ["", f"⏳ Esperando a que {self._firma(pareja)} acepte abrirla."]
            elif not (prop and prop["que"] == "abrir"):
                botones.append([("🐷 Proponer abrir la caja" if pareja else "🐷 Abrir la caja", "caja:abrir")])
        else:
            lineas += [
                f"💰 Ahorrado: <b>{D.dinero(caja['saldo'])}</b>",
                "📈 Gana un 1 % cada mes · 🔒 no se gasta en facturas",
                "",
                f"👛 Tu cartera: {D.dinero(j.cartera)}",
                f"🏦 Cuenta compartida: {D.dinero(h.cuenta)}",
            ]
            if prop and prop["que"] == "sacar" and prop["de"] == j.id:
                lineas += ["", f"⏳ Esperando a que {self._firma(pareja)} acepte sacar {D.dinero(prop['monto'])}."]
            botones += [
                [("➕ De mi cartera", "caja:poner:c"), ("➕ De la compartida", "caja:poner:h")],
                [("➖ Sacar a la compartida", "caja:sacar")],
            ]
        if prop and prop["de"] != j.id:
            if prop["que"] == "abrir":
                lineas += ["", f"💌 {self._firma(pareja)} propone abrir la caja de ahorros."]
            else:
                lineas += ["", f"💌 {self._firma(pareja)} quiere sacar {D.dinero(prop['monto'])} a la cuenta compartida."]
            botones.insert(0, [("✅ Sí, de acuerdo", "cajaok"), ("❌ Ahora no", "cajano")])
        elif prop:
            botones.append([("🚫 Retirar mi propuesta", "cajano")])
        botones.append([("💰 Dinero", "dinero"), ("🎮 Menú", "menu")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="caja")

    def _caja_montos(self, j: Jugador, que: str, donde: str, res) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        caja = self._caja(h)
        if caja is None:
            res.alerta = "Primero abran la caja de ahorros."
            self._pantalla_caja(j, res)
            return
        if que == "poner":
            donde = "c" if donde != "h" else "h"
            disponible = j.cartera if donde == "c" else h.cuenta
            titulo = "➕ <b>Poner en la caja</b> de " + ("tu cartera" if donde == "c" else "la cuenta compartida")
            dato = f"cajap:{donde}:"
        else:
            disponible = caja["saldo"]
            titulo = "➖ <b>Sacar de la caja</b> a la cuenta compartida"
            if self._pareja_en_sala(j):
                titulo += "\n<i>Tu pareja tiene que estar de acuerdo.</i>"
            dato = "cajas:"
        opciones = [(D.dinero(m), f"{dato}{m}") for m in MONTOS if m <= disponible]
        if disponible > 0:
            opciones.append((f"Todo ({D.dinero(disponible)})", f"{dato}{disponible}"))
        texto = f"{titulo}\n\nDisponible: {D.dinero(disponible)}"
        if not opciones:
            texto += "\n\nNo hay dinero para mover."
        filas = [opciones[i:i + 2] for i in range(0, len(opciones), 2)]
        res.pantalla = Pantalla(texto, filas + [[("⬅️ Caja de ahorros", "caja")]], clave="caja")

    # ------------------------------------------------------------------
    # Abrir, poner y sacar
    # ------------------------------------------------------------------

    def _abrir_caja(self, h: Hogar) -> None:
        extras = self._extras_hogar(h)
        extras["caja"] = {"saldo": 0, "desde": self._dia_hogar(h.sala_id)}
        extras.pop("caja_prop", None)
        self._guardar_extras_hogar(h, extras)

    def _caja_abrir(self, j: Jugador, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        if self._caja(h) is not None:
            self._pantalla_caja(j, res)
            return
        pareja = self._pareja_en_sala(j)
        prop = self._propuesta_caja(h)
        if pareja is None:
            self._abrir_caja(h)
            self._pantalla_caja(j, res, "🐷 ¡Abriste tu caja de ahorros!")
            return
        if prop and prop["que"] == "abrir" and prop["de"] != j.id:  # los dos lo propusieron
            self._b_caja_si(j, "", res)
            return
        extras = self._extras_hogar(h)
        extras["caja_prop"] = {"que": "abrir", "de": j.id, "monto": 0, "ts": self.reloj()}
        self._guardar_extras_hogar(h, extras)
        res.avisos.append(Aviso(
            pareja.id,
            f"🐷 {self._firma(j)} propone abrir una <b>caja de ahorros</b> para los dos: lo que pongan no se gasta "
            "en facturas y gana un 1 % cada mes. ¿Están de acuerdo?",
            [[("✅ Sí, abrámosla", "cajaok"), ("❌ Ahora no", "cajano")]],
        ))
        self._pantalla_caja(j, res, f"💌 Propuesta enviada. Cuando {self._firma(pareja)} acepte, se abre la caja.")

    def _b_caja_poner(self, j: Jugador, arg: str, res) -> None:
        """cajap:c|h:<monto>: poner dinero de la cartera o de la cuenta compartida."""
        from .juego import Aviso

        donde, _, monto = arg.partition(":")
        monto = int(monto) if monto.isdigit() else 0
        h = self._hogar(j.sala_id)
        extras = self._extras_hogar(h)
        caja = extras.get("caja")
        disponible = j.cartera if donde == "c" else h.cuenta if donde == "h" else 0
        if caja is None or monto <= 0 or monto > disponible:
            res.alerta = "No hay suficiente dinero." if caja is not None else "Primero abran la caja de ahorros."
            self._pantalla_caja(j, res)
            return
        if donde == "c":
            j.cartera -= monto
            self.db.guardar_jugador(j)
            self._anotar_movimiento(j.sala_id, j.id, "cartera", -monto, "🐷 A la caja de ahorros")
        else:
            h.cuenta -= monto
            self._anotar_movimiento(j.sala_id, j.id, "compartida", -monto, "🐷 A la caja de ahorros")
        caja["saldo"] += monto
        self._anotar_movimiento(j.sala_id, j.id, "caja", monto, "🐷 Ahorro")
        self._guardar_extras_hogar(h, extras)
        pareja = self._pareja_en_sala(j)
        if pareja:
            res.avisos.append(Aviso(
                pareja.id, f"🐷 {self._firma(j)} puso {D.dinero(monto)} en la caja de ahorros "
                           f"(ahora tiene {D.dinero(caja['saldo'])}).",
            ))
        self._pantalla_caja(j, res, f"✅ Pusiste {D.dinero(monto)} en la caja de ahorros.")

    def _sacar_de_caja(self, h: Hogar, quien: Jugador, monto: int) -> bool:
        extras = self._extras_hogar(h)
        caja = extras.get("caja")
        if caja is None or monto <= 0 or monto > caja["saldo"]:
            return False
        caja["saldo"] -= monto
        h.cuenta += monto
        extras.pop("caja_prop", None)
        self._anotar_movimiento(h.sala_id, quien.id, "caja", -monto, "🐷 Sacado de la caja")
        self._anotar_movimiento(h.sala_id, quien.id, "compartida", monto, "🐷 Desde la caja de ahorros")
        self._guardar_extras_hogar(h, extras)
        return True

    def _b_caja_sacar(self, j: Jugador, arg: str, res) -> None:
        """cajas:<monto>: sin pareja se saca al momento; en pareja, se le propone."""
        from .juego import Aviso

        monto = int(arg) if arg.isdigit() else 0
        h = self._hogar(j.sala_id)
        caja = self._caja(h)
        if caja is None or monto <= 0 or monto > caja["saldo"]:
            res.alerta = "No hay tanto en la caja."
            self._pantalla_caja(j, res)
            return
        pareja = self._pareja_en_sala(j)
        if pareja is None:
            self._sacar_de_caja(h, j, monto)
            self._pantalla_caja(j, res, f"✅ Sacaste {D.dinero(monto)} a la cuenta compartida.")
            return
        extras = self._extras_hogar(h)
        extras["caja_prop"] = {"que": "sacar", "de": j.id, "monto": monto, "ts": self.reloj()}
        self._guardar_extras_hogar(h, extras)
        res.avisos.append(Aviso(
            pareja.id,
            f"🐷 {self._firma(j)} quiere sacar <b>{D.dinero(monto)}</b> de la caja de ahorros a la cuenta compartida "
            f"(en la caja hay {D.dinero(caja['saldo'])}). ¿Están de acuerdo?",
            [[("✅ Sí, de acuerdo", "cajaok"), ("❌ Ahora no", "cajano")]],
        ))
        self._pantalla_caja(j, res, f"💌 Le pregunté a {self._firma(pareja)}. Si acepta, el dinero pasa a la compartida.")

    def _b_caja_si(self, j: Jugador, arg: str, res) -> None:
        """La pareja acepta la propuesta: abrir la caja o sacar dinero."""
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        prop = self._propuesta_caja(h)
        de = self.db.jugador(prop["de"]) if prop else None
        if prop is None or prop["de"] == j.id or de is None or de.sala_id != j.sala_id:
            res.alerta = "Esa propuesta ya no está."
            self._pantalla_caja(j, res)
            return
        if prop["que"] == "abrir":
            if self._caja(h) is None:
                self._abrir_caja(h)
            texto = "🐷 ¡Abrieron la caja de ahorros! Pongan ahí lo que quieran guardar."
        elif self._sacar_de_caja(h, de, prop["monto"]):
            texto = f"🐷 Sacaron {D.dinero(prop['monto'])} de la caja a la cuenta compartida."
        else:
            res.alerta = "Ya no hay tanto en la caja."
            self._pantalla_caja(j, res)
            return
        res.avisos.append(Aviso(de.id, f"💞 {self._firma(j)} aceptó.\n{texto}", [[("🐷 Caja de ahorros", "caja")]]))
        self._pantalla_caja(j, res, texto)

    def _b_caja_no(self, j: Jugador, arg: str, res) -> None:
        """Rechazar la propuesta de la pareja o retirar la propia."""
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        extras = self._extras_hogar(h)
        prop = extras.pop("caja_prop", None)
        if prop:
            self._guardar_extras_hogar(h, extras)
            if prop["de"] != j.id:
                que = "abrir la caja de ahorros" if prop["que"] == "abrir" else f"sacar {D.dinero(prop['monto'])} de la caja"
                res.avisos.append(Aviso(prop["de"], f"🙈 {self._firma(j)} prefiere no {que} por ahora."))
                res.alerta = "Le avisé que por ahora no."
            else:
                res.alerta = "Propuesta retirada."
        self._pantalla_caja(j, res)
