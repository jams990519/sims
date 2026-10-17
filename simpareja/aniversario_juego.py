"""Aniversario mensual y recuerdos (actualización 2, parte 10).

`AniversarioMixin` se mezcla con `Juego`. Cada mes, el mismo día en que empezaron a jugar juntos,
cumplen un mes más:
- Aviso: tres días antes, a los dos.
- Planificación: deciden juntos el día (ese o moverlo), qué hacer (cena en casa, restaurante, cine
  o parque) y el presupuesto. Uno lo propone y el otro acepta; al aceptar se paga.
- Celebración: ese día, con los dos conectados, brindan 🥂 y se dan un regalo 🎁.
- Recompensa: +10 en el medidor de los dos, diversión y social, y un recuerdo en el álbum.
- Si no se celebra, no pasa nada grave: se pierde la recompensa.

Las citas (restaurante, cine o parque juntos) también quedan en el álbum.

En `extras` del hogar: "aniv" {n, fecha, dia, propuesta, plan, presupuesto, acordado, brindis,
regalos, avisos, hecho, perdido} y "recuerdos".
"""

from __future__ import annotations

import calendar
from datetime import date

from . import dinero as D
from .db import Hogar, Jugador

AVISO_DIAS = 3
RELACION = 10
PREMIO = {"diversion": 20, "social": 20}
RECUERDOS = 50
PLANES = {
    "casa": ("🕯️ Cena en casa", (0, 20, 40)),
    "restaurante": ("🍝 Restaurante", (40, 60, 80)),
    "cine": ("🎬 Cine", (25, 40)),
    "parque": ("🌳 Picnic en el parque", (0, 20)),
}
REGALOS = {
    "carta": ("💌 Una carta", 0),
    "chocolates": ("🍫 Chocolates", 10),
    "flores": ("🌹 Flores", 15),
    "peluche": ("🧸 Un peluche", 20),
    "perfume": ("✨ Un perfume", 50),
}
CITAS = {"restaurante": "🍝 Cena en el restaurante", "cine": "🎬 Cita en el cine", "parque": "🌳 Paseo por el parque"}


def sumar_meses(d: date, meses: int) -> date:
    anio, mes = divmod(d.month - 1 + meses, 12)
    anio += d.year
    return date(anio, mes + 1, min(d.day, calendar.monthrange(anio, mes + 1)[1]))


def proximo(desde: date, hoy: date, despues_de: int = 0) -> tuple[int, date]:
    """(meses que cumplen, fecha) del próximo aniversario desde hoy, después del número `despues_de`."""
    n = max(1, despues_de + 1)
    while sumar_meses(desde, n) < hoy:
        n += 1
    return n, sumar_meses(desde, n)


def texto_meses(n: int) -> str:
    if n % 12 == 0:
        return "1 año" if n == 12 else f"{n // 12} años"
    return "1 mes" if n == 1 else f"{n} meses"


class AniversarioMixin:
    # ------------------------------------------------------------------
    # Fechas
    # ------------------------------------------------------------------

    def _pareja_desde(self, miembros: list[Jugador]) -> date:
        """Desde cuándo juegan juntos: cuando entró el último de los dos."""
        return self._local(miembros[0], max(m.creado for m in miembros)).date()

    def _aniversario(self, h: Hogar, miembros: list[Jugador]) -> dict | None:
        """El aniversario en curso, al día (empieza uno nuevo cuando el anterior pasó)."""
        if len(miembros) < 2:
            return None
        ex = self._extras_hogar(h)
        st = ex.get("aniv")
        hoy = self._local(miembros[0]).date().toordinal()
        if st is None or (hoy > st["dia"] and (st.get("hecho") or st.get("perdido"))):
            n, fecha = proximo(self._pareja_desde(miembros), date.fromordinal(hoy), st["n"] if st else 0)
            st = {"n": n, "fecha": fecha.toordinal(), "dia": fecha.toordinal(), "propuesta": None, "plan": None,
                  "presupuesto": 0, "acordado": False, "brindis": [], "regalos": {}, "avisos": [],
                  "hecho": False, "perdido": False}
            ex["aniv"] = st
            self._guardar_extras_hogar(h, ex)
        return st

    def _guardar_aniv(self, h: Hogar, st: dict) -> None:
        ex = self._extras_hogar(h)
        ex["aniv"] = st
        self._guardar_extras_hogar(h, ex)

    def _miembros_activos(self, j: Jugador) -> list[Jugador]:
        return [m for m in self.db.miembros_sala(j.sala_id) if m.estado == "activo"]

    def _fecha_texto(self, ordinal: int) -> str:
        from . import vida as V

        d = date.fromordinal(ordinal)
        return f"{V.dia_semana(d.weekday()).lower()} {d.day}"

    # ------------------------------------------------------------------
    # Pantalla
    # ------------------------------------------------------------------

    def _b_aniversario(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💕 Pareja → 🎂 Aniversario."""
        from .juego import Pantalla, esc

        miembros = self._miembros_activos(j)
        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "El aniversario es para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        h = self._hogar(j.sala_id)
        st = self._aniversario(h, miembros)
        hoy = self._hoy(j)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"🎂 <b>Aniversario</b>: cumplen <b>{texto_meses(st['n'])}</b> juntos el {self._fecha_texto(st['fecha'])}.",
        ]
        botones = []
        if st["hecho"]:
            lineas.append("🎉 ¡Ya lo celebraron! Quedó en el 📸 álbum.")
        elif st["perdido"]:
            lineas.append("Esta vez no lo celebraron. No pasa nada: el próximo mes hay otra oportunidad.")
        elif st["acordado"]:
            plan = PLANES[st["plan"]][0]
            lineas.append(f"✅ Plan acordado: {plan} ({D.dinero(st['presupuesto'])}) el {self._fecha_texto(st['dia'])}.")
            if hoy == st["dia"]:
                lineas += ["", "🎉 <b>¡Hoy es el día!</b> Con los dos conectados: brinden y dense un regalo."]
                brindis = "✅" if len(st["brindis"]) == 2 else f"{len(st['brindis'])}/2"
                lineas.append(f"🥂 Brindis: {brindis}")
                for m in (j, pareja):
                    regalo = st["regalos"].get(str(m.id))
                    nombre = "Tu regalo" if m.id == j.id else f"El regalo de {esc(m.personaje)}"
                    lineas.append(f"🎁 {nombre}: {REGALOS[regalo][0] if regalo else '⏳'}")
                if j.id not in st["brindis"]:
                    botones.append([("🥂 Brindar", "anivb")])
                if str(j.id) not in st["regalos"]:
                    botones.append([("🎁 Dar un regalo", "anivr")])
            elif hoy < st["dia"]:
                lineas.append(f"⏳ Faltan {st['dia'] - hoy} día(s). Ese día, conéctense los dos para celebrar.")
        else:
            propuesta = st.get("propuesta")
            if propuesta:
                de = self.db.jugador(propuesta["de"])
                lineas.append(
                    f"💌 {esc(de.personaje) if de else '…'} propuso: {PLANES[propuesta['plan']][0]} "
                    f"({D.dinero(propuesta['presupuesto'])}) el {self._fecha_texto(propuesta['dia'])}."
                )
                if propuesta["de"] != j.id:
                    botones.append([("✅ Aceptar el plan", "anivok"), ("✏️ Proponer otro", "anivp")])
                else:
                    lineas.append("⏳ Esperando que acepte.")
            else:
                lineas.append("Decidan juntos qué hacer: uno propone el plan y el otro lo acepta.")
            if not botones:
                botones.append([("🎯 Proponer un plan", "anivp")])
        recuerdos = [r for r in self._extras_hogar(h).get("recuerdos", []) if r["tipo"] == "aniversario"]
        if recuerdos:
            lineas += ["", f"🎂 Han celebrado {len(recuerdos)} aniversario(s)."]
        botones.append([("📸 Álbum", "album"), ("⬅️ Atrás", "mpar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="aniv")

    def _b_aniv_plan(self, j: Jugador, arg: str, res) -> None:
        """anivp · anivp:<plan> · anivp:<plan>:<presupuesto> · anivp:<plan>:<presupuesto>:<día>."""
        from .juego import Aviso, Pantalla

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            self._b_aniversario(j, "", res)
            return
        h = self._hogar(j.sala_id)
        st = self._aniversario(h, self._miembros_activos(j))
        if st["acordado"] or st["hecho"] or st["perdido"]:
            self._b_aniversario(j, "", res)
            return
        partes = arg.split(":") if arg else []
        plan = partes[0] if partes and partes[0] in PLANES else None
        if plan is None:
            res.pantalla = Pantalla(
                "🎯 ¿Qué quieren hacer para celebrar?",
                [[(nombre, f"anivp:{clave}")] for clave, (nombre, _) in PLANES.items()] + [[("⬅️ Atrás", "aniv")]],
                clave="aniv",
            )
            return
        nombre, presupuestos = PLANES[plan]
        presupuesto = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() and int(partes[1]) in presupuestos else None
        if presupuesto is None:
            res.pantalla = Pantalla(
                f"{nombre}: ¿qué presupuesto? (sale de la cuenta compartida al aceptar)",
                [[(D.dinero(p) if p else "Gratis", f"anivp:{plan}:{p}") for p in presupuestos], [("⬅️ Atrás", "anivp")]],
                clave="aniv",
            )
            return
        hoy = self._hoy(j)
        dias = [d for d in (st["fecha"] - 1, st["fecha"], st["fecha"] + 1, st["fecha"] + 2) if d >= hoy]
        dia = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() and int(partes[2]) in dias else None
        if dia is None:
            res.pantalla = Pantalla(
                f"{nombre} ({D.dinero(presupuesto)}): ¿qué día? El aniversario es el {self._fecha_texto(st['fecha'])}.",
                [[((("🎂 " if d == st["fecha"] else "") + self._fecha_texto(d)), f"anivp:{plan}:{presupuesto}:{d}")
                  for d in dias], [("⬅️ Atrás", f"anivp:{plan}")]],
                clave="aniv",
            )
            return
        st["propuesta"] = {"de": j.id, "plan": plan, "presupuesto": presupuesto, "dia": dia}
        self._guardar_aniv(h, st)
        res.avisos.append(Aviso(
            pareja.id,
            f"🎂 {self._firma(j)} propone celebrar sus {texto_meses(st['n'])} el {self._fecha_texto(dia)}: "
            f"{nombre} ({D.dinero(presupuesto)}). ¿Te parece?",
            [[("✅ Aceptar", "anivok"), ("✏️ Proponer otro", "anivp")]],
        ))
        self._b_aniversario(j, "", res, "💌 Plan propuesto. Cuando tu pareja lo acepte, queda listo.")

    def _b_aniv_aceptar(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        st = self._aniversario(h, self._miembros_activos(j))
        propuesta = st.get("propuesta") if st else None
        if not propuesta or propuesta["de"] == j.id or st["acordado"] or propuesta["dia"] < self._hoy(j):
            res.alerta = "Esa propuesta ya no está."
            self._b_aniversario(j, "", res)
            return
        nombre = PLANES[propuesta["plan"]][0]
        if propuesta["presupuesto"] and not self._pagar(j, propuesta["presupuesto"], f"🎂 Aniversario: {nombre}"):
            res.alerta = f"No alcanza: el plan cuesta {D.dinero(propuesta['presupuesto'])}."
            self._b_aniversario(j, "", res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        st = self._aniversario(h, self._miembros_activos(j))
        st.update(plan=propuesta["plan"], presupuesto=propuesta["presupuesto"], dia=propuesta["dia"],
                  acordado=True, propuesta=None)
        self._guardar_aniv(h, st)
        res.avisos.append(Aviso(
            propuesta["de"],
            f"🎂 {self._firma(j)} aceptó: {nombre} el {self._fecha_texto(st['dia'])}. ¡Ese día conéctense los dos!",
            [[("🎂 Aniversario", "aniv")]],
        ))
        self._b_aniversario(j, "", res, "✅ ¡Plan acordado!")

    def _celebrando(self, j: Jugador, res) -> tuple[Hogar, dict, Jugador] | None:
        """Comprueba que hoy se puede celebrar y que los dos están conectados."""
        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        st = self._aniversario(h, self._miembros_activos(j)) if pareja else None
        if not st or not st["acordado"] or st["hecho"] or self._hoy(j) != st["dia"]:
            res.alerta = "Hoy no toca celebrar."
            self._b_aniversario(j, "", res)
            return None
        if self._estado_presencia(pareja, self.reloj()) != "en_linea":
            res.alerta = f"Para celebrar tienen que estar los dos conectados: {pareja.personaje} no está en línea."
            self._b_aniversario(j, "", res)
            return None
        return h, st, pareja

    def _b_aniv_brindis(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        listo = self._celebrando(j, res)
        if listo is None:
            return
        h, st, pareja = listo
        if j.id not in st["brindis"]:
            st["brindis"].append(j.id)
            self._guardar_aniv(h, st)
            if len(st["brindis"]) < 2:
                res.avisos.append(Aviso(pareja.id, f"🥂 {self._firma(j)} levantó su copa: ¡choca la tuya!",
                                        [[("🥂 Brindar", "anivb")]]))
            else:
                res.avisos.append(Aviso(pareja.id, "🥂 ¡Chin chin! Brindaron por su aniversario."))
        self._completar_aniversario(h, st, j, pareja, res)

    def _b_aniv_regalo(self, j: Jugador, arg: str, res) -> None:
        """anivr · anivr:<regalo>."""
        from .juego import Aviso, Pantalla

        listo = self._celebrando(j, res)
        if listo is None:
            return
        h, st, pareja = listo
        if str(j.id) in st["regalos"]:
            self._b_aniversario(j, "", res)
            return
        if arg not in REGALOS:
            res.pantalla = Pantalla(
                f"🎁 ¿Qué le regalas a {pareja.personaje}?",
                [[(f"{n} · {D.dinero(c) if c else 'gratis'}", f"anivr:{k}")] for k, (n, c) in REGALOS.items()]
                + [[("⬅️ Atrás", "aniv")]],
                clave="aniv",
            )
            return
        nombre, costo = REGALOS[arg]
        if costo:
            if j.cartera >= costo:
                j.cartera -= costo
                self.db.guardar_jugador(j)
                self._anotar_movimiento(j.sala_id, j.id, "cartera", -costo, f"🎁 Regalo: {nombre}")
            elif not self._pagar(j, costo, f"🎁 Regalo: {nombre}"):
                res.alerta = f"No alcanza para {nombre.lower()} ({D.dinero(costo)})."
                self._b_aniversario(j, "", res)
                return
            h = self._hogar(j.sala_id)
            st = self._aniversario(h, self._miembros_activos(j))
        st["regalos"][str(j.id)] = arg
        self._guardar_aniv(h, st)
        res.avisos.append(Aviso(pareja.id, f"🎁 {self._firma(j)} te regaló {nombre.lower()} 💞"))
        self._completar_aniversario(h, st, j, pareja, res)

    def _completar_aniversario(self, h: Hogar, st: dict, j: Jugador, pareja: Jugador, res) -> None:
        """Si ya brindaron y se dieron los regalos: la recompensa y el recuerdo."""
        from .juego import Aviso

        if len(st["brindis"]) < 2 or len(st["regalos"]) < 2:
            self._b_aniversario(j, "", res)
            return
        st["hecho"] = True
        motivo = f"🎂 Aniversario de {texto_meses(st['n'])}"
        for m in (j, pareja):
            self._cambiar_relacion(m, RELACION, motivo, auto=True)
            self._sumar_necesidades(m, PREMIO)
        regalos = " y ".join(REGALOS[r][0].lower() for r in st["regalos"].values())
        texto = f"🎂 {texto_meses(st['n'])} juntos: {PLANES[st['plan']][0].lower()}, brindis y {regalos}"
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        ex["aniv"] = st
        ex["recuerdos"] = (ex.get("recuerdos", []) + [{"tipo": "aniversario", "texto": texto, "ts": self.reloj()}])[-RECUERDOS:]
        self._guardar_extras_hogar(h, ex)
        noticia = (f"🎂🎉 <b>¡Feliz aniversario de {texto_meses(st['n'])}!</b> Su medidor sube {RELACION} y "
                   "el recuerdo quedó en el 📸 álbum.")
        res.avisos.append(Aviso(pareja.id, noticia, [[("📸 Álbum", "album")]]))
        self._b_aniversario(j, "", res, noticia)

    # ------------------------------------------------------------------
    # Citas para el álbum y avisos de cada día
    # ------------------------------------------------------------------

    def _recordar_cita(self, j: Jugador, accion: dict) -> None:
        """Al terminar una salida juntos, queda en el álbum (una sola vez por cita)."""
        if accion["k"] not in CITAS or not accion.get("con"):
            return
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        recuerdos = ex.get("recuerdos", [])
        if any(r["tipo"] == "cita" and r.get("rini") == accion["rini"] for r in recuerdos):
            return
        recuerdos.append({"tipo": "cita", "texto": CITAS[accion["k"]], "ts": self.reloj(), "rini": accion["rini"]})
        ex["recuerdos"] = recuerdos[-RECUERDOS:]
        self._guardar_extras_hogar(h, ex)
        self._lograr_hito(h, "primera_cita")

    def _tick_aniversario(self, res) -> None:
        from .juego import Aviso

        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if len(miembros) < 2 or not h.casa:
                continue
            h = self._hogar(h.sala_id)
            st = self._aniversario(h, miembros)
            hoy = self._local(miembros[0]).date().toordinal()
            texto, clave = None, None
            meses = texto_meses(st["n"])
            if not st["hecho"] and not st["perdido"] and hoy > st["dia"]:
                st["perdido"] = True
                texto = (f"🎂 Esta vez no celebraron sus {meses}. No pasa nada grave: "
                         "el próximo mes hay otra oportunidad.")
            elif hoy == st["dia"] and not st["hecho"] and "dia" not in st["avisos"]:
                clave = "dia"
                texto = (f"🎂 <b>¡Hoy celebran {meses} juntos!</b> Conéctense los dos para brindar y darse un regalo."
                         if st["acordado"] else
                         f"🎂 <b>¡Hoy cumplen {meses} juntos!</b> Todavía no tienen plan: propongan uno y celébrenlo.")
            elif 0 < st["fecha"] - hoy <= AVISO_DIAS and "antes" not in st["avisos"] and not st["acordado"]:
                clave = "antes"
                texto = (f"🎂 En {st['fecha'] - hoy} día(s), el {self._fecha_texto(st['fecha'])}, cumplen {meses} "
                         "juntos. ¿Cómo lo celebran?")
            if texto is None:
                continue
            if clave:
                st["avisos"].append(clave)
            self._guardar_aniv(h, st)
            for m in miembros:
                res.avisos.append(Aviso(m.id, texto, [[("🎂 Aniversario", "aniv")]]))
