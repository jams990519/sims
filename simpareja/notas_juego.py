"""Notas en la nevera (actualización 2, parte 8).

`NotasMixin` se mezcla con `Juego`. Un jugador deja un mensaje en la nevera y su pareja lo ve
al entrar al juego (también al volver de la pausa). Mientras no la lea, el menú lo marca.

En `extras` del hogar: "notas" [{de, para, texto, ts, leida}], las últimas 20.
"""

from __future__ import annotations

import json

from .db import Jugador

NOTA_MAX = 300
NOTAS = 20


class NotasMixin:
    def _notas_sin_leer(self, j: Jugador) -> list[dict]:
        if j.sala_id is None:
            return []
        notas = self._extras_hogar(self._hogar(j.sala_id)).get("notas", [])
        return [n for n in notas if n["para"] == j.id and not n.get("leida")]

    def _leer_notas(self, j: Jugador) -> list[str]:
        """Las notas nuevas para `j`, ya marcadas como leídas (para mostrarlas al entrar)."""
        from .juego import duracion, esc

        if not self._notas_sin_leer(j):
            return []
        h = self._hogar(j.sala_id)
        extras = self._extras_hogar(h)
        lineas = []
        for n in extras.get("notas", []):
            if n["para"] == j.id and not n.get("leida"):
                n["leida"] = True
                de = self.db.jugador(n["de"])
                lineas.append(
                    f"📝 <b>Nota en la nevera</b> de {self._firma(de) if de else '…'} "
                    f"(hace {duracion(self.reloj() - n['ts'])}):\n«{esc(n['texto'])}»"
                )
        self._guardar_extras_hogar(h, extras)
        return lineas

    def _b_notas(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """🏠 Casa → 📝 Notas en la nevera."""
        from .juego import Pantalla, duracion, esc

        sin_leer = {(n["de"], n["ts"]) for n in self._notas_sin_leer(j)}
        self._leer_notas(j)  # al abrir la nevera, quedan leídas
        notas = self._extras_hogar(self._hogar(j.sala_id)).get("notas", [])
        lineas = [aviso, ""] if aviso else []
        lineas += ["📝 <b>Notas en la nevera</b>", ""]
        for n in reversed(notas[-8:]):
            quien = "Tú" if n["de"] == j.id else esc(getattr(self.db.jugador(n["de"]), "personaje", "…"))
            marca = "🆕 " if (n["de"], n["ts"]) in sin_leer else ""
            leida = " ✓ leída" if n["de"] == j.id and n.get("leida") else ""
            lineas.append(f"{marca}{quien} · hace {duracion(self.reloj() - n['ts'])}{leida}:\n«{esc(n['texto'])}»")
        if not notas:
            lineas.append("No hay notas. Deja una: tu pareja la verá al entrar al juego.")
        res.pantalla = Pantalla(
            "\n".join(lineas),
            [[("✍️ Dejar una nota", "notan")], [("⬅️ Atrás", "mcasa")]],
            clave="notas",
        )

    def _b_nota_nueva(self, j: Jugador, arg: str, res) -> None:
        """notan: el próximo texto que escriba es la nota."""
        from .juego import Pantalla

        if self._pareja_en_sala(j) is None:
            res.alerta = "Las notas son para tu pareja: invítala con 💌."
            self._b_notas(j, "", res)
            return
        extras = self._extras(j)
        extras["nota_pendiente"] = {"ts": self.reloj()}
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.pantalla = Pantalla(
            "📝 Escribe la nota para la nevera. Tu pareja la verá al entrar al juego:",
            [[("⬅️ Atrás", "notas")]],
            clave="notaesc",
        )

    def _nota_escrita(self, j: Jugador, texto: str, res) -> None:
        from .juego import esc

        extras = self._extras(j)
        extras.pop("nota_pendiente", None)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        pareja = self._pareja_en_sala(j)
        if pareja is None:
            self._b_notas(j, "", res)
            return
        h = self._hogar(j.sala_id)
        extras_h = self._extras_hogar(h)
        nota = {"de": j.id, "para": pareja.id, "texto": texto.strip()[:NOTA_MAX], "ts": self.reloj(), "leida": False}
        extras_h["notas"] = (extras_h.get("notas", []) + [nota])[-NOTAS:]
        self._guardar_extras_hogar(h, extras_h)
        self._b_notas(j, "", res, f"📝 Nota pegada en la nevera. {esc(pareja.personaje)} la verá al entrar al juego.")
