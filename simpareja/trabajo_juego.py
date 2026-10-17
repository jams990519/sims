"""Trabajos dentro del juego: horario real, turnos automáticos y flexibles, sueldo y ascensos.

`TrabajoMixin` se mezcla con `Juego`. El empleo de cada jugador se guarda como JSON:
{"clave", "nivel", "dias" (trabajados en este nivel), "horario" {"dias", "inicio", "horas"},
"ultimo" (fecha local del último turno), "aplazado" (fecha en que movió el turno para
cuando se desconecte), "avisado" (fecha en que se le preguntó), "error" (fecha del último
aviso de que no pudo ir), "pasaje" (fecha del último transporte pagado), "rojo", "historial"}.

Reglas: como mucho 8 horas al día. A la hora de su horario el Sim se va solo a trabajar,
aunque el jugador no esté. Si la pareja está conectada a la vez, nunca se le obliga: se le
pregunta si va ahora o cuando se desconecte. Si ese día no repone el turno, no cobra.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import cocina as C
from . import dinero as D
from . import trabajo as T
from . import vida as V
from .db import Jugador

TAPER_HAMBRE = 40  # lo que quita el táper durante el turno
SIN_COMIDA_HAMBRE = 1.5  # sin táper, el hambre baja más rápido trabajando
VOLVER_SIN_TRABAJAR = 30 * 60  # si se fue hace menos, puede volver y trabajar más tarde
RAPIDA_CADA = 30 * 60  # acciones rápidas durante el turno: una cada media hora
ZONAS_HORARIAS = range(-11 * 60, 13 * 60, 60)  # para preguntar qué hora es (UTC−11 … UTC+12: las 24 horas)


def _hora_en(offset_min: int, ts: float) -> str:
    return f"{datetime.fromtimestamp(ts + offset_min * 60, tz=timezone.utc):%H:%M}"


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

    def _horario(self, empleo: dict) -> dict:
        """El horario guardado o, si todavía no lo puso, uno provisional de 8 h."""
        if empleo.get("horario"):
            return empleo["horario"]
        t = T.TRABAJOS[empleo["clave"]]
        dias = T.dias_sugeridos(t.horario, self.rng) if t.horario != T.ROTATIVO else list(range(7))
        return {"dias": dias, "inicio": "09:00", "horas": T.MAX_HORAS}

    def _trabajando(self, j: Jugador) -> dict | None:
        accion = self._accion(j)
        return accion if accion and accion.get("k") == "trabajar" and accion["rfin"] > self.reloj() else None

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_trabajo(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla, duracion

        empleo = self._empleo(j)
        genero = j.ap.get("genero")
        lineas = [aviso, ""] if aviso else []
        if not empleo.get("clave"):
            lineas += [
                "💼 <b>Buscar trabajo</b>",
                "",
                "Elige un trabajo. Luego pones tu <b>horario real</b> (días y horas, máximo 8 al día): "
                "a esa hora tu Sim se va solo a trabajar, aunque no estés, y cobra al terminar "
                f"(menos {D.dinero(T.TRANSPORTE)} de transporte).",
            ]
            botones = [
                [(f"{t.emoji} {t.niveles[0].nombre(genero)} · ${t.niveles[0].por_hora}/h", f"vtrab:{t.clave}")]
                for t in T.TRABAJOS.values()
            ]
            botones.append([("📚 Estudios 🚧", "pronto:estudiar"), ("📱 Influencer 🚧", "pronto:influencer")])
            botones.append([("⬅️ Atrás", "menu")])
            res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")
            return
        ahora = self.reloj()
        hoy = self._hoy(j)
        local = self._local(j)
        t = T.TRABAJOS[empleo["clave"]]
        nivel = empleo["nivel"]
        puesto = t.niveles[nivel - 1]
        horario = self._horario(empleo)
        lineas += [
            f"💼 <b>{puesto.nombre(genero)}</b> · {t.nombre} · nivel {nivel} · ${puesto.por_hora}/h",
            f"🗓️ Tu horario: {T.texto_horario(horario)}" + ("" if empleo.get("horario") else " (provisional)"),
            f"💵 {D.dinero(T.sueldo(t.clave, nivel, horario['horas']))} por día trabajado",
        ]
        if nivel in T.DIAS_PARA_ASCENDER:
            siguiente = t.niveles[nivel]
            lineas.append(
                f"📈 Ascenso: {empleo.get('dias', 0)} de {T.DIAS_PARA_ASCENDER[nivel]} días "
                f"→ {siguiente.nombre(genero)} (${siguiente.por_hora}/h)"
            )
        lineas.append("")
        botones = []
        trabajando = self._trabajando(j)
        if trabajando:
            lineas.append(
                f"▶️ Trabajando hasta las {self._hora(j, trabajando['rfin'])} "
                f"(faltan {duracion(trabajando['rfin'] - ahora)}). El chat sigue abierto 💬"
            )
            botones.append([("📱 Descanso: ver redes", "rapida:redes"), ("🤗 Mandar un abrazo", "rapida:abrazo")])
            botones.append([("📝 Dejar una nota en la nevera", "notan")])
        elif empleo.get("ultimo") == hoy:
            lineas.append(f"✅ Hoy ({V.dia_semana(local.weekday())}) ya trabajaste. ¡A descansar!")
        elif not T.trabaja(horario, local.weekday()):
            lineas.append(f"🌴 Hoy ({V.dia_semana(local.weekday())}) es tu día libre.")
        elif empleo.get("aplazado") == hoy:
            lineas.append("⏰ Moviste el turno: tu Sim se irá a trabajar cuando te desconectes. ¡Disfruten! 💞")
            botones.append([("💼 Ir ahora", "trabajar:ir")])
        else:
            lineas.append(f"🕗 Hoy ({V.dia_semana(local.weekday())}) entras a las {horario['inicio']}.")
            botones.append([("💼 Ir a trabajar ahora", "trabajar:ir"), ("⏰ Cuando me desconecte", "trabajar:luego")])
        botones.append([("🗓️ Mi horario", "hor"), ("📈 Mi carrera", "carrera")])
        botones.append([("🚪 Renunciar o cambiar", "renunciar")])
        botones.append([("📚 Estudios 🚧", "pronto:estudiar"), ("📱 Influencer 🚧", "pronto:influencer")])
        botones.append([("⬅️ Atrás", "menu")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")

    def _b_ver_trabajo(self, j: Jugador, clave: str, res) -> None:
        from .juego import Pantalla

        t = T.TRABAJOS.get(clave)
        if t is None or self._empleo(j).get("clave"):
            self._b_trabajo(j, "", res)
            return
        genero = j.ap.get("genero")
        lineas = [
            f"{t.emoji} <b>{t.nombre}</b>",
            f"🗓️ Horario habitual: {T.HORARIOS[t.horario].lower()} (luego pones el tuyo, máximo 8 h al día)",
            "📋 Requisitos: ninguno para empezar",
            "",
        ]
        for i, p in enumerate(t.niveles, 1):
            lineas.append(f"Nivel {i}: {p.nombre(genero)} · ${p.por_hora}/h")
        lineas += ["", f"Un día de 8 h al empezar: {D.dinero(T.sueldo(clave, 1, 8))}."]
        res.pantalla = Pantalla(
            "\n".join(lineas),
            [[("✅ Aplicar a este trabajo", f"tomar:{clave}")], [("⬅️ Atrás", "trabajo")]],
            clave="trabajo",
        )

    def _b_tomar_trabajo(self, j: Jugador, clave: str, res) -> None:
        t = T.TRABAJOS.get(clave)
        if t is None or self._empleo(j).get("clave"):
            self._b_trabajo(j, "", res)
            return
        self._guardar_empleo(j, {"clave": clave, "nivel": 1, "dias": 0, "ultimo": 0})
        aviso = f"🎉 ¡Te contrataron! Ahora eres {t.niveles[0].nombre(j.ap.get('genero')).lower()}."
        self._b_horario(j, "", res, aviso)

    def _b_renunciar(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        puesto = self._texto_puesto(j)
        if puesto is None:
            self._b_trabajo(j, "", res)
            return
        if self._trabajando(j):
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
    # Mi horario: hora local, días, hora de entrada y horas (máximo 8)
    # ------------------------------------------------------------------

    def _b_horario(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """hor · hor:tz:<min> (o hor:tz:x para cambiarla) · hor:d:<día> · hor:i:<HH:MM> · hor:h:<horas> · hor:ok"""
        from .juego import Pantalla

        empleo = self._empleo(j)
        if not empleo.get("clave"):
            self._b_trabajo(j, "", res)
            return
        extras = self._extras(j)
        paso, _, valor = arg.partition(":")
        borrador = extras.get("horario_tmp") or dict(self._horario(empleo))
        if paso == "tz" and valor == "x":
            extras["hora_ok"] = False
        elif paso == "tz" and valor.lstrip("-").isdigit():
            j.utc_offset = int(valor)
            extras["hora_ok"] = True
        elif paso == "d" and valor.isdigit() and 0 <= int(valor) <= 6:
            borrador["dias"] = sorted(set(borrador["dias"]) ^ {int(valor)})
        elif paso == "i" and valor in T.INICIOS:
            borrador["inicio"] = valor
        elif paso == "h" and valor.isdigit() and int(valor) in T.HORAS_POSIBLES:
            borrador["horas"] = int(valor)
        elif paso == "ok":
            if not borrador["dias"]:
                res.alerta = "Elige al menos un día."
            else:
                empleo["horario"] = borrador
                self._guardar_empleo(j, empleo)
                extras.pop("horario_tmp", None)
                j.extras = json.dumps(extras)
                self.db.guardar_jugador(j)
                self._b_trabajo(j, "", res, "🗓️ ¡Horario guardado! A esa hora tu Sim se irá a trabajar solo.")
                return
        extras["horario_tmp"] = borrador
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        lineas = [aviso, ""] if aviso else []
        lineas.append("🗓️ <b>Tu horario real de trabajo</b>")
        if not extras.get("hora_ok"):
            ahora = self.reloj()
            lineas += ["", "Primero, para usar tu hora local: <b>¿qué hora es ahora donde estás?</b>"]
            opciones = [(f"🕒 {_hora_en(o, ahora)}", f"hor:tz:{o}") for o in ZONAS_HORARIAS]
            botones = [opciones[k:k + 4] for k in range(0, len(opciones), 4)] + [[("⬅️ Atrás", "trabajo")]]
            res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")
            return
        lineas += [
            f"🕒 Tu hora ahora: {self._hora(j, self.reloj())}",
            "",
            f"Quedaría así: <b>{T.texto_horario(borrador)}</b>",
            f"💵 {D.dinero(T.sueldo(empleo['clave'], empleo['nivel'], borrador['horas']))} por día · máximo {T.MAX_HORAS} h",
            "",
            "Toca los días que trabajas, la hora de entrada y las horas:",
        ]
        dias = [((("✅ " if d in borrador["dias"] else "") + T.DIAS_CORTOS[d]), f"hor:d:{d}") for d in range(7)]
        inicios = [((("✅ " if i == borrador["inicio"] else "") + i), f"hor:i:{i}") for i in T.INICIOS]
        horas = [((("✅ " if h == borrador["horas"] else "") + f"{h} h"), f"hor:h:{h}") for h in T.HORAS_POSIBLES]
        botones = [dias[:4], dias[4:]] + [inicios[k:k + 4] for k in range(0, len(inicios), 4)] + [horas]
        botones.append([("✅ Guardar horario", "hor:ok")])
        botones.append([("🕒 Cambiar mi hora local", "hor:tz:x"), ("⬅️ Atrás", "trabajo")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="trabajo")

    # ------------------------------------------------------------------
    # Ir a trabajar
    # ------------------------------------------------------------------

    def _b_trabajar(self, j: Jugador, arg: str, res) -> None:
        """trabajar:ir (ficha) · trabajar:<horas>[:con|sin] · trabajar:luego"""
        from .juego import Pantalla

        empleo = self._empleo(j)
        if not empleo.get("clave"):
            self._b_trabajo(j, "", res)
            return
        if arg == "luego":
            self._aplazar_turno(j, res)
            return
        partes = [p for p in arg.split(":") if p and p != "ir"]
        horas = self._horario(empleo)["horas"]
        if partes and partes[0].isdigit():
            horas = int(partes.pop(0))
        confirmar = partes[0] if partes else ""
        if horas > T.MAX_HORAS or horas < 1:
            res.alerta = f"Como mucho {T.MAX_HORAS} horas al día."
            self._b_trabajo(j, "", res)
            return
        if confirmar not in ("con", "sin"):
            t = T.TRABAJOS[empleo["clave"]]
            lineas = [
                f"💼 <b>Ir a trabajar {horas} h</b> · {t.niveles[empleo['nivel'] - 1].nombre(j.ap.get('genero'))}",
                f"💵 +{D.dinero(T.sueldo(t.clave, empleo['nivel'], horas))} al terminar (🚌 −{D.dinero(T.TRANSPORTE)})",
                f"⚡ −{T.ENERGIA_POR_HORA * horas} energía · ⏱️ sales a las {self._hora(j, self.reloj() + horas * V.HORA)}",
            ]
            botones = []
            if j.taper in C.RECETAS:
                lineas.append(f"🥡 ¿Llevas tu táper de {C.RECETAS[j.taper].nombre.lower()}? Quita {TAPER_HAMBRE} de hambre en el turno.")
                botones.append([("✅ Sí, con táper", f"trabajar:{horas}:con"), ("✅ Sí, sin táper", f"trabajar:{horas}:sin")])
            else:
                lineas.append("🥡 No tienes táper: sin comida, el hambre baja más rápido. (Prepáralo en ⚡ Acciones → Comer.)")
                botones.append([("✅ Sí, ir a trabajar", f"trabajar:{horas}:sin")])
            botones.append([("❌ No, atrás", "trabajo")])
            res.pantalla = Pantalla("\n".join(lineas + ["", "¿Confirmar?"]), botones, clave="trabajo")
            return
        if self._ocupado(j, res):
            return
        error, aviso = self._iniciar_turno(j, horas, llevar_taper=confirmar == "con")
        if error:
            res.alerta = error
            self._b_trabajo(j, "", res)
            return
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        res.pantalla = self._pantalla_sim(j, aviso)

    def _iniciar_turno(self, j: Jugador, horas: int, llevar_taper: bool) -> tuple[str | None, str]:
        """Empieza un turno (a mano o automático). Devuelve (error, aviso)."""
        empleo = self._empleo(j)
        horario = self._horario(empleo)
        hoy = self._hoy(j)
        nec = self._nec(j)
        if empleo.get("ultimo") == hoy:
            return "Hoy ya trabajaste.", ""
        if not T.trabaja(horario, self._local(j).weekday()):
            return "Hoy es tu día libre.", ""
        if V.de_mal_humor(nec):
            return "😡 Con mal humor no se puede trabajar: atiende la necesidad que está en 0.", ""
        if empleo.get("pasaje") != hoy:  # si volvió a casa al rato, el pasaje de hoy ya está pagado
            if not self._pagar(j, T.TRANSPORTE, "🚌 Transporte al trabajo"):
                return f"💸 No alcanza ni para el transporte ({D.dinero(T.TRANSPORTE)}).", ""
            empleo["pasaje"] = hoy
        empleo["ultimo"] = hoy
        empleo["rojo"] = bool(V.en_rojo(nec))
        empleo.pop("aplazado", None)
        self._guardar_empleo(j, empleo)
        datos = self._empezar(j, V.ACCIONES["trabajar"], str(horas), None, self.reloj())
        aviso = f"💼 ¡A trabajar! Sale a las {self._hora(j, datos['rfin'])} y cobra al terminar."
        if j.taper and llevar_taper:
            # El táper le quita el hambre a mitad del turno.
            datos["ef"]["hambre"] = datos["ef"].get("hambre", 0) + TAPER_HAMBRE
            aviso += f"\n🥡 Lleva su táper de {C.RECETAS[j.taper].nombre.lower() if j.taper in C.RECETAS else 'comida'}."
            j.taper = ""
        else:
            datos["mult"] = {"hambre": SIN_COMIDA_HAMBRE}
            aviso += "\n⚠️ Va sin comida: el hambre bajará más rápido. (Prepara un táper la próxima vez.)"
        if empleo["rojo"]:
            aviso += "\n⚠️ Va con necesidades en rojo: este día no contará para el ascenso."
        j.accion = json.dumps(datos)
        self.db.guardar_jugador(j)
        return None, aviso

    def _aplazar_turno(self, j: Jugador, res) -> None:
        """Mover el turno de hoy para cuando el jugador se desconecte."""
        empleo = self._empleo(j)
        hoy = self._hoy(j)
        ahora = self.reloj()
        trabajando = self._trabajando(j)
        if trabajando:
            if ahora - trabajando["rini"] > VOLVER_SIN_TRABAJAR:
                res.alerta = "Ya lleva un buen rato trabajando: para el turno si quieres volver."
                self._b_trabajo(j, "", res)
                return
            self._vivir(j, ahora)
            j.accion = None
            j.lugar = V.HABITACION_INICIAL
            if empleo.get("ultimo") == hoy:
                empleo["ultimo"] = 0
        elif empleo.get("ultimo") == hoy:
            res.alerta = "Hoy ya trabajaste."
            self._b_trabajo(j, "", res)
            return
        empleo["aplazado"] = hoy
        self._guardar_empleo(j, empleo)
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        self._b_trabajo(j, "", res, "⏰ Listo: tu Sim irá a trabajar cuando te desconectes y cobrará igual.")

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
        hambre = round(6 * horas * accion.get("mult", {}).get("hambre", 1) - accion["ef"].get("hambre", 0))
        texto += f"\n⚡ −{round(T.ENERGIA_POR_HORA * horas)} energía · 🍔 {'−' if hambre >= 0 else '+'}{abs(hambre)} hambre"
        historial = empleo.get("historial", [])
        historial.append({"dia": self._dia(j, accion["rini"]), "semana": self._local(j, accion["rini"]).weekday(),
                          "horas": round(horas, 1), "pago": pago, "completo": completo})
        empleo["historial"] = historial[-10:]
        if completo and not empleo.get("rojo"):
            empleo["dias"] = empleo.get("dias", 0) + 1
            if T.puede_ascender(empleo["nivel"], empleo["dias"]):
                empleo["nivel"] += 1
                empleo["dias"] = 0
                nuevo = T.TRABAJOS[empleo["clave"]].niveles[empleo["nivel"] - 1]
                texto += f"\n🎉 <b>¡Ascenso!</b> Ahora es {nuevo.nombre(j.ap.get('genero')).lower()} (${nuevo.por_hora}/h)."
        elif not completo:
            texto += " (turno incompleto: no cuenta para el ascenso)"
        if empleo["nivel"] in T.DIAS_PARA_ASCENDER and "Ascenso" not in texto:
            faltan = T.DIAS_PARA_ASCENDER[empleo["nivel"]] - empleo.get("dias", 0)
            texto += f"\n📈 Faltan {faltan} día(s) para el ascenso."
        empleo.pop("rojo", None)
        j.trabajo = json.dumps(empleo)
        self.db.guardar_jugador(j)
        return texto

    def _b_carrera(self, j: Jugador, arg: str, res) -> None:
        """💼 Trabajo → Mi carrera: nivel, progreso e historial."""
        from .juego import Pantalla

        empleo = self._empleo(j)
        if not empleo.get("clave"):
            res.alerta = "Todavía no tienes trabajo."
            self._b_trabajo(j, "", res)
            return
        t = T.TRABAJOS[empleo["clave"]]
        genero = j.ap.get("genero")
        lineas = [f"📈 <b>Mi carrera</b> · {t.emoji} {t.nombre}", ""]
        for i, p in enumerate(t.niveles, 1):
            marca = "👉" if i == empleo["nivel"] else ("✅" if i < empleo["nivel"] else "▫️")
            lineas.append(f"{marca} Nivel {i}: {p.nombre(genero)} · ${p.por_hora}/h")
        if empleo["nivel"] in T.DIAS_PARA_ASCENDER:
            total = T.DIAS_PARA_ASCENDER[empleo["nivel"]]
            hechos = empleo.get("dias", 0)
            lineas += ["", f"Progreso: {'🟩' * hechos}{'⬜' * (total - hechos)} {hechos}/{total} días"]
        historial = empleo.get("historial", [])
        if historial:
            lineas += ["", "<b>Últimos turnos</b>"]
            for turno in reversed(historial):
                marca = "✅" if turno.get("completo") else "⏹️"
                cuando = f"{V.dia_semana(turno['semana'])} (día {turno['dia']})" if "semana" in turno else f"Día {turno['dia']}"
                lineas.append(f"{marca} {cuando}: {turno['horas']} h · {D.dinero(turno['pago'])}")
        res.pantalla = Pantalla("\n".join(lineas), [[("⬅️ Atrás", "trabajo")]], clave="carrera")

    # ------------------------------------------------------------------
    # Acciones rápidas durante el turno
    # ------------------------------------------------------------------

    def _b_rapida(self, j: Jugador, que: str, res) -> None:
        from .juego import Aviso

        if not self._trabajando(j):
            res.alerta = "Las acciones rápidas son para los descansos del trabajo."
            self._b_trabajo(j, "", res)
            return
        ahora = self.reloj()
        extras = self._extras(j)
        if ahora - extras.get("rapida_ts", 0) < RAPIDA_CADA:
            res.alerta = "☕ El descanso es cada media hora. ¡A seguir trabajando!"
            self._b_trabajo(j, "", res)
            return
        self._vivir(j, ahora)
        nec = self._nec(j)
        if que == "abrazo":
            pareja = self._pareja_en_sala(j)
            if pareja is None:
                res.alerta = "No tienes pareja en la sala."
                self._b_trabajo(j, "", res)
                return
            self._vivir(pareja, ahora)
            nec_p = self._nec(pareja)
            nec_p["social"] = min(100, nec_p.get("social", 0) + 5)
            pareja.necesidades = json.dumps(nec_p)
            self.db.guardar_jugador(pareja)
            nec["social"] = min(100, nec.get("social", 0) + 5)
            res.avisos.append(Aviso(pareja.id, f"🤗 {self._firma(j)} te mandó un abrazo desde el trabajo 💞 (+5 💬 social)"))
            texto = "🤗 Abrazo enviado: +5 💬 social para los dos."
        else:
            nec["diversion"] = min(100, nec.get("diversion", 0) + 5)
            nec["social"] = min(100, nec.get("social", 0) + 3)
            texto = "📱 Descanso: +5 🎉 diversión, +3 💬 social."
        j.necesidades = json.dumps(nec)
        extras["rapida_ts"] = ahora
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        self._b_trabajo(j, "", res, texto)

    # ------------------------------------------------------------------
    # Turnos automáticos (cada minuto)
    # ------------------------------------------------------------------

    def _tick_trabajo(self, res) -> None:
        from .juego import Aviso

        ahora = self.reloj()
        for j in self.db.jugadores_en_sala():
            if j.estado != "activo":
                continue
            empleo = self._empleo(j)
            if not empleo.get("clave") or not empleo.get("horario"):
                continue
            horario = empleo["horario"]
            local = self._local(j)
            hoy = local.toordinal()
            if empleo.get("ultimo") == hoy or not T.trabaja(horario, local.weekday()):
                continue
            h, m = (int(x) for x in horario["inicio"].split(":"))
            if local < local.replace(hour=h, minute=m, second=0, microsecond=0) or self._trabajando(j):
                continue
            en_linea = self._estado_presencia(j, ahora) == "en_linea"
            pareja = self._pareja_en_sala(j)
            juntos = en_linea and pareja is not None and self._estado_presencia(pareja, ahora) == "en_linea"
            if empleo.get("aplazado") == hoy:
                if en_linea:
                    continue  # se irá cuando se desconecte
            elif juntos:
                # Tiempo juntos protegido: nunca se les obliga a ir a trabajar.
                if empleo.get("avisado") != hoy:
                    empleo["avisado"] = hoy
                    self._guardar_empleo(j, empleo)
                    res.avisos.append(Aviso(
                        j.id,
                        f"💼 Es tu hora de trabajar ({horario['inicio']}), pero estás con {self._firma(pareja)}. "
                        "No te obligo: ¿qué hacemos?",
                        [[("💼 Ir ahora", "trabajar:ir"), ("⏰ Cuando me desconecte", "trabajar:luego")]],
                    ))
                continue
            accion = self._accion(j)
            if accion and accion.get("k") == "cocinar":
                continue  # termina de cocinar primero
            if accion:  # deja lo que estaba haciendo (por ejemplo, se despierta)
                self._vivir(j, ahora)
                j.accion = None
                self.db.guardar_jugador(j)
            self._descongelar(j, ahora)
            error, aviso = self._iniciar_turno(j, horario["horas"], llevar_taper=True)
            if error:
                empleo = self._empleo(j)
                if empleo.get("error") != hoy:
                    empleo["error"] = hoy
                    self._guardar_empleo(j, empleo)
                    res.avisos.append(Aviso(j.id, f"💼 Tu Sim no pudo ir a trabajar: {error}", [[("💼 Trabajo", "trabajo")]]))
                continue
            botones = [[("⏰ Quedarme: ir cuando me desconecte", "trabajar:luego")]] if en_linea else []
            res.avisos.append(Aviso(j.id, f"🕗 {self._firma(j)} se fue a trabajar. {aviso}", botones))
            res.ediciones += self._refrescar_sala(j.sala_id)
