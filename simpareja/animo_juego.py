"""Estado de ánimo con foto (actualización 2, parte 6).

`AnimoMixin` se mezcla con `Juego`. Al cambiar de ánimo se elige el color y, si se quiere, se
agrega una foto y una frase corta. La pareja recibe un aviso con la foto, la ve en el perfil
(color, foto, frase y hora) y las fotos anteriores quedan en el álbum.

Las fotos no se descargan: se guarda el `file_id` de Telegram, que sirve para volver a enviarlas.
En `extras` del jugador: "animo_pendiente" {animo, frase, ts} mientras elige la foto,
"animo_actual" {animo, frase, foto, ts} y "animos" (historial, los últimos 30).
"""

from __future__ import annotations

import json

from . import personaje as P
from .db import EN_JUEGO, Jugador

FRASE_MAX = 120
ESPERA_FOTO = 10 * 60  # cuánto espera la foto o la frase después de elegir el color
HISTORIAL = 30


class AnimoMixin:
    def _animo_pendiente(self, j: Jugador) -> dict | None:
        """El ánimo elegido que espera foto o frase (si la última pantalla fue esa y no pasó mucho)."""
        pendiente = self._extras(j).get("animo_pendiente")
        uc = self.db.ultima_conexion(j.id)
        if pendiente and uc and uc.pantalla == "animofoto" and self.reloj() - pendiente["ts"] < ESPERA_FOTO:
            return pendiente
        return None

    def _b_animos(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla, en_filas, esc

        ap = j.ap
        genero, actual = ap.get("genero"), ap.get("animo")
        opciones = [
            (("✅ " if o.clave == actual else "") + o.boton(genero), f"animo:{o.clave}")
            for o in P.ANIMO.opciones
        ]
        res.pantalla = Pantalla(
            f"🎭 <b>¿Cómo se siente {esc(j.personaje)} ahora?</b>\n"
            "Elige el color. Después puedes agregar una foto y una frase corta: tu pareja recibe un aviso.",
            en_filas(opciones) + [[("⬅️ Atrás", "mest")]],
            clave="animo",
        )

    def _b_animo(self, j: Jugador, clave: str, res) -> None:
        """animo:<clave>: elige el color y espera la foto o la frase (opcionales)."""
        if P.ANIMO.opcion(clave) is None:
            self._b_animos(j, "", res)
            return
        extras = self._extras(j)
        extras["animo_pendiente"] = {"animo": clave, "frase": "", "ts": self.reloj()}
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.pantalla = self._pantalla_animo_foto(j)

    def _pantalla_animo_foto(self, j: Jugador, aviso: str | None = None):
        from .juego import Pantalla, esc

        pendiente = self._extras(j)["animo_pendiente"]
        opcion = P.ANIMO.opcion(pendiente["animo"])
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"🎭 Tu ánimo: <b>{opcion.boton(j.ap.get('genero'))}</b>",
            "",
            "📸 Si quieres, <b>mándame una foto</b> (la frase puede ir en el pie de foto) "
            "o <b>escribe una frase corta</b>.",
        ]
        if pendiente["frase"]:
            lineas += ["", f"💬 Frase: «{esc(pendiente['frase'])}»", "Ahora puedes mandar la foto o publicarlo así."]
        publicar = "✅ Publicar" + ("" if pendiente["frase"] else " sin foto")
        return Pantalla(
            "\n".join(lineas),
            [[(publicar, "animop")], [("❌ Cancelar", "animos")]],
            clave="animofoto",
        )

    def _frase_animo(self, j: Jugador, texto: str, res) -> None:
        extras = self._extras(j)
        extras["animo_pendiente"]["frase"] = " ".join(texto.split())[:FRASE_MAX]
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.pantalla = self._pantalla_animo_foto(j, "✍️ Frase guardada.")

    def _b_publicar_animo(self, j: Jugador, arg: str, res) -> None:
        """animop: publica el ánimo elegido sin foto."""
        if not self._extras(j).get("animo_pendiente"):
            self._b_animos(j, "", res)
            return
        self._publicar_animo(j, None, "", res)

    def _publicar_animo(self, j: Jugador, foto: str | None, pie: str, res) -> None:
        from .juego import Aviso, esc

        ahora = self.reloj()
        extras = self._extras(j)
        pendiente = extras.pop("animo_pendiente")
        frase = " ".join(pie.split())[:FRASE_MAX] or pendiente["frase"]
        ap = j.ap
        ap["animo"] = pendiente["animo"]
        j.apariencia = json.dumps(ap, ensure_ascii=False)
        registro = {"animo": pendiente["animo"], "frase": frase, "foto": foto, "ts": ahora}
        extras["animo_actual"] = registro
        extras["animos"] = (extras.get("animos", []) + [registro])[-HISTORIAL:]
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        texto = f"🎭 {self._firma(j)} ahora se siente: <b>{P.animo(ap)}</b>"
        if frase:
            texto += f"\n💬 «{esc(frase)}»"
        botones = [[("👀 Ver su perfil", "perfil")]]
        pregunta = self._pregunta_por_animo(j)  # según el ánimo aparece una pregunta para los dos
        if pregunta:
            botones = [[("✍️ Responder", "pregr"), ("👀 Ver su perfil", "perfil")]]
        for o in self._companeros(j):
            if o.estado == "activo":
                extra = f"\n\n{self._texto_pregunta(o, pregunta)}" if pregunta else ""
                res.avisos.append(Aviso(o.id, texto + extra, botones, foto=foto))
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        res.alerta = f"Ánimo: {P.animo(ap)}"
        aviso = "🎭 ¡Listo! Tu pareja recibió el aviso" + (" con tu foto 📸." if foto else ".")
        if pregunta:
            aviso += f"\n\n{self._texto_pregunta(j, pregunta)}\nRespóndanla los dos en 💕 Pareja → ❓ Preguntas."
        res.pantalla = self._pantalla_sala(j, aviso if self._companeros(j) else "🎭 ¡Listo!")

    # ------------------------------------------------------------------
    # Ver las fotos: perfil y álbum
    # ------------------------------------------------------------------

    def _texto_animo_actual(self, viendo: Jugador, de: Jugador) -> list[str]:
        """Color, frase y hora del ánimo de `de`, para el perfil."""
        from .juego import duracion, esc

        actual = self._extras(de).get("animo_actual")
        animo = P.animo(de.ap)
        if not actual or actual["animo"] != de.ap.get("animo"):
            return [f"🎭 {animo or 'Sin estado de ánimo'}"]
        lineas = [
            f"🎭 {animo} · desde las {self._hora(viendo, actual['ts'])} "
            f"(hace {duracion(self.reloj() - actual['ts'])})"
        ]
        if actual.get("frase"):
            lineas.append(f"💬 «{esc(actual['frase'])}»")
        if actual.get("foto"):
            lineas.append("📸 Con foto")
        return lineas

    def _fecha_corta(self, j: Jugador, ts: float) -> str:
        local = self._local(j, ts)
        return f"{local.day}/{local.month}"

    def _fotos(self, j: Jugador) -> list[dict]:
        return [r for r in self._extras(j).get("animos", []) if r.get("foto")]

    def _b_foto_animo(self, j: Jugador, arg: str, res) -> None:
        """fotoan:<id>[:<n>]: envía la foto de ánimo (la actual, o la n del álbum) como mensaje."""
        from .juego import Aviso, esc

        uid, _, n = arg.partition(":")
        de = self.db.jugador(int(uid)) if uid.isdigit() else None
        if de is None or de.sala_id != j.sala_id:
            res.alerta = "Esa foto ya no está."
            return
        fotos = self._fotos(de)
        if n.isdigit():
            registro = fotos[int(n)] if int(n) < len(fotos) else None
        else:
            registro = self._extras(de).get("animo_actual")
        if not registro or not registro.get("foto"):
            res.alerta = "Esa foto ya no está."
            return
        opcion = P.ANIMO.opcion(registro["animo"])
        pie = f"{self._firma(de)} · {opcion.boton(de.ap.get('genero')) if opcion else ''} · {self._reloj(j, registro['ts'])}"
        if registro.get("frase"):
            pie += f"\n💬 «{esc(registro['frase'])}»"
        res.avisos.append(Aviso(j.id, pie, foto=registro["foto"]))
        res.alerta = "📸 Te la envío abajo."

    def _b_album(self, j: Jugador, arg: str, res) -> None:
        """💕 Pareja → 📸 Álbum: las fotos de ánimo de los dos y las respuestas que les gustaron."""
        from .juego import Pantalla, esc

        miembros = [m for m in self.db.miembros_sala(j.sala_id) if m.estado in EN_JUEGO]
        lineas = ["📸 <b>Álbum de recuerdos</b>", ""]
        botones = []
        hay = False
        for m in miembros:
            fotos = self._fotos(m)
            if not fotos:
                continue
            hay = True
            lineas.append(f"{self._firma(m)}: {len(fotos)} foto(s) de ánimo")
            fila = []
            for i, registro in reversed(list(enumerate(fotos))):
                opcion = P.ANIMO.opcion(registro["animo"])
                fila.append((f"{opcion.color if opcion else '📸'} {self._hora(j, registro['ts'])}", f"fotoan:{m.id}:{i}"))
            botones += [fila[k:k + 3] for k in range(0, min(len(fila), 9), 3)]
        if not hay:
            lineas.append("Todavía no hay fotos. Cambia tu 🎭 estado de ánimo y agrega una foto: se guardan aquí.")
        recuerdos = self._extras_hogar(self._hogar(j.sala_id)).get("recuerdos", [])
        for tipo, titulo in (("hito", "🏆 <b>Hitos</b>"), ("aniversario", "🎂 <b>Aniversarios</b>"), ("cita", "🌹 <b>Citas</b>")):
            de_tipo = [r for r in recuerdos if r["tipo"] == tipo]
            if de_tipo:
                lineas += ["", titulo] + [f"{r['texto']} · {self._fecha_corta(j, r['ts'])}" for r in reversed(de_tipo[-5:])]
        respuestas = [r for r in recuerdos if r["tipo"] == "respuesta"]
        if respuestas:
            lineas += ["", "💬 <b>Respuestas que les gustaron</b>"]
            for r in reversed(respuestas[-5:]):
                de = self.db.jugador(r["de"])
                lineas.append(f"❓ {esc(r['pregunta'])}\n   {esc(de.personaje) if de else '…'}: «{esc(r['texto'])}»")
        botones.append([("🎭 Mi ánimo", "animos"), ("⬅️ Atrás", "mpar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="album")
