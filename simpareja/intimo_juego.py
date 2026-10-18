"""Momento íntimo: un minijuego de pareja con opciones (versión 0.33), al estilo del «ñiqui-ñiqui» de Los Sims.

`IntimoMixin` se mezcla con `Juego`. En 💕 Pareja → 🔥 Momento íntimo:
- Solo entre la pareja de la sala y solo si los dos quieren: uno lo propone (lugar y ambiente) y el otro
  acepta o dice «hoy no», sin ningún castigo. Cualquiera puede parar en cualquier momento.
- Tres rondas (preparar el momento, acercarse y el momento): cada uno elige una opción sin ver la del
  otro. Si eligen lo mismo hay conexión, y más si va con el ambiente que buscaban.
- Al final las luces se apagan (nada explícito): suben el social, la diversión y el medidor de los dos,
  según la conexión, y se quedan un rato descansando abrazados. Llega una foto estilo anime romántico del
  lugar, con los rasgos de los dos y pixelada abajo (se pide a la IA en cuanto empiezan).

En `extras` del hogar: "intimo" {estado: propuesto|jugando, de, para, lugar, ambiente, ronda,
elecciones, puntos, ts} e "intimo_ultimo" (cuándo fue el último).
"""

from __future__ import annotations

from . import narracion as N
from . import vida as V
from .db import Hogar, Jugador

# En cualquier lugar de la casa: (emoji, dónde, habitación del plano).
LUGARES = {
    "cuarto": ("🛏️", "en la cama", "cuarto"),
    "bano": ("🚿", "en la ducha", "bano"),
    "salon": ("🛋️", "en el sofá", "salon"),
    "cocina": ("🍳", "en la cocina", "salon"),
    "closet": ("👗", "en el clóset", "closet"),
    "extra": ("🧸", "en el cuarto extra", "extra"),
}
# Cada ambiente va con uno de los tres estilos de las opciones (el mismo orden en cada ronda).
AMBIENTES = {"romantico": ("🕯️", "Romántico"), "jugueton": ("😏", "Juguetón"), "apasionado": ("🔥", "Apasionado")}
ESTILOS = tuple(AMBIENTES)
RONDAS = (
    ("🕯️ Preparar el momento", (("velas", "🕯️", "Velas y luz suave"), ("musica", "🎵", "Su canción favorita"),
                               ("copa", "🍷", "Una copa y miradas"))),
    ("💋 Acercarse", (("abrazo", "🤗", "Un abrazo largo"), ("risas", "😏", "Coquetear y hacer reír"),
                     ("beso", "💋", "Un beso intenso"))),
    ("💞 El momento", (("ternura", "💞", "Con calma y ternura"), ("cosquillas", "😂", "Entre risas y cosquillas"),
                      ("pasion", "🔥", "Con pasión"))),
)
VENCE = 30 * 60  # la propuesta, y cada ronda sin respuesta
ESPERA = 60 * 60  # entre un momento íntimo y el siguiente
ENERGIA_MINIMA = 15
ABRAZADOS = 10  # minutos descansando abrazados al terminar


def _opcion(ronda: int, clave: str) -> tuple[int, str, str] | None:
    """(estilo, emoji, nombre) de una opción de la ronda."""
    for i, (c, emoji, nombre) in enumerate(RONDAS[ronda][1]):
        if c == clave:
            return i, emoji, nombre
    return None


def puntos_ronda(a: str, b: str, ronda: int, ambiente: str) -> tuple[int, str]:
    """Lo que suma una ronda: 1 si eligen distinto, 2 si eligen lo mismo y 3 si además va con el ambiente."""
    if a != b:
        return 1, "✨ Cada quien a su manera… ¡y se complementan!"
    if ESTILOS[_opcion(ronda, a)[0]] == ambiente:
        return 3, "🔥 ¡Los dos eligieron lo mismo, justo el ambiente que buscaban!"
    return 2, "💞 ¡Los dos eligieron lo mismo: conexión total!"


def resultado(puntos: int) -> str:
    if puntos >= 8:
        return "🔥 <b>¡Un momento inolvidable!</b>"
    if puntos >= 5:
        return "💞 <b>Un momento muy especial.</b>"
    return "😊 <b>Un momento tierno y divertido.</b>"


class IntimoMixin:
    def _intimo(self, h: Hogar) -> dict | None:
        """El momento propuesto o en juego (si no venció)."""
        estado = self._extras_hogar(h).get("intimo")
        return estado if estado and self.reloj() - estado["ts"] <= VENCE else None

    def _guardar_intimo(self, h: Hogar, estado: dict | None, terminado: bool = False) -> None:
        extras = self._extras_hogar(h)
        if estado is None:
            extras.pop("intimo", None)
        else:
            extras["intimo"] = estado
        if terminado:
            extras["intimo_ultimo"] = self.reloj()
        self._guardar_extras_hogar(h, extras)

    def _no_se_puede_intimo(self, j: Jugador, pareja: Jugador | None) -> str | None:
        """Por qué ahora no (o None si se puede)."""
        ahora = self.reloj()
        if pareja is None:
            return "Es para hacerlo en pareja: primero invita a tu pareja a tu sala."
        ultimo = self._extras_hogar(self._hogar(j.sala_id)).get("intimo_ultimo", 0)
        if ahora - ultimo < ESPERA:
            return "Hace poco tuvieron un momento juntos: denle una hora. 💞"
        for m in (j, pareja):
            quien = "Tu Sim" if m.id == j.id else self._firma(m)
            if m.lugar.startswith(V.FUERA):
                return f"{quien} está fuera de casa."
            if self._texto_accion(m, ahora):
                return f"{quien} está ocupado ahora: primero tiene que terminar lo que hace."
            if self._nec(m).get("energia", 0) < ENERGIA_MINIMA:
                return f"{quien} está sin energía: mejor descansar primero."
        return None

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_intimo(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💕 Pareja → 🔥 Momento íntimo: elegir el lugar, ver la propuesta o seguir la ronda."""
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        estado = self._intimo(h)
        pareja = self._pareja_en_sala(j)
        if estado and estado["estado"] == "jugando" and j.id in (estado["de"], estado["para"]):
            res.pantalla = self._pantalla_ronda(j, estado, aviso)
            return
        lineas = [aviso, ""] if aviso else []
        lineas += [
            "🔥 <b>Momento íntimo</b>",
            "",
            "Un rato a solas, solo si los dos quieren. Eligen el lugar y el ambiente, y en tres rondas cada "
            "uno escoge cómo quiere que sea, sin ver lo que elige el otro. Cuanta más conexión, mejor.",
            "🛑 Cualquiera puede decir «hoy no» o parar cuando quiera, sin ningún problema.",
            "",
        ]
        botones = []
        if estado and estado["para"] == j.id:
            lugar, ambiente = LUGARES[estado["lugar"]][:2], AMBIENTES[estado["ambiente"]]
            lineas.append(f"💌 {self._firma(pareja)} te propone un momento a solas {lugar[0]} {lugar[1]} · "
                          f"{ambiente[0]} {ambiente[1].lower()}.")
            botones.append([("✅ Sí, me encantaría", "intsi"), ("🙈 Hoy no", "intno")])
        elif estado and estado["de"] == j.id:
            lineas.append(f"⏳ Esperando a que {self._firma(pareja)} responda.")
            botones.append([("🚫 Retirar la propuesta", "intno")])
        else:
            motivo = self._no_se_puede_intimo(j, pareja)
            if motivo:
                lineas.append(f"ℹ️ {motivo}")
            else:
                lineas.append("<b>¿Dónde?</b> En cualquier lugar de la casa.")
                botones += self._botones_lugares_intimo(j)
        botones.append([("⬅️ Pareja", "mpar"), ("🎮 Menú", "menu")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="intimo")

    def _lugares_intimo(self, j: Jugador) -> list[str]:
        """Los lugares de esta casa (el cuarto extra, solo si lo hay); primero donde estás ahora."""
        zonas = self._zonas(j.sala_id)
        lugares = [clave for clave, (_, _, zona) in LUGARES.items() if zona in zonas]
        aqui = next((c for c in lugares if LUGARES[c][2] == j.lugar), None)
        return ([aqui] if aqui else []) + [c for c in lugares if c != aqui]

    def _botones_lugares_intimo(self, j: Jugador):
        from .juego import en_filas

        botones = []
        for clave in self._lugares_intimo(j):
            e, nombre, zona = LUGARES[clave]
            texto = f"{e} {nombre[0].upper()}{nombre[1:]}"
            botones.append((("📍 " if zona == j.lugar and not botones else "") + texto, f"intl:{clave}"))
        return [[botones[0]]] + en_filas(botones[1:]) if botones else []

    def _b_intimo_lugar(self, j: Jugador, lugar: str, res) -> None:
        """intl:<lugar>: elegir el ambiente."""
        from .juego import Pantalla

        if lugar not in self._lugares_intimo(j):
            self._b_intimo(j, "", res)
            return
        e, nombre, _ = LUGARES[lugar]
        res.pantalla = Pantalla(
            f"🔥 <b>Momento íntimo</b> · {e} {nombre}\n\n<b>¿Qué ambiente?</b>",
            [[(f"{ae} {anombre}", f"intp:{lugar}:{clave}")] for clave, (ae, anombre) in AMBIENTES.items()]
            + [[("⬅️ Atrás", "intimo")]],
            clave="intimo",
        )

    def _pantalla_ronda(self, j: Jugador, estado: dict, aviso: str | None = None):
        from .juego import Pantalla

        ronda = estado["ronda"]
        titulo, opciones = RONDAS[ronda]
        lugar, ambiente = LUGARES[estado["lugar"]][:2], AMBIENTES[estado["ambiente"]]
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"🔥 <b>Momento íntimo</b> · {lugar[0]} {lugar[1]} · {ambiente[0]} {ambiente[1].lower()}",
            f"Ronda {ronda + 1} de {len(RONDAS)}: <b>{titulo}</b>",
            "",
        ]
        elegida = estado["elecciones"].get(str(j.id))
        if elegida:
            _, emoji, nombre = _opcion(ronda, elegida)
            otro = self.db.jugador(estado["para"] if j.id == estado["de"] else estado["de"])
            lineas.append(f"✅ Elegiste {emoji} {nombre}. Esperando a {self._firma(otro)}…")
            botones = []
        else:
            lineas.append("¿Cómo lo quieres? (tu pareja no ve lo que eliges hasta que elija)")
            botones = [[(f"{emoji} {nombre}", f"into:{clave}")] for clave, emoji, nombre in opciones]
        botones.append([("🛑 Parar", "intpara")])
        return Pantalla("\n".join(lineas), botones, clave="intimo")

    # ------------------------------------------------------------------
    # Proponer, aceptar, elegir y parar
    # ------------------------------------------------------------------

    def _b_intimo_proponer(self, j: Jugador, arg: str, res) -> None:
        """intp:<lugar>:<ambiente>."""
        from .juego import Aviso

        lugar, _, ambiente = arg.partition(":")
        h = self._hogar(j.sala_id)
        pareja = self._pareja_en_sala(j)
        motivo = self._no_se_puede_intimo(j, pareja)
        if lugar not in self._lugares_intimo(j) or ambiente not in AMBIENTES or motivo or self._intimo(h):
            res.alerta = motivo or "Ahora no se puede."
            self._b_intimo(j, "", res)
            return
        self._guardar_intimo(h, {
            "estado": "propuesto", "de": j.id, "para": pareja.id, "lugar": lugar, "ambiente": ambiente,
            "ronda": 0, "elecciones": {}, "puntos": 0, "ts": self.reloj(),
        })
        e, nombre, _ = LUGARES[lugar]
        ae, anombre = AMBIENTES[ambiente]
        res.avisos.append(Aviso(
            pareja.id,
            f"💌 {self._firma(j)} te propone un <b>momento a solas</b> {e} {nombre} · {ae} {anombre.lower()}.\n\n"
            "Solo si tú también quieres. 💞",
            [[("✅ Sí, me encantaría", "intsi"), ("🙈 Hoy no", "intno")]],
        ))
        self._b_intimo(j, "", res, f"💌 Se lo propusiste a {self._firma(pareja)}. Te aviso cuando responda.")

    def _b_intimo_si(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        estado = self._intimo(h)
        if not estado or estado["estado"] != "propuesto" or estado["para"] != j.id:
            res.alerta = "Esa propuesta ya no está."
            self._b_intimo(j, "", res)
            return
        de = self.db.jugador(estado["de"])
        if de is None or de.sala_id != j.sala_id:
            res.alerta = "Esa propuesta ya no está."
            self._guardar_intimo(h, None)
            self._b_intimo(j, "", res)
            return
        motivo = self._no_se_puede_intimo(j, de)
        if motivo:
            res.alerta = motivo
            self._b_intimo(j, "", res)
            return
        ahora = self.reloj()
        for m in (j, de):
            self._descongelar(m, ahora)
            m.lugar = LUGARES[estado["lugar"]][2]
            m.ultima_jugada = ahora
            self.db.guardar_jugador(m)
        estado.update(estado="jugando", ts=ahora)
        self._guardar_intimo(h, estado)
        self.por_dibujar += [f for f in (self._foto_intima(j, de, estado), self._foto_intima(de, j, estado)) if f]
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        pantalla = self._pantalla_ronda(de, estado, f"💞 {self._firma(j)} dijo que sí.")
        res.avisos.append(Aviso(de.id, pantalla.texto, pantalla.botones))
        res.pantalla = self._pantalla_ronda(j, estado, "💞 ¡Empieza su momento a solas!")

    def _b_intimo_no(self, j: Jugador, arg: str, res) -> None:
        """«Hoy no» (quien recibe la propuesta) o retirar la propia; sin ningún castigo."""
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        estado = self._intimo(h)
        if estado and estado["estado"] == "propuesto" and j.id in (estado["de"], estado["para"]):
            self._guardar_intimo(h, None)
            if j.id == estado["para"]:
                res.avisos.append(Aviso(estado["de"], f"🙈 {self._firma(j)} prefiere hoy no. ¡Otro día será! 💞"))
                res.alerta = "Le avisé con cariño. 💞"
            else:
                res.alerta = "Propuesta retirada."
        self._b_intimo(j, "", res)

    def _b_intimo_parar(self, j: Jugador, arg: str, res) -> None:
        """Cualquiera puede parar en cualquier momento."""
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        estado = self._intimo(h)
        if estado and j.id in (estado["de"], estado["para"]):
            self._guardar_intimo(h, None)
            otro = estado["para"] if j.id == estado["de"] else estado["de"]
            res.avisos.append(Aviso(otro, f"🛑 {self._firma(j)} prefirió parar. Todo bien: otro día será. 💞",
                                    [[("💕 Pareja", "mpar")]]))
            aviso = "🛑 Paraste. Todo bien: se lo avisé a tu pareja con cariño. 💞"
        else:
            aviso = None
        self._b_intimo(j, "", res, aviso)

    def _b_intimo_opcion(self, j: Jugador, clave: str, res) -> None:
        """into:<opción>: la elección de esta ronda."""
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        estado = self._intimo(h)
        if not estado or estado["estado"] != "jugando" or j.id not in (estado["de"], estado["para"]):
            res.alerta = "Ese momento ya terminó."
            self._b_intimo(j, "", res)
            return
        self._descongelar(j, self.reloj())
        ronda = estado["ronda"]
        if _opcion(ronda, clave) is None or str(j.id) in estado["elecciones"]:
            res.pantalla = self._pantalla_ronda(j, estado)
            return
        otro = self.db.jugador(estado["para"] if j.id == estado["de"] else estado["de"])
        estado["elecciones"][str(j.id)] = clave
        estado["ts"] = self.reloj()
        if str(otro.id) not in estado["elecciones"]:
            self._guardar_intimo(h, estado)
            res.pantalla = self._pantalla_ronda(j, estado)
            return
        mia, suya = clave, estado["elecciones"][str(otro.id)]
        puntos, frase = puntos_ronda(mia, suya, ronda, estado["ambiente"])
        _, e1, n1 = _opcion(ronda, mia)
        _, e2, n2 = _opcion(ronda, suya)
        resumen = (f"{self._firma(j)} eligió {e1} {n1} y {self._firma(otro)} eligió {e2} {n2}.\n{frase}")
        estado["puntos"] += puntos
        estado["ronda"] += 1
        estado["elecciones"] = {}
        if estado["ronda"] < len(RONDAS):
            self._guardar_intimo(h, estado)
            pantalla = self._pantalla_ronda(otro, estado, resumen)
            res.avisos.append(Aviso(otro.id, pantalla.texto, pantalla.botones))
            res.pantalla = self._pantalla_ronda(j, estado, resumen)
            return
        self._guardar_intimo(h, None, terminado=True)
        final = self._terminar_intimo(j, otro, estado)
        texto = f"{resumen}\n\n{final}"
        botones = [[("🗺️ Ver la casa", "mcasa"), ("🎮 Menú", "menu")]]
        res.avisos.append(Aviso(otro.id, texto, botones))
        emoji, donde, _ = LUGARES[estado["lugar"]]
        for m, pareja in ((otro, j), (j, otro)):
            foto = self._foto_intima(m, pareja, estado)
            if foto:
                res.avisos.append(Aviso(m.id, f"📸 Su momento {emoji} {donde}. 💞", foto=f"ilus:{foto}",
                                        silencio=True, solo_foto=True))
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        from .juego import Pantalla

        res.pantalla = Pantalla(texto, botones, clave="intimo")

    def _foto_intima(self, j: Jugador, otro: Jugador, estado: dict) -> str | None:
        """La foto del momento según el lugar de la casa (ilustraciones.py), si quien la recibe quiere fotos."""
        return self._foto(j, f"intimo_{estado['lugar']}", N.momento(self._hora_local(j)), otro.id)

    def _terminar_intimo(self, j: Jugador, otro: Jugador, estado: dict) -> str:
        """Las luces se apagan: suben las necesidades y el medidor de los dos, y se quedan abrazados."""
        extra = estado["puntos"] - len(RONDAS)  # de 0 a 6
        cambios = {"social": 20 + 3 * extra, "diversion": 15 + 3 * extra, "energia": -10,
                   "higiene": 20 if estado["lugar"] == "bano" else -10}
        relacion = 2 + extra // 2
        abrazados = V.ACCIONES["abrazados"]
        ahora = self.reloj()
        for m, con in ((j, otro), (otro, j)):
            m = self.db.jugador(m.id)
            self._descongelar(m, ahora)
            self._sumar_necesidades(m, cambios)
            self._cambiar_relacion(m, relacion, "💞 Un momento a solas juntos", auto=True)
            m = self.db.jugador(m.id)
            self._empezar(m, abrazados, "", con.id, ahora, minutos=ABRAZADOS)
        return (
            "🌙 … y las luces se apagan. ❤️\n\n"
            f"{resultado(estado['puntos'])}\n"
            f"💬 Social +{cambios['social']} · 🎉 Diversión +{cambios['diversion']} · 💗 Medidor +{relacion} "
            "para los dos\n"
            f"💞 Ahora se quedan un rato descansando abrazados ({ABRAZADOS} min)."
        )
