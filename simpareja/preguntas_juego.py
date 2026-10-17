"""Preguntas de pareja (actualización 2, parte 7).

`PreguntasMixin` se mezcla con `Juego`. Aparecen preguntas según el color del estado de ánimo:
al cambiar de ánimo (si no hay otra pregunta reciente) o cuando alguien pide una nueva.
Los dos responden y cada quien marca la respuesta del otro con «me gustó» o «no me gustó»:
- Me gustó: sube el medidor de quien la valora y la respuesta se guarda en el álbum.
- No me gustó: no baja nada solo; se ofrece hablarlo en el chat o bajar el medidor a mano.
Queda registro de qué temas gustan más.

En `extras` del hogar: "pregunta" (la de ahora), "preguntas" (las anteriores), "temas"
({tema: [me gustó, no me gustó]}) y "recuerdos" (para el álbum). En `extras` del jugador:
"preg_pendiente" mientras escribe su respuesta.
"""

from __future__ import annotations

import json

from . import personaje as P
from . import preguntas as Q
from .db import Hogar, Jugador

ME_GUSTO = 3  # lo que sube el medidor de quien marca «me gustó»
RESPUESTA_MAX = 500
ARCHIVO = 20
NUEVA_CADA = 12 * 60 * 60  # al cambiar de ánimo, como mucho una pregunta automática cada 12 h
RECUERDOS = 50


class PreguntasMixin:
    def _pregunta(self, h: Hogar) -> dict | None:
        return self._extras_hogar(h).get("pregunta")

    def _nueva_pregunta(self, h: Hogar, para: Jugador, por: Jugador | None) -> dict:
        """Elige una pregunta según el ánimo de `para` y la deja como la pregunta de ahora."""
        extras = self._extras_hogar(h)
        anterior = extras.get("pregunta")
        if anterior:
            extras["preguntas"] = (extras.get("preguntas", []) + [anterior])[-ARCHIVO:]
        recientes = [p["texto"] for p in extras.get("preguntas", [])]
        animo = para.ap.get("animo") or "feliz"
        tema, texto = Q.elegir(animo, recientes, self.rng)
        extras["preg_n"] = extras.get("preg_n", 0) + 1
        pregunta = {
            "id": extras["preg_n"], "tema": tema, "texto": texto, "animo": animo, "para": para.id,
            "por": por.id if por else None, "ts": self.reloj(), "respuestas": {}, "valoraciones": {},
        }
        extras["pregunta"] = pregunta
        self._guardar_extras_hogar(h, extras)
        return pregunta

    def _pregunta_por_animo(self, j: Jugador) -> dict | None:
        """Al cambiar de ánimo, aparece una pregunta para los dos (si no hay otra reciente)."""
        if self._pareja_en_sala(j) is None:
            return None
        h = self._hogar(j.sala_id)
        actual = self._pregunta(h)
        if actual and self.reloj() - actual["ts"] < NUEVA_CADA:
            return None
        return self._nueva_pregunta(h, para=j, por=None)

    def _texto_pregunta(self, j: Jugador, pregunta: dict) -> str:
        from .juego import esc

        para = self.db.jugador(pregunta["para"])
        opcion = P.ANIMO.opcion(pregunta["animo"])
        color = opcion.boton(para.ap.get("genero")) if opcion and para else ""
        quien = "tu ánimo" if para and para.id == j.id else f"el ánimo de {esc(para.personaje) if para else '…'}"
        return f"❓ <b>{esc(pregunta['texto'])}</b>\n<i>Según {quien}: {color} · {Q.TEMAS.get(pregunta['tema'], '')}</i>"

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_preguntas(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💕 Pareja → ❓ Preguntas."""
        from .juego import Pantalla, esc

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "Las preguntas son para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        h = self._hogar(j.sala_id)
        pregunta = self._pregunta(h)
        lineas = [aviso, ""] if aviso else []
        lineas += ["❓ <b>Preguntas de pareja</b>", ""]
        botones = []
        if pregunta is None:
            lineas.append("Según el estado de ánimo aparecen preguntas para conocerse mejor: los dos responden "
                          "y cada quien dice si le gustó la respuesta del otro.")
        else:
            lineas += [self._texto_pregunta(j, pregunta), ""]
            for m in (j, pareja):
                respuesta = pregunta["respuestas"].get(str(m.id))
                nombre = "Tú" if m.id == j.id else esc(m.personaje)
                if respuesta:
                    lineas.append(f"{nombre}: «{esc(respuesta)}»")
                    valor = pregunta["valoraciones"].get(str(m.id))
                    if valor:
                        lineas.append("   " + ("💗 Le gustó" if valor == "si" else "🙈 No le convenció"))
                    elif m.id == pareja.id:
                        botones.append([("💗 Me gustó", f"pregv:{pregunta['id']}:1"),
                                        ("🙈 No me gustó", f"pregv:{pregunta['id']}:0")])
                else:
                    lineas.append(f"{nombre}: ⏳ falta responder")
            if str(j.id) not in pregunta["respuestas"]:
                botones.insert(0, [("✍️ Responder", "pregr")])
        botones.append([("🎲 Nueva pregunta", "pregn"), ("📊 Temas", "pregt")])
        botones.append([("⬅️ Atrás", "mpar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="preguntas")

    def _b_nueva_pregunta(self, j: Jugador, arg: str, res) -> None:
        """pregn: una pregunta nueva según el ánimo de la pareja (se la haces tú)."""
        from .juego import Aviso

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            self._b_preguntas(j, "", res)
            return
        pregunta = self._nueva_pregunta(self._hogar(j.sala_id), para=pareja, por=j)
        res.avisos.append(Aviso(
            pareja.id,
            f"❓ {self._firma(j)} te hace una pregunta:\n{self._texto_pregunta(pareja, pregunta)}",
            [[("✍️ Responder", "pregr")]],
        ))
        self._b_preguntas(j, "", res, "🎲 Pregunta nueva: respóndanla los dos.")

    def _b_responder(self, j: Jugador, arg: str, res) -> None:
        """pregr: el próximo texto que escriba es su respuesta."""
        from .juego import Pantalla

        pregunta = self._pregunta(self._hogar(j.sala_id))
        if pregunta is None or str(j.id) in pregunta["respuestas"]:
            self._b_preguntas(j, "", res)
            return
        extras = self._extras(j)
        extras["preg_pendiente"] = {"id": pregunta["id"], "ts": self.reloj()}
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.pantalla = Pantalla(
            f"{self._texto_pregunta(j, pregunta)}\n\n✍️ Escribe tu respuesta:",
            [[("⬅️ Atrás", "preg")]],
            clave="pregresp",
        )

    def _respuesta_escrita(self, j: Jugador, texto: str, res) -> None:
        """El texto que escribió después de «✍️ Responder»: le llega a la pareja para que lo valore."""
        from .juego import Aviso, esc

        extras = self._extras(j)
        pendiente = extras.pop("preg_pendiente", None)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        h = self._hogar(j.sala_id)
        extras_h = self._extras_hogar(h)
        pregunta = extras_h.get("pregunta")
        if pendiente is None or pregunta is None or pregunta["id"] != pendiente["id"]:
            self._b_preguntas(j, "", res, "Esa pregunta ya cambió.")
            return
        respuesta = texto.strip()[:RESPUESTA_MAX]
        pregunta["respuestas"][str(j.id)] = respuesta
        self._guardar_extras_hogar(h, extras_h)
        if len(pregunta["respuestas"]) >= 2:
            self._avanzar_reto(h, "preguntas", pregunta["id"])
        pareja = self._pareja_en_sala(j)
        if pareja is not None:
            res.avisos.append(Aviso(
                pareja.id,
                f"❓ {self._firma(j)} respondió «{esc(pregunta['texto'])}»:\n💬 «{esc(respuesta)}»",
                [[("💗 Me gustó", f"pregv:{pregunta['id']}:1"), ("🙈 No me gustó", f"pregv:{pregunta['id']}:0")]]
                + ([[("✍️ Responder yo también", "pregr")]] if str(pareja.id) not in pregunta["respuestas"] else []),
                chat=True,
            ))
        self._b_preguntas(j, "", res, "💬 Respuesta enviada.")

    def _b_valorar(self, j: Jugador, arg: str, res) -> None:
        """pregv:<id>:<1|0>: me gustó o no me gustó la respuesta de la pareja."""
        from .juego import Aviso, Pantalla, esc

        pid, _, valor = arg.partition(":")
        h = self._hogar(j.sala_id)
        extras_h = self._extras_hogar(h)
        pregunta = extras_h.get("pregunta")
        if pregunta is None or str(pregunta["id"]) != pid:
            pregunta = next((p for p in extras_h.get("preguntas", []) if str(p["id"]) == pid), None)
        pareja = self._pareja_en_sala(j)
        respuesta = pregunta["respuestas"].get(str(pareja.id)) if pregunta and pareja else None
        if not respuesta:
            res.alerta = "Esa respuesta ya no está."
            self._b_preguntas(j, "", res)
            return
        if pregunta["valoraciones"].get(str(pareja.id)):
            res.alerta = "Ya la valoraste."
            self._b_preguntas(j, "", res)
            return
        gusto = valor == "1"
        pregunta["valoraciones"][str(pareja.id)] = "si" if gusto else "no"
        tema = extras_h.setdefault("temas", {}).setdefault(pregunta["tema"], [0, 0])
        tema[0 if gusto else 1] += 1
        if gusto:
            recuerdo = {"tipo": "respuesta", "pregunta": pregunta["texto"], "texto": respuesta,
                        "de": pareja.id, "ts": self.reloj()}
            extras_h["recuerdos"] = (extras_h.get("recuerdos", []) + [recuerdo])[-RECUERDOS:]
        self._guardar_extras_hogar(h, extras_h)
        if gusto:
            subio = self._cambiar_relacion(j, ME_GUSTO, "❓ Me gustó su respuesta", auto=True)
            res.avisos.append(Aviso(
                pareja.id,
                f"💗 A {self._firma(j)} le gustó tu respuesta a «{esc(pregunta['texto'])}»"
                + (f" (+{subio} en su medidor)." if subio else ".") + " Quedó en el álbum 📸.",
            ))
            self._b_preguntas(j, "", res, f"💗 ¡Anotado! Tu medidor subió {subio} y la respuesta quedó en el álbum."
                              if subio else "💗 ¡Anotado! La respuesta quedó en el álbum.")
            return
        res.avisos.append(Aviso(
            pareja.id,
            f"🙈 A {self._firma(j)} no le convenció tu respuesta a «{esc(pregunta['texto'])}». ¿Lo hablan en el chat?",
            [[("💬 Chat", "sala")]],
        ))
        res.pantalla = Pantalla(
            "🙈 Anotado. No baja nada solo.\n\n¿Quieres hablarlo en el chat o bajar tu medidor?",
            [[("💬 Hablarlo en el chat", "sala"), ("➖ Bajar mi medidor", "rel:-")], [("⬅️ Atrás", "preg")]],
            clave="preguntas",
        )

    def _b_temas(self, j: Jugador, arg: str, res) -> None:
        """pregt: qué temas gustan más y las últimas preguntas."""
        from .juego import Pantalla, esc

        extras_h = self._extras_hogar(self._hogar(j.sala_id))
        temas = extras_h.get("temas", {})
        lineas = ["📊 <b>Temas que más les gustan</b>", ""]
        if temas:
            for tema, (si, no) in sorted(temas.items(), key=lambda t: (-t[1][0], t[1][1])):
                lineas.append(f"{Q.TEMAS.get(tema, tema)}: 💗 {si} · 🙈 {no}")
        else:
            lineas.append("Todavía no han valorado respuestas.")
        anteriores = extras_h.get("preguntas", [])[-5:]
        if anteriores:
            lineas += ["", "<b>Últimas preguntas</b>"]
            lineas += [f"❓ {esc(p['texto'])} ({len(p['respuestas'])}/2 respuestas)" for p in reversed(anteriores)]
        res.pantalla = Pantalla("\n".join(lineas), [[("⬅️ Atrás", "preg")]], clave="preguntas")
