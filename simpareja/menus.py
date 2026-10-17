"""Menú principal y submenús (actualización 2, parte 1).

🏠 Casa · ⚡ Acciones · 📍 Lugares · 💼 Trabajo · 💕 Pareja · 👤 Estado · 💬 Chat.
Cada submenú tiene "⬅️ Atrás", y cada acción termina en una ficha para confirmar.
"""

from __future__ import annotations

import html

from . import cocina as C
from . import personaje as P
from . import plano as PL
from . import vida as V
from .db import EN_JUEGO, Jugador

# Lo que todavía no existe: se ve en el menú, pero avisa que llega pronto.
PRONTO = {
    "objetos": "🪑 Los objetos de la casa",
    "mascota": "🐾 La mascota",
    "estudiar": "📚 Los estudios",
    "muebles": "🛋️ La tienda de muebles",
    "electronica": "📺 La tienda de electrónica",
    "influencer": "📱 El minijuego de influencer",
    "aniversario": "🎂 El aniversario",
    "retos": "🎯 Los retos semanales",
    "hitos": "🏆 Los hitos de pareja",
}


def _resumen_necesidades(nec: dict) -> str:
    """'🍔 62 · ⚡ 81 · 🚿 70 · 🎉 55 · 💬 40' (en rojo las que están bajas)."""
    partes = []
    for n in V.NECESIDADES:
        valor = round(nec.get(n.clave, 0))
        partes.append(f"{n.emoji} {valor}{'❗' if valor <= V.ROJO else ''}")
    return " · ".join(partes)


class MenuMixin:
    def _b_menu(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import CONTINUAR, Pantalla

        ahora = self.reloj()
        animo = P.animo(j.ap)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"🎮 <b>Menú</b> · {self._firma(j)}{' · ' + animo if animo else ''}",
            f"🕒 {self._reloj(j)} · 📍 {V.nombre_habitacion(j.lugar)}",
        ]
        haciendo = self._texto_accion(j, ahora)
        pausado = self._congelado(j, ahora)
        if haciendo:
            lineas.append(f"▶️ Está {haciendo}")
        elif pausado:
            lineas.append("❄️ Tu Sim está en pausa: toca ▶️ Continuar.")
        lineas.append(_resumen_necesidades(self._nec(j)))
        eventos = self._eventos_activos(j)
        if eventos:
            lineas += ["🎲 " + " · ".join(eventos)]
        pareja = self._pareja_en_sala(j)
        if pareja:
            lineas.append(f"💞 {self._firma(pareja)}: {self._texto_presencia(pareja, ahora)}")
        botones = [
            [("🏠 Casa" + (" 📝" if self._notas_sin_leer(j) else ""), "mcasa"), ("⚡ Acciones", "macc")],
            [("📍 Lugares", "mlug"), ("💼 Trabajo", "trabajo")],
            [("💕 Pareja", "mpar"), ("👤 Estado", "mest")],
            [("💬 Chat", "sala")],
        ]
        if haciendo:
            botones.insert(0, [("⏹️ Parar lo que está haciendo", "parar")])
        if pausado and not haciendo:
            botones.insert(0, [CONTINUAR])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="menu")

    def _b_pronto(self, j: Jugador, que: str, res) -> None:
        res.alerta = f"🚧 {PRONTO.get(que, 'Esto')}: llega en una próxima actualización."

    # --- 🏠 Casa ---------------------------------------------------------

    def _b_menu_casa(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        lineas = [aviso, ""] if aviso else []
        lineas += [
            "🏠 <b>Casa</b>",
            f"📍 Estás en: {V.nombre_habitacion(j.lugar)}",
        ]
        nuevas = self._notas_sin_leer(j)
        if nuevas:
            lineas.append("📝 ¡Hay una nota nueva para ti en la nevera!")
        botones = [
            [("🗺️ Ver plano", "plano"), ("🚶 Moverse", "moverse")],
            [("🧊 Nevera y despensa", "nevera"), ("🪑 Objetos 🚧", "pronto:objetos")],
            [("📝 Notas en la nevera" + (f" ({len(nuevas)})" if nuevas else ""), "notas"), ("🐾 Mascota 🚧", "pronto:mascota")],
            [("🔑 Renta y mudanza", "casa")],
            [("⬅️ Atrás", "menu")],
        ]
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="mcasa")

    def _b_moverse(self, j: Jugador, volver: str, res) -> None:
        """moverse · moverse:plano (desde el plano, y vuelve a él)."""
        from .juego import Pantalla

        volver = "plano" if volver == "plano" else "mcasa"
        if j.lugar.startswith(V.FUERA):
            res.alerta = "Tu Sim está fuera de casa."
            self._volver_de_moverse(j, volver, res)
            return
        sufijo = ":plano" if volver == "plano" else ""
        botones = [
            [(("📍 " if clave == j.lugar else "") + f"{e} {nombre}", f"ir:{clave}{sufijo}")]
            for clave, (e, nombre) in self._zonas(j.sala_id).items()
        ]
        botones.append([("⬅️ Atrás", volver)])
        res.pantalla = Pantalla(
            f"🚶 <b>¿A dónde vas?</b>\n📍 Ahora estás en: {V.nombre_habitacion(j.lugar)}",
            botones,
            clave="mcasa",
        )

    def _volver_de_moverse(self, j: Jugador, volver: str, res, aviso: str | None = None) -> None:
        if volver == "plano":
            res.pantalla = self._pantalla_plano(j, aviso)
        else:
            self._b_menu_casa(j, "", res, aviso)

    def _b_ir(self, j: Jugador, arg: str, res) -> None:
        habitacion, _, volver = arg.partition(":")
        if habitacion not in self._zonas(j.sala_id):
            self._b_moverse(j, volver, res)
            return
        if self._texto_accion(j, self.reloj()):
            res.alerta = "Tu Sim está ocupado ahora. Para lo que está haciendo primero."
            self._volver_de_moverse(j, volver, res)
            return
        j.lugar = habitacion
        self.db.guardar_jugador(j)
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        self._volver_de_moverse(j, volver, res, f"🚶 Ahora estás en {V.nombre_habitacion(habitacion)}.")

    # --- 🗺️ Plano ----------------------------------------------------------

    def _estado_en_plano(self, m: Jugador, ahora: float) -> str:
        """'🍳 cocinando arroz con pollo (12 min)', '❄️ en pausa'…"""
        from .vida_juego import _dur

        accion = self._accion(m)
        a = V.ACCIONES.get(accion["k"]) if accion and accion["rfin"] > ahora else None
        if a is not None:
            texto = f"{a.emoji} {a.verbo}"
            falta = accion["rfin"] - ahora
            coccion = self._coccion(self._hogar(m.sala_id)) if a.clave == "cocinar" else None
            if coccion and m.id in coccion["cocineros"]:
                r = C.RECETAS[coccion["receta"]]
                texto += f" {r.nombre.lower()}"
                _, listo, _ = self._tiempos_paso(coccion)
                siguientes = r.pasos[coccion["paso"] + 1:]
                falta = max(0.0, listo - ahora) + sum(C.minutos_paso(mi, coccion["juntos"]) * 60 for _, mi in siguientes)
            if accion.get("con"):
                otro = self.db.jugador(accion["con"])
                texto += f" con {html.escape(otro.personaje)}" if otro else ""
            return f"{texto} ({_dur(falta)})"
        if m.lugar.startswith(V.FUERA):
            return "📍 fuera de casa"
        if self._congelado(m, ahora):
            return "❄️ en pausa"
        return "🧍 sin hacer nada"

    def _pantalla_plano(self, j: Jugador, aviso: str | None = None):
        """🏠 Casa → Ver plano: la casa en texto, con cada Sim donde está. Se actualiza sola."""
        from .juego import CONTINUAR, Pantalla

        ahora = self.reloj()
        casa = self._casa(self._hogar(j.sala_id))
        miembros = [m for m in self.db.miembros_sala(j.sala_id) if m.estado in EN_JUEGO]
        miembros.sort(key=lambda m: m.id != j.id)  # primero tú
        letras = PL.iniciales([m.personaje for m in miembros])
        dentro, fuera = {}, []
        for m, letra in zip(miembros, letras):
            if m.lugar in casa.zonas:
                dentro.setdefault(m.lugar, []).append(letra)
            else:
                fuera.append(letra)
        lineas = [aviso, ""] if aviso else []
        pausado = self._congelado(j, ahora)
        if pausado:
            lineas += ["❄️ <b>Tu Sim está en pausa.</b> Toca ▶️ Continuar para seguir.", ""]
        lineas.append(f"{casa.emoji} <b>{casa.nombre}</b> — {V.reloj_texto(self._local(j))}")
        lineas.append("<pre>" + html.escape("\n".join(PL.dibujar(casa.zonas, dentro))) + "</pre>")
        if fuera:
            lineas.append(f"🚗 Fuera de casa: {html.escape(PL.marcas(fuera))}")
        for m, letra in zip(miembros, letras):
            quien = f"{html.escape(m.personaje)}{' (tú)' if m.id == j.id else ''}"
            lineas.append(f"<code>[{html.escape(letra)}]</code> {quien}: {self._estado_en_plano(m, ahora)}")
        botones = [
            [("🚶 Moverse", "moverse:plano"), ("⚡ Acciones", "macc")],
            [("🔄 Actualizar", "plano"), ("⬅️ Atrás", "mcasa")],
        ]
        if pausado:
            botones.insert(0, [CONTINUAR])
        return Pantalla("\n".join(lineas), botones, es_sala=True, clave="plano")

    def _b_plano(self, j: Jugador, arg: str, res) -> None:
        res.pantalla = self._pantalla_plano(j)

    # --- ⚡ Acciones --------------------------------------------------------

    def _b_menu_acciones(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        botones = [
            [(f"{e} {nombre}", f"acc:{clave}") for clave, e, nombre in V.CATEGORIAS[i:i + 2]]
            for i in range(0, len(V.CATEGORIAS), 2)
        ]
        botones.append([("📚 Estudiar 🚧", "pronto:estudiar")])
        botones.append([("⬅️ Atrás", "menu")])
        res.pantalla = Pantalla(
            f"⚡ <b>Acciones</b>\n📍 Estás en: {V.nombre_habitacion(j.lugar)}\n"
            "Si una acción se hace en otra habitación, tu Sim va solo hasta allí.",
            botones,
            clave="macc",
        )

    # --- 📍 Lugares ---------------------------------------------------------

    def _b_menu_lugares(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        lineas = ["📍 <b>Lugares</b>"]
        if self._finde(j):
            lineas.append("🎉 Fin de semana: ofertas en el súper; restaurante y cine salen más caros.")
        botones = [[(f"{e} {nombre}", f"a:{clave}")] for clave, e, nombre in V.LUGARES]
        botones.append([("🛋️ Tienda de muebles 🚧", "pronto:muebles"), ("📺 Electrónica 🚧", "pronto:electronica")])
        botones.append([("⬅️ Atrás", "menu")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="mlug")

    # --- 💕 Pareja ----------------------------------------------------------

    def _b_menu_pareja(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        pareja = self._pareja_en_sala(j)
        texto = "💕 <b>Pareja</b>"
        if pareja:
            texto += f"\n💞 {self._firma(pareja)}: {self._texto_presencia(pareja, self.reloj())}"
        else:
            texto += "\nTodavía juegas sin pareja en la sala. Invítala con 💌 Invitar."
        pregunta = self._pregunta(self._hogar(j.sala_id)) if pareja else None
        falta = pregunta is not None and str(j.id) not in pregunta["respuestas"]
        botones = [
            [("💞 Acciones en pareja", "acc:pareja")],
            [("💗 Medidor de relación", "medidor"), ("❓ Preguntas" + (" (1)" if falta else ""), "preg")],
            [("🎂 Aniversario 🚧", "pronto:aniversario"), ("🎯 Retos 🚧", "pronto:retos")],
            [("🏆 Hitos 🚧", "pronto:hitos"), ("📸 Álbum", "album")],
            [("💌 Invitar", "invitar"), ("⬅️ Atrás", "menu")],
        ]
        res.pantalla = Pantalla(texto, botones, clave="mpar")

    # --- 👤 Estado ----------------------------------------------------------

    def _b_menu_estado(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        botones = [
            [("🧍 Mis necesidades", "sim"), ("🎭 Estado de ánimo", "animos")],
            [("👀 Perfil de mi pareja", "perfil"), ("💰 Dinero", "dinero")],
            [("🪪 Personajes", "pjs"), ("⚙️ Ajustes", "ajustes")],
            [("⬅️ Atrás", "menu")],
        ]
        res.pantalla = Pantalla(
            f"👤 <b>Estado</b>\n{self._firma(j)} · {_resumen_necesidades(self._nec(j))}",
            botones,
            clave="mest",
        )

    def _b_perfil(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla, esc

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "Todavía no hay pareja en tu sala."
            self._b_menu_estado(j, "", res)
            return
        ahora = self.reloj()
        lineas = [f"👀 <b>Perfil de {self._firma(pareja)}</b>"] + self._texto_animo_actual(j, pareja) + [
            f"{self._texto_presencia(pareja, ahora)}",
            f"🕒 Su hora: {self._reloj(pareja)} · 📍 {V.nombre_habitacion(pareja.lugar)}",
            f"💼 {self._texto_puesto(pareja) or 'Sin trabajo todavía'}",
            f"📊 {_resumen_necesidades(self._nec(pareja))}",
            f"💗 Tú → {esc(pareja.personaje)}: {self._relacion(j)} % · {esc(pareja.personaje)} → tú: {self._relacion(pareja)} %",
            "",
            f"<i>{esc(P.descripcion(pareja.personaje, pareja.ap))}</i>",
        ]
        botones = [[("💞 Hacer algo juntos", "acc:pareja"), ("⬅️ Atrás", "mest")]]
        actual = self._extras(pareja).get("animo_actual")
        if actual and actual.get("foto") and actual["animo"] == pareja.ap.get("animo"):
            botones.insert(0, [("📸 Ver su foto", f"fotoan:{pareja.id}"), ("📸 Álbum", "album")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="perfil")
