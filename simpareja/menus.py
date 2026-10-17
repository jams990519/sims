"""Menú principal y submenús (actualización 2, parte 1).

🏠 Casa · ⚡ Acciones · 📍 Lugares · 💼 Trabajo · 💕 Pareja · 👤 Estado · 💬 Chat.
Cada submenú tiene "⬅️ Atrás", y cada acción termina en una ficha para confirmar.
"""

from __future__ import annotations

from . import personaje as P
from . import vida as V
from .db import Jugador

# Lo que todavía no existe: se ve en el menú, pero avisa que llega pronto.
PRONTO = {
    "plano": "🗺️ El plano de la casa",
    "objetos": "🪑 Los objetos de la casa",
    "notas": "📝 Las notas en la nevera",
    "mascota": "🐾 La mascota",
    "estudiar": "📚 Los estudios",
    "muebles": "🛋️ La tienda de muebles",
    "electronica": "📺 La tienda de electrónica",
    "influencer": "📱 El minijuego de influencer",
    "medidor": "💗 El medidor de relación",
    "preguntas": "❓ Las preguntas de pareja",
    "aniversario": "🎂 El aniversario",
    "retos": "🎯 Los retos semanales",
    "hitos": "🏆 Los hitos de pareja",
    "album": "📸 El álbum de recuerdos",
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
        pareja = self._pareja_en_sala(j)
        if pareja:
            lineas.append(f"💞 {self._firma(pareja)}: {self._texto_presencia(pareja, ahora)}")
        botones = [
            [("🏠 Casa", "mcasa"), ("⚡ Acciones", "macc")],
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
        botones = [
            [("🗺️ Ver plano 🚧", "pronto:plano"), ("🚶 Moverse", "moverse")],
            [("🧊 Nevera y despensa", "nevera"), ("🪑 Objetos 🚧", "pronto:objetos")],
            [("📝 Notas en la nevera 🚧", "pronto:notas"), ("🐾 Mascota 🚧", "pronto:mascota")],
            [("🔑 Renta y mudanza", "casa")],
            [("⬅️ Atrás", "menu")],
        ]
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="mcasa")

    def _b_moverse(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        if j.lugar.startswith(V.FUERA):
            res.alerta = "Tu Sim está fuera de casa."
            self._b_menu_casa(j, "", res)
            return
        botones = [
            [(("📍 " if clave == j.lugar else "") + f"{e} {nombre}", f"ir:{clave}")]
            for clave, (e, nombre) in V.ZONAS.items()
        ]
        botones.append([("⬅️ Atrás", "mcasa")])
        res.pantalla = Pantalla(
            f"🚶 <b>¿A dónde vas?</b>\n📍 Ahora estás en: {V.nombre_habitacion(j.lugar)}",
            botones,
            clave="mcasa",
        )

    def _b_ir(self, j: Jugador, habitacion: str, res) -> None:
        if habitacion not in V.ZONAS:
            self._b_moverse(j, "", res)
            return
        if self._texto_accion(j, self.reloj()):
            res.alerta = "Tu Sim está ocupado ahora. Para lo que está haciendo primero."
            self._b_menu_casa(j, "", res)
            return
        j.lugar = habitacion
        self.db.guardar_jugador(j)
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        self._b_menu_casa(j, "", res, f"🚶 Ahora estás en {V.nombre_habitacion(habitacion)}.")

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
        botones = [
            [("💞 Acciones en pareja", "acc:pareja")],
            [("💗 Medidor de relación 🚧", "pronto:medidor"), ("❓ Preguntas 🚧", "pronto:preguntas")],
            [("🎂 Aniversario 🚧", "pronto:aniversario"), ("🎯 Retos 🚧", "pronto:retos")],
            [("🏆 Hitos 🚧", "pronto:hitos"), ("📸 Álbum 🚧", "pronto:album")],
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
        animo = P.animo(pareja.ap)
        lineas = [
            f"👀 <b>Perfil de {self._firma(pareja)}</b>",
            f"🎭 {animo or 'Sin estado de ánimo'}",
            f"{self._texto_presencia(pareja, ahora)}",
            f"🕒 Su hora: {self._reloj(pareja)} · 📍 {V.nombre_habitacion(pareja.lugar)}",
            f"💼 {self._texto_puesto(pareja) or 'Sin trabajo todavía'}",
            f"📊 {_resumen_necesidades(self._nec(pareja))}",
            "",
            f"<i>{esc(P.descripcion(pareja.personaje, pareja.ap))}</i>",
        ]
        res.pantalla = Pantalla(
            "\n".join(lineas), [[("💞 Hacer algo juntos", "acc:pareja"), ("⬅️ Atrás", "mest")]], clave="perfil"
        )
