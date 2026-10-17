"""Estudios (diseño v1, parte 10).

`EstudiosMixin` se mezcla con `Juego`. En 💼 Trabajo → Estudios (o ⚡ Acciones → Estudiar):
- Cursos cortos online: de $50 a $150, una hora al día durante unos días. Dan habilidad y aceleran
  los ascensos (+2 días de progreso en el trabajo).
- Certificados técnicos: de $400 a $800, dos horas al día durante unas semanas. Permiten entrar a un
  trabajo directamente en el nivel 2.
- Carrera: $300 al mes durante varios meses. Abre los mejores puestos (nivel 3).
Se estudia una sesión al día. Estudiar juntos es más rápido y sube la relación.

En `extras` del jugador: "estudio" {clave, sesiones, ultimo (fecha), pagado_hasta}, "estudios_hechos",
"certificados" [trabajo], "titulo" y "credito" (días de ascenso guardados para el próximo trabajo).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import dinero as D
from . import trabajo as T
from .db import Jugador

ASCENSO_CURSO = 2
RELACION_JUNTOS = 2
MES = 30


@dataclass(frozen=True)
class Estudio:
    clave: str
    emoji: str
    nombre: str
    tipo: str  # "curso" | "certificado" | "carrera"
    precio: int  # total; en la carrera, por mes
    sesiones: int
    horas: int  # por sesión
    efecto: str
    trabajo: str = ""  # el certificado es para este trabajo


ESTUDIOS: dict[str, Estudio] = {e.clave: e for e in (
    Estudio("ofimatica", "💻", "Curso de ofimática", "curso", 80, 5, 1, "+2 días para el ascenso."),
    Estudio("ingles", "🗣️", "Curso de inglés", "curso", 120, 6, 1, "+2 días para el ascenso."),
    Estudio("atencion", "🤝", "Curso de atención al cliente", "curso", 50, 4, 1, "+2 días para el ascenso."),
    Estudio("redes", "📱", "Curso de redes sociales", "curso", 60, 4, 1, "+2 días para el ascenso y +50 de experiencia de influencer."),
    Estudio("cocina", "👨‍🍳", "Curso de cocina", "curso", 150, 5, 1, "+2 días para el ascenso y el súper crece antes (+3 recetas)."),
    Estudio("cert_manicura", "💅", "Certificado de uñas", "certificado", 400, 10, 2, "Entrar en manicura en el nivel 2.", "manicura"),
    Estudio("cert_foto", "📸", "Certificado de fotografía", "certificado", 600, 12, 2, "Entrar en el estudio de fotografía en el nivel 2.", "foto"),
    Estudio("cert_super", "🛒", "Certificado de comercio", "certificado", 450, 10, 2, "Entrar en el súper en el nivel 2.", "super"),
    Estudio("cert_reparto", "🚚", "Certificado de logística", "certificado", 500, 10, 2, "Entrar en reparto en el nivel 2.", "reparto"),
    Estudio("cert_cocina", "🍳", "Certificado de cocina profesional", "certificado", 550, 12, 2, "Entrar en la cocina de restaurante en el nivel 2.", "cocina"),
    Estudio("cert_oficina", "🛎️", "Certificado de administración", "certificado", 800, 14, 2, "Entrar en la oficina en el nivel 2.", "recepcion"),
    Estudio("cert_taller", "🔧", "Certificado de mecánica", "certificado", 700, 14, 2, "Entrar en el taller en el nivel 2.", "taller"),
    Estudio("carrera", "🎓", "Carrera universitaria", "carrera", 300, 90, 2, "Abre los mejores puestos: el nivel 3 de tu trabajo."),
)}
TIPOS = (("curso", "💻 <b>Cursos cortos online</b>"), ("certificado", "📜 <b>Certificados técnicos</b>"),
         ("carrera", "🎓 <b>Carrera</b>"))


class EstudiosMixin:
    def _estudio(self, j: Jugador) -> dict | None:
        return self._extras(j).get("estudio")

    def _guardar_extras(self, j: Jugador, extras: dict) -> None:
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)

    def _falta_estudio(self, j: Jugador, a) -> str | None:
        if a.clave != "estudiar":
            return None
        estudio = self._estudio(j)
        if estudio is None:
            return "📚 Primero inscríbete en algo en 💼 Trabajo → Estudios."
        if estudio.get("ultimo") == self._hoy(j):
            return "📚 Hoy ya estudiaste: mañana, la siguiente sesión."
        if estudio.get("debe"):
            return "💸 Deben la mensualidad de la carrera: pónganse al día en 💼 Trabajo → Estudios."
        return None

    def _nivel_por_estudios(self, j: Jugador, trabajo: str) -> int:
        """En qué nivel entra a un trabajo según lo que estudió."""
        extras = self._extras(j)
        if extras.get("titulo"):
            return 3
        return 2 if trabajo in extras.get("certificados", []) else 1

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_estudios(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """💼 Trabajo → 📚 Estudios."""
        from .juego import Pantalla

        extras = self._extras(j)
        estudio = self._estudio(j)
        hechos = extras.get("estudios_hechos", [])
        lineas = [aviso, ""] if aviso else []
        lineas += ["📚 <b>Estudios</b>", "Una sesión al día. Estudiar juntos es más rápido y sube la relación.", ""]
        botones = []
        if estudio:
            e = ESTUDIOS[estudio["clave"]]
            hecho = estudio["sesiones"]
            barra = "🟩" * round(10 * hecho / e.sesiones) + "⬜" * (10 - round(10 * hecho / e.sesiones))
            lineas += [f"✏️ Estudias: {e.emoji} <b>{e.nombre}</b>", f"{barra} {hecho}/{e.sesiones} sesiones · {e.horas} h cada una"]
            if estudio.get("debe"):
                lineas.append(f"💸 Deben la mensualidad ({D.dinero(e.precio)}): hasta pagarla no hay clases.")
                botones.append([(f"💳 Pagar la mensualidad ({D.dinero(e.precio)})", "estpagar")])
            elif estudio.get("ultimo") == self._hoy(j):
                lineas.append("✅ Hoy ya estudiaste.")
            else:
                botones.append([(f"📚 Estudiar hoy ({e.horas} h)", f"a:estudiar:{e.horas}")])
            botones.append([("🚪 Dejarlo", "estno")])
            lineas.append("")
        else:
            for tipo, titulo in TIPOS:
                lineas.append(titulo)
                for e in ESTUDIOS.values():
                    if e.tipo != tipo:
                        continue
                    if e.clave in hechos:
                        lineas.append(f"✅ {e.emoji} {e.nombre}")
                        continue
                    precio = f"{D.dinero(e.precio)}/mes" if e.tipo == "carrera" else D.dinero(e.precio)
                    lineas.append(f"{e.emoji} {e.nombre} · {precio} · {e.sesiones} × {e.horas} h: <i>{e.efecto}</i>")
                    botones.append([(f"{e.emoji} {e.nombre} · {precio}", f"estin:{e.clave}")])
                lineas.append("")
        if extras.get("titulo"):
            lineas.append("🎓 Tienes título universitario.")
        if extras.get("certificados"):
            nombres = ", ".join(T.TRABAJOS[t].nombre.lower() for t in extras["certificados"] if t in T.TRABAJOS)
            lineas.append(f"📜 Certificados: {nombres}.")
        botones.append([("💼 Trabajo", "trabajo"), ("⬅️ Atrás", "macc")])
        res.pantalla = Pantalla("\n".join(lineas).rstrip(), botones, clave="estudios")

    def _b_inscribirse(self, j: Jugador, clave: str, res) -> None:
        e = ESTUDIOS.get(clave)
        extras = self._extras(j)
        if e is None or extras.get("estudio") or clave in extras.get("estudios_hechos", []):
            self._b_estudios(j, "", res)
            return
        if not self._pagar(j, e.precio, f"{e.emoji} {e.nombre}" + (" (primer mes)" if e.tipo == "carrera" else "")):
            res.alerta = f"No alcanza: cuesta {D.dinero(e.precio)}."
            self._b_estudios(j, "", res)
            return
        j = self.db.jugador(j.id)  # _pagar pudo cambiar la cartera
        extras = self._extras(j)
        extras["estudio"] = {"clave": clave, "sesiones": 0, "ultimo": None, "pagado_hasta": self._hoy(j) + MES}
        self._guardar_extras(j, extras)
        self._b_estudios(j, "", res, f"✅ ¡Te inscribiste en {e.nombre.lower()}! Una sesión al día.")

    def _b_dejar_estudio(self, j: Jugador, arg: str, res) -> None:
        extras = self._extras(j)
        estudio = extras.pop("estudio", None)
        self._guardar_extras(j, extras)
        nombre = ESTUDIOS[estudio["clave"]].nombre.lower() if estudio else "el estudio"
        self._b_estudios(j, "", res, f"🚪 Dejaste {nombre}. Lo pagado no se devuelve.")

    # ------------------------------------------------------------------
    # Al terminar una sesión, y la mensualidad de la carrera
    # ------------------------------------------------------------------

    def _sesion_estudio(self, j: Jugador, accion: dict) -> str:
        if accion["k"] != "estudiar":
            return ""
        extras = self._extras(j)
        estudio = extras.get("estudio")
        if not estudio:
            return ""
        hoy = self._hoy(j, accion["rini"])
        if estudio.get("ultimo") == hoy:
            return ""
        estudio["ultimo"] = hoy
        estudio["sesiones"] += 1
        e = ESTUDIOS[estudio["clave"]]
        texto = f" 📚 Sesión {estudio['sesiones']}/{e.sesiones} de {e.nombre.lower()}."
        if estudio["sesiones"] >= e.sesiones:
            extras.pop("estudio")
            extras["estudios_hechos"] = extras.get("estudios_hechos", []) + [e.clave]
        j.extras = json.dumps(extras)
        if accion.get("con"):  # después de guardar el progreso: _cambiar_relacion relee los extras
            self._cambiar_relacion(j, RELACION_JUNTOS, "📚 Estudiamos juntos", auto=True)
        if estudio["sesiones"] < e.sesiones:
            return texto
        return texto + " " + self._terminar_estudio(j, e)

    def _terminar_estudio(self, j: Jugador, e: Estudio) -> str:
        """El premio de terminar: ascenso más rápido, certificado o título."""
        empleo = self._empleo(j)
        texto = f"🎉 <b>¡Terminaste {e.nombre.lower()}!</b>"
        extras = self._extras(j)
        if e.tipo == "curso":
            if empleo.get("clave"):
                empleo["dias"] = empleo.get("dias", 0) + ASCENSO_CURSO
                j.trabajo = json.dumps(empleo)
                texto += f" +{ASCENSO_CURSO} días para el ascenso."
            else:
                extras["credito"] = extras.get("credito", 0) + ASCENSO_CURSO
                texto += f" Te cuenta +{ASCENSO_CURSO} días en tu próximo trabajo."
            if e.clave == "redes":
                influ = self._influ(j)
                influ["xp"] += 50
                extras["influencer"] = influ
            if e.clave == "cocina" and j.sala_id is not None:
                h = self._hogar(j.sala_id)
                ex = self._extras_hogar(h)
                ex["cocinadas"] = ex.get("cocinadas", 0) + 3
                self._guardar_extras_hogar(h, ex)
        elif e.tipo == "certificado":
            extras["certificados"] = sorted(set(extras.get("certificados", [])) | {e.trabajo})
            if empleo.get("clave") == e.trabajo and empleo.get("nivel", 1) < 2:
                empleo.update(nivel=2, dias=0)
                j.trabajo = json.dumps(empleo)
                texto += " ¡Subes al nivel 2 de tu trabajo!"
            else:
                texto += f" Puedes entrar a {T.TRABAJOS[e.trabajo].nombre.lower()} en el nivel 2."
        else:
            extras["titulo"] = True
            if empleo.get("clave") and empleo.get("nivel", 1) < 3:
                empleo.update(nivel=3, dias=0)
                j.trabajo = json.dumps(empleo)
                texto += " 🎓 ¡Con tu título llegas al mejor puesto de tu trabajo!"
            else:
                texto += " 🎓 Con tu título, los trabajos nuevos te reciben en el mejor puesto."
        j.extras = json.dumps(extras)
        return texto

    def _b_pagar_carrera(self, j: Jugador, arg: str, res) -> None:
        estudio = self._estudio(j)
        if not estudio or not estudio.get("debe"):
            self._b_estudios(j, "", res)
            return
        e = ESTUDIOS[estudio["clave"]]
        if not self._pagar(j, e.precio, f"{e.emoji} Mensualidad de la carrera"):
            res.alerta = f"No alcanza: la mensualidad es de {D.dinero(e.precio)}."
            self._b_estudios(j, "", res)
            return
        j = self.db.jugador(j.id)
        extras = self._extras(j)
        extras["estudio"]["debe"] = False
        extras["estudio"]["pagado_hasta"] = self._hoy(j) + MES
        self._guardar_extras(j, extras)
        self._b_estudios(j, "", res, "✅ Mensualidad pagada: ¡a seguir estudiando!")

    def _tick_estudios(self, res) -> None:
        """La carrera se paga cada mes; si no alcanza, las clases se pausan hasta que paguen."""
        from .juego import Aviso

        for j in self.db.jugadores_en_sala():
            if j.estado != "activo":
                continue
            extras = self._extras(j)
            estudio = extras.get("estudio")
            if (not estudio or ESTUDIOS[estudio["clave"]].tipo != "carrera" or estudio.get("debe")
                    or self._hoy(j) < estudio["pagado_hasta"]):
                continue
            e = ESTUDIOS[estudio["clave"]]
            if self._pagar(j, e.precio, f"{e.emoji} Mensualidad de la carrera"):
                j = self.db.jugador(j.id)
                extras = self._extras(j)
                extras["estudio"]["pagado_hasta"] += MES
                self._guardar_extras(j, extras)
                res.avisos.append(Aviso(j.id, f"🎓 Se pagó la mensualidad de la carrera: {D.dinero(e.precio)}."))
            else:
                extras["estudio"]["debe"] = True
                self._guardar_extras(j, extras)
                res.avisos.append(Aviso(j.id, f"🎓 No alcanzó para la mensualidad de la carrera ({D.dinero(e.precio)}): "
                                              "las clases se pausan hasta que la paguen. No pierdes lo avanzado.",
                                        [[("📚 Estudios", "estudios")]]))
