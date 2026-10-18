"""Narración de las acciones (versión 0.34).

`NarracionMixin` se mezcla con `Juego`. Cada minuto, a quien está haciendo una acción con narración le
llega el mensajito de la etapa que toca (sin sonido, para no molestar). En el restaurante la carta deja
elegir el plato y al final preguntan por el postre.

En la acción guardada del jugador: "nar" (cuántas etapas ya llegaron) y, en el restaurante,
"rest" {lugar, plato, postre}.
"""

from __future__ import annotations

import json

from . import narracion as N
from .db import Jugador


class NarracionMixin:
    def _quiere_narracion(self, uid: int) -> bool:
        """Los mensajitos se pueden apagar en ⚙️ Ajustes."""
        j = self.db.jugador(uid)
        return j is not None and self._extras(j).get("narracion", True)

    def _b_narracion(self, j: Jugador, arg: str, res) -> None:
        """⚙️ Ajustes: encender o apagar los mensajitos de las acciones."""
        extras = self._extras(j)
        extras["narracion"] = not extras.get("narracion", True)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        self._b_ajustes(j, "", res)

    def _tick_narracion(self, ahora: float, res) -> None:
        for j in self.db.jugadores_en_sala():
            j = self.db.jugador(j.id) or j
            accion = self._accion(j) if j.estado == "activo" and self._extras(j).get("narracion", True) else None
            etapas = N.ETAPAS.get(accion["k"]) if accion else None
            if not etapas or accion["rfin"] <= ahora:
                continue
            progreso = (ahora - accion["rini"]) / max(1.0, accion["rfin"] - accion["rini"])
            i = N.siguiente(etapas, accion.get("nar", 0), progreso)
            if i is None:
                continue
            accion["nar"] = i + 1
            aviso = self._narrar(j, accion, etapas[i])
            j.accion = json.dumps(accion)
            self.db.guardar_jugador(j)
            res.avisos.append(aviso)

    def _narrar(self, j: Jugador, accion: dict, etapa: N.Etapa):
        from .juego import Aviso

        juntos = accion.get("con") is not None
        cuando = N.momento(self._hora_local(j))
        extra, botones = "", []
        if accion["k"] == "restaurante":
            # En una cita los dos empezaron a la vez: el mismo restaurante para los dos.
            lugar = N.RESTAURANTES[int(accion["rini"] // 60) % len(N.RESTAURANTES)]
            rest = accion.setdefault("rest", {"lugar": lugar, "plato": None, "postre": None})
            if etapa.pregunta == "carta" and not rest["plato"]:
                botones = [[(f"{e} {nombre[0].upper()}{nombre[1:]}", f"rplato:{clave}")]
                           for clave, (e, nombre) in N.PLATOS.items()]
            elif etapa.pregunta == "postre":
                botones = [[("🍰 Sí, un postre", "rpostre:si"), ("🧾 No, la cuenta", "rpostre:no")]]
            elif "{plato}" in etapa.solo and not rest["plato"]:
                rest["plato"] = N.DE_LA_CASA
                extra = "🤵 Como no te decidías, el mesero te recomendó lo de la casa.\n"
            e, nombre = N.PLATOS.get(rest["plato"] or N.DE_LA_CASA)
            texto = etapa.texto(juntos, cuando).format(lugar=rest["lugar"], plato=f"{e} {nombre}")
        else:
            texto = etapa.texto(juntos, cuando)
        return Aviso(j.id, extra + texto, botones, silencio=not botones, foto=self._dibujo(j, accion, etapa, cuando))

    def _dibujo(self, j: Jugador, accion: dict, etapa: N.Etapa, cuando: str) -> str | None:
        """'ilus:escena:momento:figuras' (el bot lo dibuja), si la etapa tiene dibujo y el jugador los quiere."""
        if not etapa.escena or not self._extras(j).get("fotos", True):
            return None
        figuras = N.letra(j.ap.get("genero"))
        pareja = self.db.jugador(accion["con"]) if accion.get("con") else None
        if pareja is not None:
            figuras += N.letra(pareja.ap.get("genero"))
        return f"ilus:{etapa.escena}:{cuando}:{figuras}"

    def _b_fotos(self, j: Jugador, arg: str, res) -> None:
        """⚙️ Ajustes: encender o apagar los dibujos de los mensajitos (gastan algo más de datos)."""
        extras = self._extras(j)
        extras["fotos"] = not extras.get("fotos", True)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        self._b_ajustes(j, "", res)

    # ------------------------------------------------------------------
    # Restaurante: la carta y el postre
    # ------------------------------------------------------------------

    def _restaurante_actual(self, j: Jugador) -> dict | None:
        accion = self._accion(j)
        if accion and accion["k"] == "restaurante" and accion["rfin"] > self.reloj() and "rest" in accion:
            return accion
        return None

    def _b_restaurante_plato(self, j: Jugador, clave: str, res) -> None:
        """rplato:<plato>: lo que pides de la carta."""
        from .juego import Pantalla

        accion = self._restaurante_actual(j)
        if accion is None or clave not in N.PLATOS:
            res.alerta = "Ya no estás en el restaurante."
            return
        rest = accion["rest"]
        if rest["plato"]:
            e, nombre = N.PLATOS[rest["plato"]]
            res.alerta = f"Ya pediste {nombre}."
            return
        rest["plato"] = clave
        j.accion = json.dumps(accion)
        self.db.guardar_jugador(j)
        e, nombre = N.PLATOS[clave]
        res.pantalla = Pantalla(f"📜 Pediste {e} <b>{nombre}</b>. ¡Buena elección! 👌\n🤵 El mesero lo anota y se va a la cocina.")

    def _b_restaurante_postre(self, j: Jugador, arg: str, res) -> None:
        """rpostre:si|no."""
        from .juego import Pantalla

        accion = self._restaurante_actual(j)
        if accion is None:
            res.alerta = "Ya no estás en el restaurante."
            return
        rest = accion["rest"]
        if rest.get("postre") is not None:
            res.alerta = "Eso ya está decidido."
            return
        if arg != "si":
            rest["postre"] = False
            j.accion = json.dumps(accion)
            self.db.guardar_jugador(j)
            res.pantalla = Pantalla("🧾 Sin postre esta vez: el mesero trae la cuenta.")
            return
        if not self._pagar(j, N.POSTRE, "🍰 Postre en el restaurante"):
            res.alerta = f"No alcanza para el postre (${N.POSTRE})."
            return
        j = self.db.jugador(j.id)
        rest["postre"] = True
        j.accion = json.dumps(accion)
        self.db.guardar_jugador(j)
        self._sumar_necesidades(j, {"hambre": 5, "diversion": 5})
        postre = self.rng.choice(N.POSTRES)
        res.pantalla = Pantalla(f"😋 Te traen {postre}. ¡Delicioso! (+5 🍔 · +5 🎉 · ${N.POSTRE})")
