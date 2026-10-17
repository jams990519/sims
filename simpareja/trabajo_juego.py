"""Trabajos dentro del juego (parte 6): elegir empleo, trabajar por horas, cobrar y ascender.

`TrabajoMixin` se mezcla con `Juego`. El empleo de cada jugador se guarda como JSON:
{"clave", "nivel", "dias" (trabajados en este nivel), "ultimo" (último día trabajado),
"libres" (días de la semana libres), "rojo" (si empezó el turno con necesidades en rojo)}.
"""

from __future__ import annotations

import json

from . import dinero as D
from . import trabajo as T
from . import vida as V
from .db import Jugador


class TrabajoMixin:
    def _empleo(self, j: Jugador) -> dict:
        return json.loads(j.trabajo or "{}")

    def _guardar_empleo(self, j: Jugador, empleo: dict) -> None:
        j.trabajo = json.dumps(empleo)
        self.db.guardar_jugador(j)

    def _puesto(self, j: Jugador, empleo: dict | None = None) -> T.Puesto | None:
        empleo = empleo if empleo is not None else self._empleo(j)
        t = T.TRABAJOS.get(empleo.get("clave", ""))
        return t.niveles[empleo.get("nivel", 1) - 1] if t else None

    def _texto_puesto(self, j: Jugador) -> str | None:
        empleo = self._empleo(j)
        puesto = self._puesto(j, empleo)
        if puesto is None:
            return None
        t = T.TRABAJOS[empleo["clave"]]
        return f"{t.emoji} {puesto.nombre(j.ap.get('genero'))} · ${puesto.por_hora}/h"

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_trabajo(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        empleo = self._empleo(j)
        genero = j.ap.get("genero")
        lineas = [aviso, ""] if aviso else []
        if not empleo.get("clave"):
            lineas += [
                "💼 <b>Buscar trabajo</b>",
                "",
                "Elige un trabajo. Es automático: decides cuántas horas trabajas y cobras al terminar "
                f"(menos {D.dinero(T.TRANSPORTE)} de transporte). Con días trabajados sin necesidades en rojo, llegan los ascensos.",
            ]
            botones = [
                [(f"{t.emoji} {t.niveles[0].nombre(genero)} · ${t.niveles[0].por_hora}/h", f"vtrab:{t.clave}")]
                for t in T.TRABAJOS.values()
            ]
            botones.append([("🧍 Mi Sim", "sim")])
            res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")
            return
        ahora = self.reloj()
        s = self._segundos_juego(j, ahora)
        dia = V.dia_de_juego(s)
        t = T.TRABAJOS[empleo["clave"]]
        nivel = empleo["nivel"]
        puesto = t.niveles[nivel - 1]
        lineas += [
            f"💼 <b>{puesto.nombre(genero)}</b> · {t.nombre} · nivel {nivel} · ${puesto.por_hora}/h",
            f"🗓️ {T.HORARIOS[t.horario]}" + (f" (libras {T.texto_libres(empleo['libres'])})" if t.horario == T.ROTATIVO else ""),
        ]
        if nivel in T.DIAS_PARA_ASCENDER:
            siguiente = t.niveles[nivel]
            lineas.append(
                f"📈 Ascenso: {empleo.get('dias', 0)} de {T.DIAS_PARA_ASCENDER[nivel]} días trabajados "
                f"→ {siguiente.nombre(genero)} (${siguiente.por_hora}/h)"
            )
        else:
            lineas.append("🏆 Ya estás en lo más alto de este trabajo.")
        lineas.append("")
        accion = self._accion(j)
        botones = []
        if accion and accion.get("k") == "trabajar" and accion["rfin"] > ahora:
            lineas.append(f"▶️ Trabajando hasta las {V.hora_texto(accion['fin'])}.")
        elif empleo.get("ultimo") == dia:
            lineas.append(f"✅ Hoy ({V.dia_semana(dia)}) ya trabajaste. ¡A descansar!")
        elif not T.trabaja_hoy(empleo["libres"], dia):
            lineas.append(f"🌴 Hoy ({V.dia_semana(dia)}) es tu día libre.")
        else:
            lineas.append(f"🕗 Hoy ({V.dia_semana(dia)}) te toca trabajar. ¿Cuántas horas?")
            botones.append([
                (f"{h} h · {D.dinero(T.sueldo(t.clave, nivel, h))}", f"trabajar:{h}") for h in T.HORAS_POSIBLES[:2]
            ])
            botones.append([
                (f"{h} h · {D.dinero(T.sueldo(t.clave, nivel, h))}", f"trabajar:{h}") for h in T.HORAS_POSIBLES[2:]
            ])
            lineas.append(f"⚡ Gasta {T.ENERGIA_POR_HORA} de energía por hora. 🚌 Transporte: {D.dinero(T.TRANSPORTE)}.")
        botones.append([("🚪 Renunciar", "renunciar"), ("🧍 Mi Sim", "sim")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")

    def _b_ver_trabajo(self, j: Jugador, clave: str, res) -> None:
        from .juego import Pantalla

        t = T.TRABAJOS.get(clave)
        if t is None or self._empleo(j).get("clave"):
            self._b_trabajo(j, "", res)
            return
        genero = j.ap.get("genero")
        lineas = [f"{t.emoji} <b>{t.nombre}</b>", f"🗓️ {T.HORARIOS[t.horario]}", ""]
        for i, p in enumerate(t.niveles, 1):
            lineas.append(f"Nivel {i}: {p.nombre(genero)} · ${p.por_hora}/h")
        lineas += ["", f"Un día de 8 h al empezar: {D.dinero(T.sueldo(clave, 1, 8))}."]
        res.pantalla = Pantalla(
            "\n".join(lineas),
            [[("✅ Aceptar este trabajo", f"tomar:{clave}")], [("⬅️ Ver otros", "trabajo")]],
            clave="trabajo",
        )

    def _b_tomar_trabajo(self, j: Jugador, clave: str, res) -> None:
        t = T.TRABAJOS.get(clave)
        if t is None or self._empleo(j).get("clave"):
            self._b_trabajo(j, "", res)
            return
        empleo = {"clave": clave, "nivel": 1, "dias": 0, "ultimo": 0,
                  "libres": T.dias_libres(t.horario, self.rng)}
        self._guardar_empleo(j, empleo)
        aviso = f"🎉 ¡Tienes trabajo! Ahora eres {t.niveles[0].nombre(j.ap.get('genero')).lower()}."
        self._b_trabajo(j, "", res, aviso)

    def _b_renunciar(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        puesto = self._texto_puesto(j)
        if puesto is None:
            self._b_trabajo(j, "", res)
            return
        accion = self._accion(j)
        if accion and accion.get("k") == "trabajar":
            res.alerta = "Estás trabajando. Para el turno primero."
            self._b_trabajo(j, "", res)
            return
        if arg != "si":
            res.pantalla = Pantalla(
                f"🚪 ¿Seguro que quieres renunciar a <b>{puesto}</b>?\n"
                "Si buscas otro trabajo, empezarás otra vez desde abajo.",
                [[("✅ Sí, renunciar", "renunciar:si")], [("⬅️ No", "trabajo")]],
                clave="trabajo",
            )
            return
        self._guardar_empleo(j, {})
        self._b_trabajo(j, "", res, "🚪 Renunciaste. Puedes buscar otro trabajo cuando quieras.")

    # ------------------------------------------------------------------
    # Trabajar
    # ------------------------------------------------------------------

    def _b_trabajar(self, j: Jugador, horas: str, res) -> None:
        empleo = self._empleo(j)
        if not empleo.get("clave"):
            self._b_trabajo(j, "", res)
            return
        if self._ocupado(j, res):
            return
        ahora = self.reloj()
        dia = V.dia_de_juego(self._segundos_juego(j, ahora))
        nec = self._nec(j)
        error = None
        if not horas.isdigit() or int(horas) not in T.HORAS_POSIBLES:
            error = "Elige cuántas horas."
        elif empleo.get("ultimo") == dia:
            error = "Hoy ya trabajaste."
        elif not T.trabaja_hoy(empleo["libres"], dia):
            error = "Hoy es tu día libre."
        elif V.de_mal_humor(nec):
            error = "😡 Con mal humor no se puede trabajar: atiende la necesidad que está en 0."
        elif not self._pagar(j, T.TRANSPORTE, "🚌 Transporte al trabajo"):
            error = f"💸 No alcanza ni para el transporte ({D.dinero(T.TRANSPORTE)})."
        if error:
            res.alerta = error
            self._b_trabajo(j, "", res)
            return
        empleo["ultimo"] = dia
        empleo["rojo"] = bool(V.en_rojo(nec))
        self._guardar_empleo(j, empleo)
        datos = self._empezar(j, V.ACCIONES["trabajar"], horas, None, ahora)
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        aviso = f"💼 ¡A trabajar! Sales a las {V.hora_texto(datos['fin'])} y cobras al terminar."
        if empleo["rojo"]:
            aviso += "\n⚠️ Vas con necesidades en rojo: este día no contará para el ascenso."
        res.pantalla = self._pantalla_sim(j, aviso)

    def _cobrar_turno(self, j: Jugador, accion: dict, hasta: float, completo: bool) -> str:
        """Paga las horas trabajadas y, si el turno fue completo y sin rojos, cuenta para el ascenso."""
        empleo = self._empleo(j)
        if not empleo.get("clave"):
            return ""
        horas = max(0.0, (min(hasta, accion["fin"]) - accion["ini"]) / V.HORA)
        pago = T.sueldo(empleo["clave"], empleo["nivel"], horas)
        if pago > 0:
            j.cartera += pago
            self._anotar_movimiento(
                j.sala_id, j.id, "cartera", pago,
                f"💼 Sueldo: {horas:.1f} h".replace(".0 h", " h"),
            )
        texto = f" Cobró {D.dinero(pago)} 👛"
        if completo and not empleo.get("rojo"):
            empleo["dias"] = empleo.get("dias", 0) + 1
            if T.puede_ascender(empleo["nivel"], empleo["dias"]):
                empleo["nivel"] += 1
                empleo["dias"] = 0
                nuevo = T.TRABAJOS[empleo["clave"]].niveles[empleo["nivel"] - 1]
                texto += f"\n🎉 <b>¡Ascenso!</b> Ahora es {nuevo.nombre(j.ap.get('genero')).lower()} (${nuevo.por_hora}/h)."
        elif not completo:
            texto += " (turno incompleto: no cuenta para el ascenso)"
        empleo.pop("rojo", None)
        j.trabajo = json.dumps(empleo)
        self.db.guardar_jugador(j)
        return texto
