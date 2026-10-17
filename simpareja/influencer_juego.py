"""Influencer: minijuego compatible con un trabajo (diseño v1, parte 9; y su equipo, actualización 2, parte 13).

`InfluencerMixin` se mezcla con `Juego`. Pasos de cada video: elegir el tema, 🎥 grabar (toma tiempo
y gasta energía), ✂️ editar y publicar (da seguidores y algo de dinero) y 📚 aprender para subir de nivel.
- Al principio gana de $5 a $20 por video; desde 1.000 seguidores llegan patrocinios de $100 a $300.
- Ayuda de la pareja: escribir el guion (mejor calidad), grabar juntos (más rápido y sale en el video:
  más seguidores). Cada ayuda sube la relación.
- Constancia: publicando cada 2 días crece. Desde el tercer día sin publicar pierde un 2 % de seguidores
  al día y, después de una semana, un 5 %. El primer video después de una pausa rinde menos.
- Fines de semana: más alcance. Cámara, aro de luz y micrófono mejoran la calidad.

En `extras` del jugador: "influencer" {seguidores, xp, videos, ganado, ultimo (fecha local), perdida
(fecha), video {tema, grabado, juntos, guion}}.
"""

from __future__ import annotations

import json

from . import dinero as D
from .db import Jugador

TEMAS = {
    "cocina": "🍳 Cocina", "belleza": "💄 Belleza", "juegos": "🎮 Videojuegos", "humor": "😂 Humor",
    "fitness": "💪 Fitness", "viajes": "✈️ Viajes", "pareja": "💑 En pareja",
}
EQUIPO = ("camara", "aro", "micro")
PAGO = (5, 20)
PATROCINIO = (100, 300)
PATROCINIO_DESDE = 1000
PATROCINIO_PROB = 0.35
XP_NIVEL = 100
NIVEL_MAX = 5
XP_APRENDER = 25
XP_VIDEO = 10
AYUDA_RELACION = 2


def nivel(xp: int) -> int:
    return min(NIVEL_MAX, 1 + xp // XP_NIVEL)


def calidad(niv: int, equipo: int, guion: bool) -> float:
    """1 al empezar; sube con el nivel, cada pieza del equipo y el guion de la pareja."""
    return round(1 + 0.2 * (niv - 1) + 0.15 * equipo + (0.3 if guion else 0), 2)


def perdida(dias_sin_publicar: int) -> float:
    """Qué parte de los seguidores se pierde hoy por no publicar."""
    if dias_sin_publicar >= 7:
        return 0.05
    if dias_sin_publicar >= 3:
        return 0.02
    return 0.0


class InfluencerMixin:
    def _influ(self, j: Jugador) -> dict:
        return self._extras(j).get("influencer") or {"seguidores": 0, "xp": 0, "videos": 0, "ganado": 0}

    def _guardar_influ(self, j: Jugador, datos: dict) -> None:
        extras = self._extras(j)
        extras["influencer"] = datos
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)

    def _equipo(self, j: Jugador) -> int:
        return sum(1 for clave in EQUIPO if self._tiene(j, clave))

    def _falta_video(self, j: Jugador, a) -> str | None:
        """Grabar necesita un tema elegido; editar, un video grabado; el guion, que la pareja esté preparando uno."""
        if a.clave == "grabar":
            video = self._influ(j).get("video")
            return None if video and not video.get("grabado") else "🎬 Primero elige el tema del video en 💼 Trabajo → Influencer."
        if a.clave == "editar":
            video = self._influ(j).get("video")
            return None if video and video.get("grabado") else "🎥 Primero graba el video."
        if a.clave == "guion":
            pareja = self._pareja_en_sala(j)
            video = self._influ(pareja).get("video") if pareja else None
            if not video or video.get("grabado") or video.get("guion"):
                return "✍️ Tu pareja no está preparando ningún video que necesite guion."
        return None

    # ------------------------------------------------------------------
    # Pantalla
    # ------------------------------------------------------------------

    def _b_influencer(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💼 Trabajo → 📱 Influencer · influ:tema:<tema> (empieza un video)."""
        from .juego import Pantalla

        datos = self._influ(j)
        paso, _, tema = arg.partition(":")
        if paso == "tema" and tema in TEMAS and not datos.get("video"):
            if tema == "pareja" and self._pareja_en_sala(j) is None:
                res.alerta = "Para un video en pareja hace falta tu pareja 💑."
            else:
                datos["video"] = {"tema": tema, "grabado": False, "juntos": False, "guion": False}
                self._guardar_influ(j, datos)
                aviso = f"🎬 Tema elegido: {TEMAS[tema]}. ¡A grabar!"
        niv = nivel(datos["xp"])
        lineas = [aviso, ""] if aviso else []
        lineas += [
            "📱 <b>Influencer</b> · compatible con tu trabajo",
            f"👥 {datos['seguidores']:,} seguidores".replace(",", ".") + f" · ⭐ nivel {niv} · 🎬 {datos['videos']} videos",
            f"💵 Ganado: {D.dinero(datos['ganado'])}"
            + (" · 🤝 con patrocinios" if datos["seguidores"] >= PATROCINIO_DESDE else f" · patrocinios desde {PATROCINIO_DESDE:,}".replace(",", ".")),
            f"🎥 Equipo: {self._equipo(j)}/3 (cámara, aro de luz, micrófono) · calidad ×{calidad(niv, self._equipo(j), False)}",
        ]
        if datos.get("ultimo"):
            dias = self._hoy(j) - datos["ultimo"]
            lineas.append("📅 Publicaste hoy." if dias == 0 else f"📅 Último video hace {dias} día(s)"
                          + (" ⚠️ pierdes seguidores cada día" if dias >= 3 else "") + ".")
        lineas.append("")
        botones = []
        video = datos.get("video")
        if not video:
            lineas.append("1️⃣ Elige el tema del video:")
            temas = [(n, f"influ:tema:{k}") for k, n in TEMAS.items()]
            botones += [temas[k:k + 3] for k in range(0, len(temas), 3)]
        elif not video["grabado"]:
            ayuda = " · ✍️ con guion de tu pareja" if video["guion"] else ""
            lineas.append(f"2️⃣ Video de {TEMAS[video['tema']]}{ayuda}: falta grabarlo (gasta energía).")
            botones.append([("🎥 Grabar", f"a:grabar:{j.id}")])
        else:
            lineas.append(f"3️⃣ Video de {TEMAS[video['tema']]} grabado"
                          + (" contigo y tu pareja" if video["juntos"] else "") + ": falta editarlo y publicarlo.")
            botones.append([("✂️ Editar y publicar", "a:editar")])
        botones.append([("📚 Aprender (sube de nivel)", "a:aprender_redes")])
        if self._finde(j):
            lineas.append("🎉 Es fin de semana: los videos llegan a más gente.")
        lineas.append("💞 Tu pareja puede ayudarte: escribir el guion, o grabar contigo y salir en el video.")
        pareja = self._pareja_en_sala(j)
        suyo = self._influ(pareja).get("video") if pareja else None
        if suyo and not suyo["grabado"] and not suyo["guion"]:
            lineas += ["", f"✍️ {pareja.personaje} está preparando un video de {TEMAS[suyo['tema']]}: puedes escribirle el guion."]
            botones.insert(-1, [("✍️ Escribirle el guion", "a:guion")])
        botones.append([("🛍️ Equipo", "tienda:electronica"), ("⬅️ Atrás", "trabajo")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="influ")

    # ------------------------------------------------------------------
    # Al terminar cada paso
    # ------------------------------------------------------------------

    def _paso_influencer(self, j: Jugador, accion: dict) -> str:
        """Lo que pasa al terminar grabar, editar, aprender o escribir el guion."""
        from .juego import esc

        clave = accion["k"]
        if clave == "guion":
            pareja = self._pareja_en_sala(j)
            if pareja is None:
                return ""
            datos = self._influ(pareja)
            if datos.get("video") and not datos["video"]["guion"]:
                datos["video"]["guion"] = True
                self._guardar_influ(pareja, datos)
                for m in (j, pareja):
                    self._cambiar_relacion(m, AYUDA_RELACION, "✍️ Guion para un video", auto=True)
            return f" ✍️ El guion de {esc(pareja.personaje)} quedó listo."
        if clave not in ("grabar", "editar", "aprender_redes"):
            return ""
        datos = self._influ(j)
        if clave == "aprender_redes":
            antes = nivel(datos["xp"])
            datos["xp"] += XP_APRENDER
            self._guardar_influ(j, datos)
            return f" 📚 +{XP_APRENDER} de experiencia" + (f": ¡nivel {nivel(datos['xp'])}! ⭐" if nivel(datos["xp"]) > antes else ".")
        video = datos.get("video")
        if clave == "grabar" and str(accion.get("x", "")).isdigit() and int(accion["x"]) != j.id:
            return " 🎥 ¡Saliste en el video de tu pareja!"  # quien ayudó a grabar
        if not video:
            return ""
        if clave == "grabar":
            video["grabado"] = True
            if accion.get("con"):
                video["juntos"] = True
                otro = self.db.jugador(accion["con"])
                for m in (j, otro):
                    if m:
                        self._cambiar_relacion(m, AYUDA_RELACION, "🎥 Grabamos un video juntos", auto=True)
            self._guardar_influ(j, datos)
            return " 🎥 Video grabado: falta editarlo y publicarlo."
        return self._publicar_video(j, datos, video)

    def _publicar_video(self, j: Jugador, datos: dict, video: dict) -> str:
        hoy = self._hoy(j)
        niv = nivel(datos["xp"])
        cal = calidad(niv, self._equipo(j), video["guion"])
        alcance = self.rng.randint(20, 60) * cal
        if video["juntos"] or video["tema"] == "pareja":
            alcance *= 1.5
        if self._finde(j):
            alcance *= 1.3
        pausa = datos.get("ultimo") is not None and hoy - datos["ultimo"] >= 3
        if pausa:
            alcance *= 0.6  # el primer video después de una pausa rinde menos
        nuevos = round(alcance + datos["seguidores"] * 0.02)
        datos["seguidores"] += nuevos
        pago = round(self.rng.randint(*PAGO) * cal)
        texto = f" 📱 ¡Publicado! +{nuevos} seguidores y {D.dinero(pago)}"
        if datos["seguidores"] >= PATROCINIO_DESDE and self.rng.random() < PATROCINIO_PROB:
            patrocinio = self.rng.randint(*PATROCINIO)
            pago += patrocinio
            texto += f" + 🤝 patrocinio de {D.dinero(patrocinio)}"
        texto += "." + (" (Volviste después de una pausa: rindió menos.)" if pausa else "")
        datos.update(videos=datos["videos"] + 1, ganado=datos["ganado"] + pago, ultimo=hoy, xp=datos["xp"] + XP_VIDEO)
        datos.pop("video", None)
        self._guardar_influ(j, datos)
        self._cobrar_influencer(j, pago)
        return texto

    def _cobrar_influencer(self, j: Jugador, pago: int) -> None:
        if not pago:
            return
        if self._dinero_unido(j):
            h = self._hogar(j.sala_id)
            h.cuenta += pago
            self.db.guardar_hogar(h)
            self._anotar_movimiento(j.sala_id, j.id, "compartida", pago, "📱 Videos")
        else:
            j.cartera += pago  # el mismo objeto que _vivir guarda después
            self.db.guardar_jugador(j)
            self._anotar_movimiento(j.sala_id, j.id, "cartera", pago, "📱 Videos")

    def _tick_influencer(self, res) -> None:
        """Sin publicar se pierden seguidores (una vez al día) y, por debajo de 1.000, los patrocinios."""
        from .juego import Aviso

        for j in self.db.jugadores_en_sala():
            if j.estado != "activo":
                continue
            datos = self._extras(j).get("influencer")
            if not datos or not datos.get("ultimo") or not datos["seguidores"]:
                continue
            hoy = self._hoy(j)
            if datos.get("perdida") == hoy:
                continue
            parte = perdida(hoy - datos["ultimo"])
            datos["perdida"] = hoy
            if parte:
                antes = datos["seguidores"]
                datos["seguidores"] = int(antes * (1 - parte))
                if antes >= PATROCINIO_DESDE > datos["seguidores"]:
                    res.avisos.append(Aviso(j.id, "📉 Bajaste de 1.000 seguidores: se acabaron los patrocinios. "
                                                  "¡Publica para recuperarlos!", [[("📱 Influencer", "influ")]]))
            self._guardar_influ(j, datos)
