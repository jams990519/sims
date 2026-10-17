"""Compromiso y boda: los hitos más grandes (actualización 2, parte 12).

`BodaMixin` se mezcla con `Juego`.
- Compromiso: con el medidor de los dos por encima del 80 %, el primer viaje hecho y un anillo
  ($500 a $2.000, comprado en secreto). La pedida llega por sorpresa y el otro responde sí o no.
  Si es no, se conserva el anillo para otro momento.
- Boda: estando comprometidos, planifican lugar, invitados, comida y fecha ($2.000 a $10.000).
  Ese día, con los dos conectados, cada uno dice «sí, acepto». Quedan casados, pueden hacer una
  luna de miel (un viaje) y, si los dos quieren, unir el dinero: los sueldos van a la cuenta compartida.

En `extras` del hogar: "anillos" {jugador: anillo}, "pedida", "compromiso", "boda", "casados",
"unir" (propuesta) y "dinero_unido".
"""

from __future__ import annotations

from . import dinero as D
from .db import Hogar, Jugador

MINIMO_RELACION = 80
ANILLOS = {
    "sencillo": ("💍 Anillo sencillo", 500),
    "brillante": ("💎 Anillo con brillante", 1000),
    "ensueno": ("👑 Anillo de ensueño", 2000),
}
BASE_BODA = 1300  # trámites, anillos de boda y fotos
LUGARES = {
    "juzgado": ("🏛️ En el juzgado", 500),
    "jardin": ("🌳 En un jardín", 1500),
    "salon": ("🎊 En un salón de fiestas", 3000),
    "playa": ("🏖️ En la playa", 4000),
}
INVITADOS = {
    "solos": ("💑 Solo nosotros y los testigos", 0),
    "familia": ("👨‍👩‍👧 La familia (20 personas)", 1000),
    "grande": ("🎉 Una boda grande (80 personas)", 2700),
}
COMIDAS = {
    "pastel": ("🍰 Pastel y brindis", 200),
    "cena": ("🍽️ Una cena", 1500),
    "banquete": ("🥂 Un banquete", 2000),
}
PLAZOS = (3, 7, 14, 30)  # días hasta la boda
POSPONER = 7


def total_boda(lugar: str, invitados: str, comida: str) -> int:
    return BASE_BODA + LUGARES[lugar][1] + INVITADOS[invitados][1] + COMIDAS[comida][1]


class BodaMixin:
    def _estado_pareja(self, h: Hogar) -> str:
        """'casados', 'comprometidos' o ''."""
        ex = self._extras_hogar(h)
        return "casados" if ex.get("casados") else "comprometidos" if ex.get("compromiso") else ""

    def _dinero_unido(self, j: Jugador) -> bool:
        return j.sala_id is not None and bool(self._extras_hogar(self._hogar(j.sala_id)).get("dinero_unido"))

    # ------------------------------------------------------------------
    # Compromiso
    # ------------------------------------------------------------------

    def _b_compromiso(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """🏆 Hitos → 💍 Compromiso."""
        from .juego import Pantalla, esc

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "El compromiso es para jugar en pareja."
            self._b_menu_pareja(j, "", res)
            return
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        lineas = [aviso, ""] if aviso else []
        lineas.append("💍 <b>Compromiso</b>")
        botones = []
        estado = self._estado_pareja(h)
        if estado:
            desde = self._local(j, ex["compromiso"]["ts"])
            lineas.append(f"💍 Están comprometidos desde el {desde.day}/{desde.month}. ¡Felicidades!")
            if estado == "casados":
                lineas.append("💒 Y ya se casaron.")
            botones.append([("💒 La boda", "boda")])
        else:
            yo, otro = self._relacion(j), self._relacion(pareja)
            viaje = "viaje" in ex.get("hitos", {})
            anillo = ex.get("anillos", {}).get(str(j.id))
            lineas += [
                "Requisitos:",
                f"{'✅' if yo > MINIMO_RELACION else '❌'} Tu medidor por encima del {MINIMO_RELACION} % (ahora {yo} %)",
                f"{'✅' if otro > MINIMO_RELACION else '❌'} El de {esc(pareja.personaje)} por encima del {MINIMO_RELACION} % (ahora {otro} %)",
                f"{'✅' if viaje else '❌'} Haber hecho su primer viaje",
                f"{'✅ ' + ANILLOS[anillo][0] if anillo else '❌ Un anillo ($500 a $2.000, en secreto)'}",
            ]
            pedida = ex.get("pedida")
            if pedida and pedida["de"] == j.id:
                lineas += ["", "⏳ Ya se lo pediste… esperando su respuesta 🤞"]
            elif pedida:
                botones.append([("💍 ¡Sí, quiero!", "compsi"), ("🙈 Todavía no", "compno")])
            elif not anillo:
                botones.append([("💍 Comprar un anillo (en secreto)", "compa")])
            elif yo > MINIMO_RELACION and otro > MINIMO_RELACION and viaje:
                botones.append([("💍 Pedir matrimonio", "comppe")])
        botones.append([("🏆 Hitos", "hitos"), ("⬅️ Atrás", "mpar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="comp")

    def _b_comprar_anillo(self, j: Jugador, arg: str, res) -> None:
        """compa · compa:<anillo>: se paga de tu cartera; si no alcanza, de la compartida (como «compra secreta»)."""
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        if self._estado_pareja(h) or self._extras_hogar(h).get("anillos", {}).get(str(j.id)):
            self._b_compromiso(j, "", res)
            return
        if arg not in ANILLOS:
            res.pantalla = Pantalla(
                "💍 ¿Qué anillo? Es un secreto: tu pareja no se entera hasta la pedida 🤫",
                [[(f"{nombre} · {D.dinero(precio)}", f"compa:{clave}")] for clave, (nombre, precio) in ANILLOS.items()]
                + [[("⬅️ Atrás", "comp")]],
                clave="comp",
            )
            return
        nombre, precio = ANILLOS[arg]
        if j.cartera >= precio:
            j.cartera -= precio
            self.db.guardar_jugador(j)
            self._anotar_movimiento(j.sala_id, j.id, "cartera", -precio, "🤫 Una compra secreta")
        elif not self._pagar(j, precio, "🤫 Una compra secreta"):
            res.alerta = f"No alcanza: {nombre.lower()} cuesta {D.dinero(precio)}."
            self._b_compromiso(j, "", res)
            return
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        ex.setdefault("anillos", {})[str(j.id)] = arg
        self._guardar_extras_hogar(h, ex)
        self._b_compromiso(j, "", res, f"{nombre} guardado en secreto 🤫")

    def _b_pedir(self, j: Jugador, arg: str, res) -> None:
        """comppe: la pedida, por sorpresa."""
        from .juego import Aviso

        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        anillo = ex.get("anillos", {}).get(str(j.id))
        listo = (
            pareja is not None and anillo and not self._estado_pareja(h) and not ex.get("pedida")
            and "viaje" in ex.get("hitos", {}) and self._relacion(j) > MINIMO_RELACION
            and self._relacion(pareja) > MINIMO_RELACION
        )
        if not listo:
            res.alerta = "Todavía no se cumplen los requisitos."
            self._b_compromiso(j, "", res)
            return
        ex["pedida"] = {"de": j.id, "anillo": anillo, "ts": self.reloj()}
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(
            pareja.id,
            f"💍✨ <b>{self._firma(j)} se arrodilla frente a ti…</b>\n\n"
            f"Abre una cajita con {ANILLOS[anillo][0].lower()} y te pregunta:\n<b>¿Quieres casarte conmigo?</b>",
            [[("💍 ¡Sí, quiero!", "compsi"), ("🙈 Todavía no", "compno")]],
        ))
        self._b_compromiso(j, "", res, "💍 Se lo pediste… ¡ahora a esperar su respuesta! 🤞")

    def _b_respuesta_pedida(self, j: Jugador, si: bool, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        pedida = ex.get("pedida")
        if not pedida or pedida["de"] == j.id:
            res.alerta = "No hay ninguna pedida pendiente."
            self._b_compromiso(j, "", res)
            return
        ex.pop("pedida")
        if si:
            ex["compromiso"] = {"de": pedida["de"], "anillo": pedida["anillo"], "ts": self.reloj()}
            ex.get("anillos", {}).pop(str(pedida["de"]), None)
            self._guardar_extras_hogar(h, ex)
            self._lograr_hito(h, "compromiso")
            res.avisos.append(Aviso(pedida["de"], f"💍🎉 <b>¡{self._firma(j)} dijo que SÍ!</b> Están comprometidos.",
                                    [[("💒 Planear la boda", "boda")]]))
            self._b_compromiso(j, "", res, "💍🎉 <b>¡Están comprometidos!</b> Cuando quieran, planeen la boda.")
            return
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(pedida["de"], f"🙈 {self._firma(j)} dijo que todavía no. Guardas el anillo 💍 "
                                              "para cuando llegue el momento."))
        self._b_compromiso(j, "", res, "🙈 Le dijiste que todavía no. El anillo se lo queda para otro momento.")

    def _b_pedida_si(self, j: Jugador, arg: str, res) -> None:
        self._b_respuesta_pedida(j, True, res)

    def _b_pedida_no(self, j: Jugador, arg: str, res) -> None:
        self._b_respuesta_pedida(j, False, res)

    # ------------------------------------------------------------------
    # Boda
    # ------------------------------------------------------------------

    def _texto_boda(self, b: dict) -> list[str]:
        return [
            f"{LUGARES[b['lugar']][0]} · {INVITADOS[b['invitados']][0]} · {COMIDAS[b['comida']][0]}",
            f"📅 El {self._fecha_texto(b['dia'])} · 💵 {D.dinero(b['total'])}",
        ]

    def _b_boda(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💒 Boda · bodap:… para planearla."""
        from .juego import Pantalla

        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        if pareja is None or not ex.get("compromiso"):
            res.alerta = "Para la boda primero tienen que estar comprometidos 💍."
            if pareja:
                self._b_compromiso(j, "", res)
            else:
                self._b_menu_pareja(j, "", res)
            return
        b = ex.get("boda")
        lineas = [aviso, ""] if aviso else []
        lineas.append("💒 <b>La boda</b>")
        botones = []
        if ex.get("casados"):
            desde = self._local(j, ex["casados"])
            lineas.append(f"💒 Están casados desde el {desde.day}/{desde.month}. 💞")
            botones.append([("🌙 Luna de miel (un viaje)", "viaje")])
            if ex.get("dinero_unido"):
                lineas.append("💰 Unieron el dinero: los sueldos van a la cuenta compartida.")
            elif ex.get("unir"):
                if ex["unir"] != j.id:
                    botones.append([("💰 Sí, unamos el dinero", "unirok")])
                else:
                    lineas.append("⏳ Propusiste unir el dinero: esperando que acepte.")
            else:
                botones.append([("💰 Unir el dinero", "unir")])
        elif b and b["estado"] == "acordada":
            lineas += self._texto_boda(b)
            if self._hoy(j) == b["dia"]:
                lineas += ["", "💒 <b>¡Hoy es el día!</b> Con los dos conectados, cada uno dice «sí, acepto»."]
                lineas.append(f"💍 Han dicho que sí: {len(b['si'])}/2")
                if j.id not in b["si"]:
                    botones.append([("💍 Sí, acepto", "bodasi")])
            else:
                lineas.append(f"⏳ Faltan {b['dia'] - self._hoy(j)} día(s). Ese día, conéctense los dos.")
        elif b and b["estado"] == "propuesta":
            lineas += ["💌 Plan propuesto:"] + self._texto_boda(b)
            if b["de"] != j.id:
                botones.append([("✅ Aceptar el plan", "bodaok"), ("✏️ Proponer otro", "bodap")])
            else:
                lineas.append("⏳ Esperando que acepte.")
        else:
            lineas.append("Planeen juntos el lugar, los invitados, la comida y la fecha (de $2.000 a $10.000).")
            botones.append([("📝 Planear la boda", "bodap")])
        botones.append([("💍 Compromiso", "comp"), ("⬅️ Atrás", "hitos")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="boda")

    def _b_boda_plan(self, j: Jugador, arg: str, res) -> None:
        """bodap[:lugar[:invitados[:comida[:dias]]]]"""
        from .juego import Aviso, Pantalla

        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        if pareja is None or not ex.get("compromiso") or ex.get("casados") or (ex.get("boda") or {}).get("estado") == "acordada":
            self._b_boda(j, "", res)
            return
        partes = arg.split(":") if arg else []
        pasos = ((LUGARES, "🏛️ ¿Dónde se casan?"), (INVITADOS, "👥 ¿A quién invitan?"), (COMIDAS, "🍽️ ¿Qué comida?"))
        for i, (opciones, pregunta) in enumerate(pasos):
            if len(partes) <= i or partes[i] not in opciones:
                previo = ":".join(partes[:i])
                res.pantalla = Pantalla(
                    pregunta,
                    [[(f"{n} · {D.dinero(c) if c else 'gratis'}", f"bodap:{previo + ':' if previo else ''}{k}")]
                     for k, (n, c) in opciones.items()] + [[("⬅️ Atrás", "boda")]],
                    clave="boda",
                )
                return
        lugar, invitados, comida = partes[:3]
        total = total_boda(lugar, invitados, comida)
        if len(partes) < 4 or not partes[3].isdigit() or int(partes[3]) not in PLAZOS:
            previo = ":".join(partes[:3])
            res.pantalla = Pantalla(
                f"📅 ¿Cuándo? Total: {D.dinero(total)} (incluye trámites, anillos de boda y fotos: {D.dinero(BASE_BODA)}).",
                [[(f"En {d} días", f"bodap:{previo}:{d}") for d in PLAZOS], [("⬅️ Atrás", "boda")]],
                clave="boda",
            )
            return
        dia = self._hoy(j) + int(partes[3])
        ex["boda"] = {"lugar": lugar, "invitados": invitados, "comida": comida, "dia": dia, "total": total,
                      "estado": "propuesta", "de": j.id, "si": []}
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(
            pareja.id,
            f"💒 {self._firma(j)} propone el plan de la boda:\n" + "\n".join(self._texto_boda(ex["boda"])),
            [[("✅ Aceptar", "bodaok"), ("✏️ Proponer otro", "bodap")]],
        ))
        self._b_boda(j, "", res, "💌 Plan de boda propuesto.")

    def _b_boda_aceptar(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        b = self._extras_hogar(h).get("boda")
        if not b or b["estado"] != "propuesta" or b["de"] == j.id:
            res.alerta = "Ese plan ya no está."
            self._b_boda(j, "", res)
            return
        if not self._pagar(j, b["total"], "💒 La boda"):
            res.alerta = f"No alcanza: la boda cuesta {D.dinero(b['total'])}."
            self._b_boda(j, "", res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        ex = self._extras_hogar(h)
        ex["boda"]["estado"] = "acordada"
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(b["de"], f"💒 {self._firma(j)} aceptó: ¡se casan el {self._fecha_texto(b['dia'])}! 💍",
                                [[("💒 La boda", "boda")]]))
        self._b_boda(j, "", res, "💒 ¡Boda reservada!")

    def _b_boda_si(self, j: Jugador, arg: str, res) -> None:
        """bodasi: «sí, acepto», con los dos conectados."""
        from .juego import Aviso

        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        b = ex.get("boda")
        if not b or b["estado"] != "acordada" or self._hoy(j) != b["dia"] or pareja is None:
            res.alerta = "Hoy no es la boda."
            self._b_boda(j, "", res)
            return
        if self._estado_presencia(pareja, self.reloj()) != "en_linea":
            res.alerta = f"Para casarse tienen que estar los dos conectados: {pareja.personaje} no está en línea."
            self._b_boda(j, "", res)
            return
        if j.id not in b["si"]:
            b["si"].append(j.id)
        if len(b["si"]) < 2:
            self._guardar_extras_hogar(h, ex)
            res.avisos.append(Aviso(pareja.id, f"💍 {self._firma(j)} dijo: «Sí, acepto». ¡Te toca!",
                                    [[("💍 Sí, acepto", "bodasi")]]))
            self._b_boda(j, "", res)
            return
        b["estado"] = "hecha"
        ex["casados"] = self.reloj()
        self._guardar_extras_hogar(h, ex)
        self._lograr_hito(h, "boda")
        texto = ("💒🎉 <b>¡Se casaron!</b> " + LUGARES[b["lugar"]][0].lower() + ". ¡Vivan los novios! 💞\n"
                 "🌙 Si quieren, hagan una luna de miel (un viaje) y decidan si unen el dinero.")
        res.avisos.append(Aviso(pareja.id, texto, [[("💒 La boda", "boda")]]))
        self._b_boda(j, "", res, texto)

    def _b_unir(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        pareja = self._pareja_en_sala(j)
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        if pareja is None or not ex.get("casados") or ex.get("dinero_unido"):
            self._b_boda(j, "", res)
            return
        ex["unir"] = j.id
        self._guardar_extras_hogar(h, ex)
        res.avisos.append(Aviso(pareja.id, f"💰 {self._firma(j)} propone unir el dinero: las carteras pasan a la cuenta "
                                           "compartida y los sueldos van ahí. ¿Aceptas?", [[("💰 Sí, unamos el dinero", "unirok")]]))
        self._b_boda(j, "", res, "💌 Propuesta enviada.")

    def _b_unir_aceptar(self, j: Jugador, arg: str, res) -> None:
        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        if not ex.get("unir") or ex["unir"] == j.id or ex.get("dinero_unido"):
            self._b_boda(j, "", res)
            return
        for m in self.db.miembros_sala(j.sala_id):
            if m.cartera:
                h.cuenta += m.cartera
                self._anotar_movimiento(h.sala_id, m.id, "compartida", m.cartera, "💰 Unimos el dinero")
                m.cartera = 0
                self.db.guardar_jugador(m)
        ex.pop("unir")
        ex["dinero_unido"] = True
        self._guardar_extras_hogar(h, ex)
        self._b_boda(j, "", res, "💰 ¡Unieron el dinero! Todo va a la cuenta compartida.")

    def _tick_boda(self, res) -> None:
        """El día de la boda avisa; si pasó sin casarse, se pospone una semana."""
        from .juego import Aviso

        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if len(miembros) < 2 or not h.casa:
                continue
            h = self._hogar(h.sala_id)
            ex = self._extras_hogar(h)
            b = ex.get("boda")
            if not b or b["estado"] != "acordada":
                continue
            hoy = self._local(miembros[0]).date().toordinal()
            texto = None
            if hoy == b["dia"] and not b.get("avisado"):
                b["avisado"] = True
                texto = "💒 <b>¡Hoy es su boda!</b> Conéctense los dos y digan «sí, acepto». 💍"
            elif hoy > b["dia"]:
                b.update(dia=hoy + POSPONER, si=[], avisado=False)
                texto = f"💒 La boda no se celebró: se movió al {self._fecha_texto(b['dia'])}. Ese día, conéctense los dos."
            if texto:
                self._guardar_extras_hogar(h, ex)
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("💒 La boda", "boda")]]))
