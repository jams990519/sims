"""Medidor de relación (diseño v1, parte 8; la actualización 2 lo usa en preguntas, hitos y retos).

`RelacionMixin` se mezcla con `Juego`. Cada jugador tiene un medidor, de 0 a 100 %, de lo que
siente por su pareja. Lo mueve cuando quiere, hacia arriba o hacia abajo, y dice qué lo causó;
queda un historial. Algunas cosas del juego lo suben solas (por ejemplo, una respuesta que gustó).

En `extras` del jugador: "relacion" (el valor) y "relacion_hist" (los últimos cambios).
"""

from __future__ import annotations

import json

from .db import Jugador

INICIAL = 50
HISTORIAL = 30
CANTIDADES = (1, 5, 10)
MOTIVO_MAX = 80
MOTIVOS = {
    "+": (
        "💞 Tiempo juntos", "🍳 Cocinó para mí", "🤗 Un abrazo o un beso", "💬 Una buena charla",
        "🎁 Un detalle", "🧹 Ayudó en casa", "😂 Me hizo reír", "💪 Me apoyó",
    ),
    "-": (
        "😤 Una discusión", "🙈 No me hizo caso", "🧹 No ayudó en casa", "⏰ Llegó tarde o no vino",
        "📱 Mucho tiempo en el móvil", "💸 Gastó de más", "😔 Me faltó su compañía",
    ),
}


def barra_relacion(valor: int) -> str:
    llenos = (valor + 5) // 10  # redondeo hacia arriba en la mitad
    return "❤️" * llenos + "🤍" * (10 - llenos)


class RelacionMixin:
    def _relacion(self, j: Jugador) -> int:
        return self._extras(j).get("relacion", INICIAL)

    def _cambiar_relacion(self, j: Jugador, delta: int, motivo: str, auto: bool = False) -> int:
        """Mueve el medidor de `j` (lo que siente por su pareja) y lo anota. Devuelve el cambio real."""
        extras = self._extras(j)
        antes = extras.get("relacion", INICIAL)
        despues = max(0, min(100, antes + delta))
        extras["relacion"] = despues
        cambio = despues - antes
        if cambio:
            registro = {"d": cambio, "m": motivo, "ts": self.reloj()}
            if auto:
                registro["auto"] = True
            extras["relacion_hist"] = (extras.get("relacion_hist", []) + [registro])[-HISTORIAL:]
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        return cambio

    def _b_medidor(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💕 Pareja → 💗 Medidor de relación."""
        from .juego import Pantalla, duracion, esc

        pareja = self._pareja_en_sala(j)
        if pareja is None:
            res.alerta = "El medidor es para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        ahora = self.reloj()
        yo, otro = self._relacion(j), self._relacion(pareja)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            "💗 <b>Medidor de relación</b>",
            "Lo que cada quien siente por el otro. Cada quien mueve el suyo cuando quiere y dice por qué.",
            "",
            f"Tú → {esc(pareja.personaje)}: {barra_relacion(yo)} <b>{yo} %</b>",
            f"{esc(pareja.personaje)} → tú: {barra_relacion(otro)} <b>{otro} %</b>",
        ]
        cambios = [(j, r) for r in self._extras(j).get("relacion_hist", [])]
        cambios += [(pareja, r) for r in self._extras(pareja).get("relacion_hist", [])]
        cambios.sort(key=lambda c: c[1]["ts"], reverse=True)
        if cambios:
            lineas += ["", "<b>Últimos cambios</b>"]
            for quien, r in cambios[:8]:
                nombre = "Tú" if quien.id == j.id else esc(quien.personaje)
                lineas.append(f"{nombre}: {'+' if r['d'] > 0 else '−'}{abs(r['d'])} · {esc(r['m'])} · hace {duracion(ahora - r['ts'])}")
        botones = [
            [("➕ Subir el mío", "rel:+"), ("➖ Bajar el mío", "rel:-")],
            [("⬅️ Atrás", "mpar")],
        ]
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="medidor")

    def _b_relacion(self, j: Jugador, arg: str, res) -> None:
        """rel:<+|-> (cuánto) · rel:<+|->:<n> (por qué) · rel:<+|->:<n>:<motivo|otro>."""
        from .juego import Pantalla

        pareja = self._pareja_en_sala(j)
        signo, _, resto = arg.partition(":")
        cantidad, _, motivo = resto.partition(":")
        if pareja is None or signo not in MOTIVOS:
            self._b_medidor(j, "", res)
            return
        verbo = "subir" if signo == "+" else "bajar"
        if not cantidad.isdigit() or int(cantidad) not in CANTIDADES:
            res.pantalla = Pantalla(
                f"💗 ¿Cuánto quieres {verbo} tu medidor? Ahora está en {self._relacion(j)} %.",
                [[(f"{signo}{n}", f"rel:{signo}:{n}") for n in CANTIDADES], [("⬅️ Atrás", "medidor")]],
                clave="medidor",
            )
            return
        if motivo == "otro":
            extras = self._extras(j)
            extras["rel_pendiente"] = {"d": int(cantidad) * (1 if signo == "+" else -1), "ts": self.reloj()}
            j.extras = json.dumps(extras)
            self.db.guardar_jugador(j)
            res.pantalla = Pantalla(
                "✍️ Escribe el motivo en una frase corta:",
                [[("⬅️ Atrás", f"rel:{signo}:{cantidad}")]],
                clave="relmotivo",
            )
            return
        if not motivo.isdigit() or int(motivo) >= len(MOTIVOS[signo]):
            opciones = [[(m, f"rel:{signo}:{cantidad}:{i}")] for i, m in enumerate(MOTIVOS[signo])]
            res.pantalla = Pantalla(
                f"💗 {signo}{cantidad} · ¿Qué lo causó?",
                opciones + [[("✍️ Otro motivo", f"rel:{signo}:{cantidad}:otro")], [("⬅️ Atrás", f"rel:{signo}")]],
                clave="medidor",
            )
            return
        delta = int(cantidad) * (1 if signo == "+" else -1)
        self._aplicar_relacion(j, pareja, delta, MOTIVOS[signo][int(motivo)], res)

    def _motivo_escrito(self, j: Jugador, texto: str, res) -> None:
        """El texto que escribió después de «✍️ Otro motivo»."""
        extras = self._extras(j)
        pendiente = extras.pop("rel_pendiente", None)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        pareja = self._pareja_en_sala(j)
        if pendiente is None or pareja is None:
            self._b_medidor(j, "", res)
            return
        motivo = "✍️ " + " ".join(texto.split())[:MOTIVO_MAX]
        self._aplicar_relacion(j, pareja, pendiente["d"], motivo, res)

    def _aplicar_relacion(self, j: Jugador, pareja: Jugador, delta: int, motivo: str, res) -> None:
        from .juego import Aviso, esc

        cambio = self._cambiar_relacion(j, delta, motivo)
        valor = self._relacion(j)
        if not cambio:
            self._b_medidor(j, "", res, f"💗 Tu medidor ya está en {valor} %.")
            return
        flecha = "subió" if cambio > 0 else "bajó"
        res.avisos.append(Aviso(
            pareja.id,
            f"💗 {self._firma(j)} {flecha} su medidor {'+' if cambio > 0 else '−'}{abs(cambio)} "
            f"por «{esc(motivo)}». Ahora siente un {valor} %.",
            [[("💗 Ver el medidor", "medidor"), ("💬 Chat", "sala")]],
        ))
        self._b_medidor(j, "", res, f"💗 Listo: tu medidor {flecha} a {valor} %. {esc(pareja.personaje)} recibió un aviso.")
