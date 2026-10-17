"""Viajes en pareja: el hito «primer viaje» (actualización 2, parte 12).

`ViajeMixin` se mezcla con `Juego`. Eligen destino y días (de $800 a $2.000): uno lo propone y el
otro acepta; al aceptar se paga. Durante el viaje no trabajan, no hacen cosas de la casa y sus
necesidades no bajan. Al volver: diversión y energía al máximo, un recuerdo en el álbum y, la
primera vez, el hito (se celebra con los dos conectados: +20 en el medidor).

En `extras` del hogar: "viaje" {destino, desde, hasta (fechas locales, incluidas), de, estado,
empezo} y "viajes" (cuántos hicieron).
"""

from __future__ import annotations

from . import dinero as D
from . import vida as V
from .mascota_juego import CUIDADOR_DIA
from .db import Hogar, Jugador

DESTINOS = {
    "playa": ("🏖️", "la playa", 2, 800),
    "montana": ("🏔️", "la montaña", 3, 1200),
    "ciudad": ("🏛️", "una ciudad histórica", 3, 1500),
    "paris": ("🗼", "París", 4, 2000),
}
ANTICIPACION = 7  # cuántos días antes se puede planear
LUGAR = f"{V.FUERA}:viaje"


class ViajeMixin:
    def _viaje(self, h: Hogar) -> dict | None:
        return self._extras_hogar(h).get("viaje")

    def _de_viaje(self, j: Jugador) -> dict | None:
        """El viaje en curso, si hoy están de viaje."""
        if j.sala_id is None:
            return None
        v = self._viaje(self._hogar(j.sala_id))
        if v and v["estado"] == "acordado" and v.get("empezo") and v["desde"] <= self._hoy(j) <= v["hasta"]:
            return v
        return None

    def _texto_viaje(self, v: dict) -> str:
        emoji, nombre, dias, costo = DESTINOS[v["destino"]]
        desde, hasta = (self._fecha_texto(v[k]) for k in ("desde", "hasta"))
        return f"{emoji} {nombre} · {dias} días, del {desde} al {hasta} · {D.dinero(costo)}"

    def _b_viaje(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """viaje · viaje:<destino> · viaje:<destino>:<desde> (propone)."""
        from .juego import Aviso, Pantalla, esc

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "Los viajes son para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        h = self._hogar(j.sala_id)
        v = self._viaje(h)
        hoy = self._hoy(j)
        if v and v["estado"] == "propuesto" and v["desde"] < hoy:
            v = None  # la propuesta caducó
        destino, _, desde = arg.partition(":")
        if v is None and destino in DESTINOS:
            emoji, nombre, dias, costo = DESTINOS[destino]
            fechas = list(range(hoy, hoy + ANTICIPACION + 1))
            if not desde.isdigit() or int(desde) not in fechas:
                res.pantalla = Pantalla(
                    f"{emoji} Viaje a {nombre} ({dias} días, {D.dinero(costo)}). ¿Cuándo se van?\n"
                    "Esos días no trabajan.",
                    [[(("Hoy" if d == hoy else "Mañana" if d == hoy + 1 else self._fecha_texto(d)), f"viaje:{destino}:{d}")
                      for d in fechas[k:k + 4]] for k in range(0, len(fechas), 4)] + [[("⬅️ Atrás", "viaje")]],
                    clave="viaje",
                )
                return
            inicio = int(desde)
            v = {"destino": destino, "desde": inicio, "hasta": inicio + dias - 1, "de": j.id, "estado": "propuesto"}
            ex = self._extras_hogar(h)
            ex["viaje"] = v
            self._guardar_extras_hogar(h, ex)
            res.avisos.append(Aviso(
                pareja.id,
                f"✈️ {self._firma(j)} propone un viaje: {self._texto_viaje(v)}. ¿Se van?",
                [[("✅ ¡Sí, vámonos!", "viajeok"), ("❌ Ahora no", "viajeno")]],
            ))
            aviso = "💌 Viaje propuesto: cuando tu pareja acepte, se paga y queda listo."
        lineas = [aviso, ""] if aviso else []
        lineas.append("✈️ <b>Viajes</b>")
        botones = []
        if v and v["estado"] == "acordado":
            if v.get("empezo"):
                lineas.append(f"🧳 ¡Están de viaje! {self._texto_viaje(v)}")
                lineas.append("No se trabaja ni se hacen cosas de casa, y las necesidades no bajan. ¡A disfrutar!")
            else:
                lineas.append(f"✅ Viaje acordado: {self._texto_viaje(v)}")
                lineas.append("Esos días no trabajan. Al volver: diversión y energía al máximo.")
        elif v and v["estado"] == "propuesto":
            de = self.db.jugador(v["de"])
            lineas.append(f"💌 {esc(de.personaje) if de else '…'} propuso: {self._texto_viaje(v)}")
            if v["de"] != j.id:
                botones.append([("✅ ¡Sí, vámonos!", "viajeok"), ("❌ Ahora no", "viajeno")])
            else:
                lineas.append("⏳ Esperando que acepte.")
        else:
            lineas += ["Elijan destino y días. Se paga de la cuenta compartida al aceptar.", ""]
            for clave, (emoji, nombre, dias, costo) in DESTINOS.items():
                botones.append([(f"{emoji} {nombre[0].upper() + nombre[1:]} · {dias} días · {D.dinero(costo)}", f"viaje:{clave}")])
        hechos = self._extras_hogar(h).get("viajes", 0)
        if hechos:
            lineas += ["", f"🧳 Han hecho {hechos} viaje(s)."]
        botones.append([("🏆 Hitos", "hitos"), ("⬅️ Atrás", "mpar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="viaje")

    def _b_viaje_aceptar(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        v = self._viaje(h)
        if not v or v["estado"] != "propuesto" or v["de"] == j.id or v["desde"] < self._hoy(j):
            res.alerta = "Esa propuesta de viaje ya no está."
            self._b_viaje(j, "", res)
            return
        emoji, nombre, dias, costo = DESTINOS[v["destino"]]
        concepto = f"{emoji} Viaje a {nombre}"
        if self._mascota(h):  # alguien cuida a la mascota mientras no están
            costo += CUIDADOR_DIA * dias
            concepto += " (con cuidador de la mascota)"
        if not self._pagar(j, costo, concepto):
            res.alerta = f"No alcanza: el viaje cuesta {D.dinero(costo)}."
            self._b_viaje(j, "", res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        ex = self._extras_hogar(h)
        ex["viaje"]["estado"] = "acordado"
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(v["de"], f"✈️ {self._firma(j)} aceptó el viaje: {self._texto_viaje(v)}. 🧳",
                                [[("✈️ Viaje", "viaje")]]))
        self._b_viaje(j, "", res, "🧳 ¡Viaje reservado!")

    def _b_viaje_no(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        v = ex.get("viaje")
        if v and v["estado"] == "propuesto" and v["de"] != j.id:
            ex.pop("viaje")
            self._guardar_extras_hogar(h, ex)
            res.avisos.append(Aviso(v["de"], f"🙈 {self._firma(j)} prefiere dejar el viaje para otro momento."))
        self._b_viaje(j, "", res)

    def _tick_viaje(self, res) -> None:
        """Empieza y termina los viajes según la fecha."""
        from .juego import Aviso

        ahora = self.reloj()
        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if len(miembros) < 2 or not h.casa:
                continue
            h = self._hogar(h.sala_id)
            v = self._viaje(h)
            if not v or v["estado"] != "acordado":
                continue
            hoy = self._local(miembros[0]).date().toordinal()
            emoji, nombre, dias, _ = DESTINOS[v["destino"]]
            if not v.get("empezo") and v["desde"] <= hoy <= v["hasta"]:
                for m in miembros:
                    self._vivir(m, ahora)
                    accion = self._accion(m)
                    if accion and accion["k"] == "trabajar":  # sale antes del trabajo: cobra lo hecho
                        self._cobrar_turno(m, accion, self._segundos_juego(m, ahora), completo=False)
                    m.accion = None
                    m.lugar = LUGAR
                    self.db.guardar_jugador(m)
                ex = self._extras_hogar(h)
                ex["viaje"]["empezo"] = True
                self._guardar_extras_hogar(h, ex)
                texto = (f"✈️ <b>¡Se van de viaje a {nombre}!</b> {emoji}\nEstos días no se trabaja y las necesidades "
                         f"no bajan. Vuelven el {self._fecha_texto(v['hasta'] + 1)}. ¡A disfrutar! 💞")
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto))
                res.ediciones += self._refrescar_sala(h.sala_id)
            elif v.get("empezo") and hoy > v["hasta"]:
                for m in miembros:
                    self._vivir(m, ahora)
                    if m.lugar == LUGAR:
                        m.lugar = V.HABITACION_INICIAL
                    self.db.guardar_jugador(m)
                    self._sumar_necesidades(m, {"diversion": 100, "energia": m.energia_max})
                ex = self._extras_hogar(h)
                ex.pop("viaje")
                ex["viajes"] = ex.get("viajes", 0) + 1
                recuerdo = {"tipo": "cita", "texto": f"{emoji} Viaje a {nombre} ({dias} días)", "ts": ahora}
                ex["recuerdos"] = (ex.get("recuerdos", []) + [recuerdo])[-50:]
                self._guardar_extras_hogar(h, ex)
                self._lograr_hito(h, "viaje")
                texto = (f"🏠 <b>Volvieron del viaje a {nombre}</b> {emoji}\n🎉 Diversión y ⚡ energía al máximo. "
                         "📸 El recuerdo quedó en el álbum.")
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("📸 Álbum", "album")]]))
                res.ediciones += self._refrescar_sala(h.sala_id)
            elif v["hasta"] < hoy:  # se pasó la fecha sin empezar (por ejemplo, nadie jugaba)
                ex = self._extras_hogar(h)
                ex.pop("viaje")
                self._guardar_extras_hogar(h, ex)
