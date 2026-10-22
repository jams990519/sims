"""Pausa de la pareja (versión 0.44): ⏸️ Pausar / ▶️ Reanudar el juego de los dos.

`PausaMixin` se mezcla con `Juego`. Es una sola pausa para la pareja y cualquiera de los dos la pone o la
quita (al otro le llega un aviso corto). Mientras dura:
- los relojes de los Sims se paran: las necesidades, el ánimo y las acciones no avanzan;
- lo que corre solo cada minuto (avisos de necesidades, mensajitos, cocina, ir al trabajo, facturas,
  mascota, eventos, influencer, estudios…) no ve la sala (ver `SinPausadas` y `Juego.tick`);
- solo se puede reanudar, chatear y mirar los ajustes.
Al reanudar, todas las horas guardadas se corren lo que duró la pausa: nada se descuenta.

En `extras` del hogar: "pausa" {desde, por, corrian (los Sims cuyo reloj corría al pausar)}.
"""

from __future__ import annotations

import json

from . import vida as V
from .db import Hogar, Jugador

EN_PAUSA = ("pausar", "sala", "ajustes")  # lo único que se puede tocar con el juego en pausa
PAUSAR = ("⏸️ Pausar el juego", "pausar")
REANUDAR = ("▶️ Reanudar el juego", "pausar")
HASTA_HORA = ("oferta_hasta", "lluvia_hasta", "apagon_hasta")  # eventos de la casa que terminan a una hora
FIN_DE_EVENTO = ("visita", "antojo")  # eventos con su propia hora de fin («hasta»)
HASTA_DIA = ("resfriado_hasta", "gimnasio_hasta")  # del jugador: hasta qué día (local) dura


class SinPausadas:
    """La base de datos tal cual, pero sin las salas en pausa: lo que avanza solo cada minuto no las ve."""

    def __init__(self, db, pausadas: set[int]):
        self._db = db
        self._pausadas = pausadas

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def hogares(self):
        return [h for h in self._db.hogares() if h.sala_id not in self._pausadas]

    def jugadores_en_sala(self):
        return [j for j in self._db.jugadores_en_sala() if j.sala_id not in self._pausadas]


class PausaMixin:
    def _pausa_pareja(self, sala_id: int | None) -> dict | None:
        h = self.db.hogar(sala_id) if sala_id is not None else None
        return self._extras_hogar(h).get("pausa") if h else None

    def _salas_en_pausa(self) -> set[int]:
        return {h.sala_id for h in self.db.hogares() if self._extras_hogar(h).get("pausa")}

    def _activos_de_sala(self, sala_id: int) -> list[Jugador]:
        return [m for m in self.db.miembros_sala(sala_id) if m.estado == "activo"]

    def _b_pausar(self, j: Jugador, arg: str, res) -> None:
        """⏸️ Pausar / ▶️ Reanudar: el mismo botón pone y quita la pausa de la pareja."""
        if self._pausa_pareja(j.sala_id):
            self._reanudar_pareja(j, res)
        else:
            self._pausar_pareja(j, res)

    def _pausar_pareja(self, j: Jugador, res) -> None:
        from .juego import Aviso

        ahora = self.reloj()
        corrian = []
        for m in self._activos_de_sala(j.sala_id):
            for texto, avisar in self._vivir(m, ahora):  # al día hasta este instante
                if m.id == j.id:
                    res.notas.append(texto)
                elif avisar:
                    res.avisos.append(Aviso(m.id, texto, [[("🧍 Mi Sim", "sim")]]))
            m = self.db.jugador(m.id)
            if not self._congelado(m, ahora):
                corrian.append(m.id)
            self._congelar(m, ahora)
            self.db.guardar_jugador(m)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        ex["pausa"] = {"desde": ahora, "por": j.id, "corrian": corrian}
        self._guardar_extras_hogar(h, ex)
        for m in self._activos_de_sala(j.sala_id):
            if m.id != j.id:
                res.avisos.append(Aviso(m.id, f"⏸️ <b>Juego en pausa</b>: lo pausó {self._firma(j)}.", [[REANUDAR]]))
        res.pantalla = self._pantalla_pausa_pareja(j)
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)

    def _reanudar_pareja(self, j: Jugador, res) -> None:
        from .juego import Aviso

        ahora = self.reloj()
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        pausa = ex.pop("pausa")
        corre = max(0.0, ahora - pausa["desde"])  # lo que duró la pausa
        dias = int(ahora // V.DIA) - int(pausa["desde"] // V.DIA)
        for m in self._activos_de_sala(j.sala_id):
            accion = self._accion(m)
            if accion:
                accion["rini"] += corre
                accion["rfin"] += corre
                m.accion = json.dumps(accion)
            if m.id in pausa["corrian"]:  # su reloj sigue justo donde quedó
                m.reloj_desde = ahora
                m.ultima_jugada += corre
            extras = self._extras(m)
            if (extras.get("influencer") or {}).get("ultimo"):
                extras["influencer"]["ultimo"] += dias  # los días sin publicar no cuentan los de la pausa
            if (extras.get("estudio") or {}).get("pagado_hasta"):
                extras["estudio"]["pagado_hasta"] += dias
            for clave in HASTA_DIA:  # el resfriado y el gimnasio pagado duran los días que jugaron
                if extras.get(clave):
                    extras[clave] += dias
            m.extras = json.dumps(extras)
            self.db.guardar_jugador(m)
        self._correr_hogar(h, ex, corre, dias)
        for m in self._activos_de_sala(j.sala_id):
            if m.id != j.id:
                res.avisos.append(Aviso(m.id, f"▶️ <b>Juego reanudado</b>: lo reanudó {self._firma(j)}.",
                                        [[("🎮 Menú", "menu")]]))
        self._b_menu(self.db.jugador(j.id), "", res, aviso="▶️ <b>Juego reanudado</b>: todo sigue donde quedó.")
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)

    def _correr_hogar(self, h: Hogar, ex: dict, corre: float, dias: int) -> None:
        """Las horas de la casa se corren lo que duró la pausa: la cocina, las facturas, la mascota y los
        eventos siguen donde quedaron."""
        if h.cocina:
            coccion = json.loads(h.cocina)
            coccion["paso_ini"] += corre
            h.cocina = json.dumps(coccion)
        h.dia_hogar += dias
        h.proximo_cobro += dias
        if ex.get("mascota"):
            ex["mascota"]["vivo"] = self.reloj()  # sus barras no bajan por la pausa
        if (ex.get("eventos") or {}).get("proximo"):
            ex["eventos"]["proximo"] += corre
        for clave in HASTA_HORA:
            if ex.get(clave):
                ex[clave] += corre
        for clave in FIN_DE_EVENTO:
            if isinstance(ex.get(clave), dict) and "hasta" in ex[clave]:
                ex[clave]["hasta"] += corre
        h.extras = json.dumps(ex)
        self.db.guardar_hogar(h)

    def _b_ver_pausa(self, j: Jugador, arg: str, res) -> None:
        """Al volver a la pantalla de la pausa: si ya se reanudó, el menú."""
        if self._pausa_pareja(j.sala_id):
            res.pantalla = self._pantalla_pausa_pareja(j)
        else:
            self._b_menu(j, "", res)

    def _pantalla_pausa_pareja(self, j: Jugador):
        from .juego import Pantalla, duracion

        pausa = self._pausa_pareja(j.sala_id)
        quien = self.db.jugador(pausa["por"])
        hace = duracion(self.reloj() - pausa["desde"])
        return Pantalla(
            "⏸️ <b>El juego está en pausa</b>\n\n"
            f"Lo pausó {self._firma(quien) if quien else 'alguien'} hace {hace}.\n"
            "❄️ Nada avanza: ni el hambre ni las demás necesidades, ni el ánimo, ni las acciones, la cocina, "
            "el trabajo o las facturas. Tampoco llegan avisos.\n\n"
            "💬 Pueden seguir chateando. Cuando quieran seguir, cualquiera de los dos toca ▶️ Reanudar.",
            [[REANUDAR], [("💬 Chat", "sala"), ("⚙️ Ajustes", "ajustes")]],
            clave="pausa",
        )
