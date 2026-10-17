"""Eventos sorpresa dentro del juego (actualización 2, parte 9).

`EventosMixin` se mezcla con `Juego`. Uno o dos por semana, al azar, llega un evento bueno, malo
o de pareja, y les llega un aviso a los dos.

En `extras` del hogar: "eventos" {proximo, historial} y lo que dura cada evento: "oferta_hasta",
"lluvia_hasta" y "apagon_hasta" (hora real), "averias" {cosa: costo}, "visita" {hasta, limpio,
cocino} y "antojo" {de, receta, hasta, cumplido}. En `extras` del jugador: "resfriado_hasta"
(fecha local, incluida).
"""

from __future__ import annotations

import json

from . import cocina as C
from . import dinero as D
from . import eventos as E
from . import vida as V
from .db import Hogar, Jugador

HISTORIAL = 20


class EventosMixin:
    # ------------------------------------------------------------------
    # Lo que está pasando
    # ------------------------------------------------------------------

    def _fin_del_dia(self, j: Jugador) -> float:
        local = self._local(j)
        return self.reloj() + (V.DIA - (local.hour * 3600 + local.minute * 60 + local.second))

    def _bloqueo_evento(self, j: Jugador, a: V.Accion) -> str | None:
        """Si un evento impide la acción (apagón, lluvia, avería), el motivo."""
        viaje = self._de_viaje(j)
        if viaje:
            return "✈️ Están de viaje: ¡a disfrutar! Las cosas de la casa esperan a que vuelvan."
        ex = self._extras_hogar(self._hogar(j.sala_id))
        ahora = self.reloj()
        if a.clave in E.APAGON and ex.get("apagon_hasta", 0) > ahora:
            return f"⚡ Hay un apagón hasta las {self._hora(j, ex['apagon_hasta'])}: no hay tele, internet ni lavadora."
        if a.clave in E.SALIDAS and ex.get("lluvia_hasta", 0) > ahora:
            return "🌧️ Hoy llueve a cántaros: se cancela el plan de salir. ¡Plan en casa! 🍿"
        for cosa, costo in ex.get("averias", {}).items():
            emoji, nombre, acciones, _ = E.AVERIAS[cosa]
            if a.clave in acciones:
                return f"{emoji} Se rompió {nombre}. Pueden arreglarla en 🏠 Casa ({D.dinero(costo)})."
        return None

    def _oferta_super(self, j: Jugador) -> bool:
        return self._extras_hogar(self._hogar(j.sala_id)).get("oferta_hasta", 0) > self.reloj()

    def _resfriado(self, j: Jugador) -> bool:
        return self._extras(j).get("resfriado_hasta", 0) >= self._hoy(j)

    def _eventos_activos(self, j: Jugador) -> list[str]:
        """Líneas cortas con los eventos que siguen en curso, para el menú."""
        from .juego import duracion

        ex = self._extras_hogar(self._hogar(j.sala_id))
        ahora = self.reloj()
        lineas = []
        if ex.get("oferta_hasta", 0) > ahora:
            lineas.append("🛒 Hoy el súper está a mitad de precio")
        if ex.get("lluvia_hasta", 0) > ahora:
            lineas.append("🌧️ Hoy llueve: no se puede salir")
        if ex.get("apagon_hasta", 0) > ahora:
            lineas.append(f"⚡ Apagón hasta las {self._hora(j, ex['apagon_hasta'])}")
        for cosa in ex.get("averias", {}):
            emoji, nombre, _, _ = E.AVERIAS[cosa]
            lineas.append(f"{emoji} Se rompió {nombre}")
        visita = ex.get("visita")
        if visita:
            falta = [t for t, hecho in (("🧹 limpiar la sala", visita["limpio"]), ("🍳 cocinar", visita["cocino"])) if not hecho]
            lineas.append(f"👨‍👩‍👧 Visita familiar: falta {' y '.join(falta)} ({duracion(visita['hasta'] - ahora)})")
        antojo = ex.get("antojo")
        if antojo:
            de = self.db.jugador(antojo["de"])
            receta = C.RECETAS[antojo["receta"]]
            quien = "Tienes" if de and de.id == j.id else f"{de.personaje if de else '…'} tiene"
            lineas.append(f"🤤 {quien} antojo de {receta.nombre.lower()} ({duracion(antojo['hasta'] - ahora)})")
        if self._resfriado(j):
            como = {"mujer": "resfriada", "nobinario": "con resfriado"}.get(j.ap.get("genero"), "resfriado")
            lineas.append(f"🤒 Estás {como}: hoy no trabajas")
        return lineas

    def _sumar_necesidades(self, m: Jugador, cambios: dict) -> None:
        ahora = self.reloj()
        self._vivir(m, ahora)
        nec = self._nec(m)
        for clave, valor in cambios.items():
            nec[clave] = max(0, min(V.maximo(clave, m.energia_max), nec.get(clave, 0) + valor))
        m.necesidades = json.dumps(nec)
        self.db.guardar_jugador(m)

    # ------------------------------------------------------------------
    # Lo que hacen los jugadores y cuenta para un evento
    # ------------------------------------------------------------------

    def _evento_limpio(self, h: Hogar, zona: str) -> None:
        ex = self._extras_hogar(h)
        if ex.get("visita") and zona == "salon":
            ex["visita"]["limpio"] = True
            self._guardar_extras_hogar(h, ex)

    def _evento_cocinado(self, h: Hogar, coccion: dict) -> None:
        ex = self._extras_hogar(h)
        cambio = False
        if ex.get("visita"):
            ex["visita"]["cocino"] = True
            cambio = True
        antojo = ex.get("antojo")
        if antojo and coccion["receta"] == antojo["receta"] and any(c != antojo["de"] for c in coccion["cocineros"]):
            antojo["cumplido"] = True
            cambio = True
        if cambio:
            self._guardar_extras_hogar(h, ex)

    def _b_arreglar(self, j: Jugador, cosa: str, res) -> None:
        """arreglar:<cosa>: pagar el arreglo de una avería."""
        h = self._hogar(j.sala_id)
        costo = self._extras_hogar(h).get("averias", {}).get(cosa)
        if costo is None:
            res.alerta = "Eso ya está arreglado."
            self._b_casa(j, "", res)
            return
        emoji, nombre, _, _ = E.AVERIAS[cosa]
        if not self._pagar(j, costo, f"🔧 Arreglo de {nombre}"):
            res.alerta = f"No alcanza: el arreglo cuesta {D.dinero(costo)}."
            self._b_casa(j, "", res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        ex = self._extras_hogar(h)
        ex["averias"].pop(cosa, None)
        self._guardar_extras_hogar(h, ex)
        self._b_casa(j, "", res, f"🔧 ¡Arreglaron {nombre}! {emoji} Ya funciona.")

    # ------------------------------------------------------------------
    # Cada minuto
    # ------------------------------------------------------------------

    def _tick_eventos(self, res) -> None:
        from .juego import Aviso

        if not self.cfg.eventos:
            return
        ahora = self.reloj()
        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if not miembros or not h.casa:
                continue
            h = self._hogar(h.sala_id)  # al día después de que los Sims vivieron este minuto
            self._seguir_eventos(h, miembros, res)
            ex = self._extras_hogar(h)
            ev = ex.setdefault("eventos", {})
            if "proximo" not in ev:
                ev["proximo"] = E.siguiente(ahora, self.rng)
                self._guardar_extras_hogar(h, ex)
                continue
            if ahora < ev["proximo"]:
                continue
            ev["proximo"] = E.siguiente(ahora, self.rng)
            self._guardar_extras_hogar(h, ex)
            if all(ahora - m.ultima_actividad > E.SIN_JUGAR for m in miembros):
                continue  # nadie juega: no se acumulan sorpresas
            con_trabajo = [m for m in miembros if self._empleo(m).get("clave")]
            con_videos = any(self._influ(m).get("videos") for m in miembros)
            evento = E.elegir(self.rng, len(miembros) > 1, bool(con_trabajo), con_videos)
            textos, botones = self._lanzar_evento(h, evento, miembros, con_trabajo)
            ex = self._extras_hogar(h)
            ex["eventos"]["historial"] = (ex["eventos"].get("historial", []) + [{"clave": evento.clave, "ts": ahora}])[-HISTORIAL:]
            self._guardar_extras_hogar(h, ex)
            for m in miembros:
                res.avisos.append(Aviso(m.id, f"🎲 <b>Evento sorpresa</b>\n{textos[m.id]}", botones))
            res.ediciones += self._refrescar_sala(h.sala_id)

    def _lanzar_evento(self, h: Hogar, evento: E.Evento, miembros: list[Jugador],
                       con_trabajo: list[Jugador]) -> tuple[dict, list]:
        """Aplica el evento. Devuelve el texto para cada miembro y los botones del aviso."""
        ahora = self.reloj()
        rng = self.rng
        ex = self._extras_hogar(h)
        botones = []
        texto = ""
        if evento.clave == "bono":
            m = rng.choice(con_trabajo)
            monto = rng.randint(*E.BONO)
            m.cartera += monto
            self.db.guardar_jugador(m)
            self._anotar_movimiento(h.sala_id, m.id, "cartera", monto, "💼 Bono en el trabajo")
            texto = f"💼🎉 <b>Bono en el trabajo</b>: {self._firma(m)} recibió {D.dinero(monto)} en su cartera."
        elif evento.clave == "viral":
            m = rng.choice([x for x in miembros if self._influ(x).get("videos")])
            nuevos = rng.randint(*E.VIRAL)
            datos = self._influ(m)
            datos["seguidores"] += nuevos
            self._guardar_influ(m, datos)
            texto = f"📱🔥 <b>¡Video viral!</b> Un video de {self._firma(m)} explotó: +{nuevos} seguidores de golpe."
            botones = [[("📱 Influencer", "influ")]]
        elif evento.clave == "oferta":
            ex["oferta_hasta"] = self._fin_del_dia(miembros[0])
            texto = "🛒🎉 <b>Oferta en el súper</b>: hoy toda la compra está a mitad de precio."
            botones = [[("🛒 Ir al súper", "a:super")]]
        elif evento.clave == "regalo":
            m = rng.choice(miembros)
            self._sumar_necesidades(m, E.REGALO)
            texto = f"🎁 <b>Regalo sorpresa</b> para {self._firma(m)}: ¡le sube el ánimo! (+20 🎉 diversión, +10 💬 social)"
        elif evento.clave == "averia":
            cosa = rng.choice(list(E.AVERIAS))
            costo = rng.randint(*E.AVERIA)
            ex.setdefault("averias", {})[cosa] = costo
            emoji, nombre, _, sin = E.AVERIAS[cosa]
            texto = (f"🔧 <b>Avería</b>: se rompió {nombre} {emoji}: {sin}. Arreglarla cuesta {D.dinero(costo)}; "
                     "también pueden dejarla así.")
            botones = [[(f"🔧 Arreglar ({D.dinero(costo)})", f"arreglar:{cosa}"), ("🏡 Casa", "casa")]]
        elif evento.clave == "resfriado":
            m = rng.choice(miembros)
            dias = rng.randint(*E.RESFRIADO_DIAS)
            extras = self._extras(m)
            extras["resfriado_hasta"] = self._hoy(m) + dias - 1
            m.extras = json.dumps(extras)
            self.db.guardar_jugador(m)
            self._sumar_necesidades(m, {"energia": -E.RESFRIADO_ENERGIA})
            cuando = "hoy" if dias == 1 else "hoy ni mañana"
            texto = (f"🤒 <b>Resfriado</b>: {self._firma(m)} amaneció con gripe: tiene menos energía "
                     f"(−{E.RESFRIADO_ENERGIA}) y no trabaja {cuando}.")
        elif evento.clave == "apagon":
            horas = rng.randint(*E.APAGON_HORAS)
            ex["apagon_hasta"] = ahora + horas * V.HORA
            texto = f"⚡ <b>Apagón</b>: sin tele, internet ni lavadora durante unas {horas} horas."
        elif evento.clave == "multa":
            concepto = rng.choice(E.MULTAS)
            costo = rng.randint(*E.MULTA)
            if h.cuenta >= costo:
                h.cuenta -= costo
                self._anotar_movimiento(h.sala_id, None, "compartida", -costo, concepto)
                texto = f"💸 <b>Gasto inesperado</b>: {concepto}: {D.dinero(costo)}, pagado de la cuenta compartida."
            else:
                pendientes = json.loads(h.pendientes)
                pendientes.append({"clave": "imprevisto", "monto": costo, "concepto": concepto})
                h.pendientes = json.dumps(pendientes)
                texto = (f"💸 <b>Gasto inesperado</b>: {concepto}: {D.dinero(costo)}. No alcanzó la cuenta: "
                         "queda pendiente en 💰 Dinero → Facturas.")
            botones = [[("💰 Dinero", "dinero")]]
        elif evento.clave == "lluvia":
            ex["lluvia_hasta"] = self._fin_del_dia(miembros[0])
            texto = ("🌧️ <b>Día de lluvia</b>: hoy se cancela el plan de salir (parque, cine, restaurante y "
                     "gimnasio). ¡Plan en casa! 🍿")
        elif evento.clave == "visita":
            ex["visita"] = {"hasta": ahora + E.VISITA_HORAS * V.HORA, "limpio": False, "cocino": False}
            texto = ("👨‍👩‍👧 <b>Visita familiar</b>: mañana viene la familia. Antes de 24 h hay que 🧹 limpiar la sala "
                     "y 🍳 cocinar algo.")
            botones = [[("🧹 Limpiar", "a:limpiar:salon"), ("🍳 Cocinar", "a:cocinar")]]
        elif evento.clave == "antojo":
            de = rng.choice(miembros)
            otro = next(m for m in miembros if m.id != de.id)
            receta = rng.choice([r for r in C.RECETAS.values() if r.nivel <= self._nivel_super(h)])
            ex["antojo"] = {"de": de.id, "receta": receta.clave, "hasta": ahora + E.ANTOJO_HORAS * V.HORA,
                            "cumplido": False}
            texto = (f"🤤 <b>Antojo</b>: a {self._firma(de)} se le antoja {receta.emoji} {receta.nombre.lower()}. "
                     f"Si {self._firma(otro)} se lo prepara antes de 24 h, sube la relación 💗.")
            botones = [[("🍳 Ver la receta", f"rec:{receta.clave}")]]
        h.extras = json.dumps(ex)
        self.db.guardar_hogar(h)
        if evento.clave == "pregunta":
            para = rng.choice(miembros)
            pregunta = self._nueva_pregunta(h, para=para, por=None)
            textos = {m.id: f"❓ <b>Pregunta de pareja</b>\n{self._texto_pregunta(m, pregunta)}" for m in miembros}
            return textos, [[("✍️ Responder", "pregr")]]
        return {m.id: texto for m in miembros}, botones

    def _seguir_eventos(self, h: Hogar, miembros: list[Jugador], res) -> None:
        """Cierra lo que terminó: la visita, el antojo y el apagón."""
        from .juego import Aviso

        ex = self._extras_hogar(h)
        ahora = self.reloj()
        noticias = []
        antes = json.dumps(ex)
        visita = ex.get("visita")
        if visita and visita["limpio"] and visita["cocino"]:
            for m in miembros:
                self._sumar_necesidades(m, E.VISITA_BIEN)
            noticias.append("👨‍👩‍👧 ¡La visita fue un éxito! La familia se fue feliz (+10 💬 social, +5 🎉 diversión).")
            ex.pop("visita")
        elif visita and ahora >= visita["hasta"]:
            for m in miembros:
                self._sumar_necesidades(m, E.VISITA_MAL)
            noticias.append("👨‍👩‍👧 La familia se fue con cara rara: la casa no estaba lista 😬 (−10 🎉 diversión).")
            ex.pop("visita")
        antojo = ex.get("antojo")
        if antojo and antojo["cumplido"]:
            de = self.db.jugador(antojo["de"])
            otro = next((m for m in miembros if m.id != antojo["de"]), None)
            subio = self._cambiar_relacion(de, E.ANTOJO_RELACION, "🤤 Me preparó mi antojo", auto=True) if de else 0
            noticias.append(f"🤤💗 ¡{self._firma(otro) if otro else 'Alguien'} le preparó su antojo a "
                            f"{self._firma(de) if de else '…'}! (+{subio} en su medidor)")
            ex.pop("antojo")
        elif antojo and ahora >= antojo["hasta"]:
            de = self.db.jugador(antojo["de"])
            noticias.append(f"🤤 A {self._firma(de) if de else '…'} se le pasó el antojo.")
            ex.pop("antojo")
        if ex.get("apagon_hasta") and ahora >= ex["apagon_hasta"]:
            ex.pop("apagon_hasta")
            noticias.append("💡 Volvió la luz.")
        for clave in ("oferta_hasta", "lluvia_hasta"):  # terminan sin aviso
            if ex.get(clave) and ahora >= ex[clave]:
                ex.pop(clave)
        if json.dumps(ex) != antes:
            self._guardar_extras_hogar(h, ex)
        if noticias:
            for m in miembros:
                res.avisos.append(Aviso(m.id, "\n".join(noticias)))
