"""Necesidades y acciones dentro del juego: pantallas, acciones en pareja y avisos (parte 4).

`VidaMixin` se mezcla con `Juego` y usa sus herramientas (db, reloj, _tocar, _firma…).
"""

from __future__ import annotations

import json

from . import cocina as C
from . import dinero as D
from . import objetos as O
from . import personaje as P
from . import vida as V
from .db import Hogar, Jugador, Propuesta

PROPUESTA_VENCE = 15 * 60
AVISAR_FIN_DESDE = 30 * 60  # se avisa al terminar acciones de al menos media hora
AVISO_NECESIDAD_CADA = 3600


def _dur(segundos: float) -> str:
    minutos = max(1, round(segundos / 60))
    if minutos < 60:
        return f"{minutos} min"
    h, m = divmod(minutos, 60)
    return f"{h} h" if not m else f"{h} h {m} min"


class VidaMixin:
    # ------------------------------------------------------------------
    # Estado del Sim
    # ------------------------------------------------------------------

    def _nec(self, j: Jugador) -> dict:
        return json.loads(j.necesidades) if j.necesidades else V.nuevas_necesidades()

    def _accion(self, j: Jugador) -> dict | None:
        return json.loads(j.accion) if j.accion else None

    def _fin_accion_real(self, j: Jugador) -> float:
        a = self._accion(j)
        return a["rfin"] if a else 0.0

    def _hogar(self, sala_id: int) -> Hogar:
        h = self.db.hogar(sala_id)
        if h is None:
            h = Hogar(sala_id, json.dumps({z: 0 for z in D.CASAS[D.CASA_INICIAL].zonas}))
            self.db.guardar_hogar(h)
        if not h.casa or "deposito" not in json.loads(h.extras or "{}"):
            self._preparar_casa(h)
        return h

    def _multiplicadores(self, j: Jugador) -> dict:
        if self._de_viaje(j):
            return {n.clave: 0.0 for n in V.NECESIDADES}  # de viaje, las necesidades no bajan
        h = self._hogar(j.sala_id)
        m = {}
        if h.ropa_sucia >= V.ROPA_LIMITE:
            m["higiene"] = 1.5
        if json.loads(h.zonas).get("salon", 0) >= V.SUCIO:
            m["diversion"] = 1.25
        decoracion = len(self._objetos(h) & set(O.DECORACION))  # plantas y cuadros: −10 % cada uno
        if decoracion:
            m["diversion"] = m.get("diversion", 1.0) * (1 - 0.1 * decoracion)
        return m

    def _vivir(self, j: Jugador, ahora: float) -> list[tuple[str, bool]]:
        """Lleva las necesidades y la acción del Sim hasta la hora de su reloj.

        Devuelve lo que pasó como (texto, avisar_aunque_no_esté_mirando).
        """
        if not j.activo or j.sala_id is None:
            return []
        s = self._segundos_juego(j, ahora)
        if not j.necesidades:
            j.necesidades = json.dumps(V.nuevas_necesidades())
            j.nec_seg = s
            self.db.guardar_jugador(j)
            return []
        nec, accion, eventos = self._nec(j), self._accion(j), []
        terminada = V.avanzar(nec, j.nec_seg, s, accion, j.energia_max, self._multiplicadores(j))
        j.nec_seg = max(j.nec_seg, s)
        if terminada:
            j.accion = None
            if j.lugar.startswith(V.FUERA):
                j.lugar = V.HABITACION_INICIAL  # vuelve a casa
            # El final de la acción cuenta como actividad: el Sim se congela 5 min después, no antes.
            j.ultima_jugada = max(j.ultima_jugada, accion["rfin"])
            eventos.append((self._al_terminar(j, accion, nec), accion["fin"] - accion["ini"] >= AVISAR_FIN_DESDE))
        sin_energia = nec["energia"] < 1 and not (accion and accion.get("duerme") and not terminada)
        j.necesidades = json.dumps({k: round(v, 3) for k, v in nec.items()})
        if sin_energia and not self._congelado(j, ahora):
            if j.accion:
                interrumpida = self._accion(j)
                j.accion = None
                if interrumpida.get("k") == "trabajar":
                    eventos.append((f"💼 Dejó de trabajar a mitad del turno.{self._cobrar_turno(j, interrumpida, s, False)}", True))
            datos = V.preparar(V.ACCIONES["dormir"], s, nec, j.energia_max, str(V.HORAS_DESMAYO))
            datos.update(rini=ahora, rfin=ahora + (datos["fin"] - datos["ini"]), con=None)
            j.accion = json.dumps(datos)
            eventos.append((f"😵 {self._firma(j)} se quedó sin energía y se durmió donde estaba.", True))
        self.db.guardar_jugador(j)
        return eventos

    def _al_terminar(self, j: Jugador, accion: dict, nec: dict) -> str:
        a = V.ACCIONES.get(accion["k"])
        if a is None:
            return ""
        texto = f"✅ {self._firma(j)} terminó: {a.emoji} {a.titulo(bool(accion.get('con')))}."
        texto += self._efecto_mascota(j, accion) + self._paso_influencer(j, accion)
        self._recordar_cita(j, accion)
        self._reto_accion(j, accion)
        h = self._hogar(j.sala_id)
        if a.clave == "limpiar" and accion.get("x") in V.ZONAS:
            zonas = json.loads(h.zonas)
            zonas[accion["x"]] = 0
            h.zonas = json.dumps(zonas)
            self.db.guardar_hogar(h)
            self._evento_limpio(h, accion["x"])
            texto += f" {V.ZONAS[accion['x']][1]} quedó reluciente ✨"
        elif a.clave == "lavar":
            h.ropa_sucia = 0
            self.db.guardar_hogar(h)
            texto += " Toda la ropa está limpia 👕"
        elif a.clave == "trabajar":
            texto += self._cobrar_turno(j, accion, accion["fin"], completo=True)
        elif a.clave == "cocinar" and h.cocina:
            # Se acabó el tiempo máximo sin terminar la receta: se quemó.
            receta = C.RECETAS.get(accion.get("x", ""))
            h.cocina = ""
            self.db.guardar_hogar(h)
            texto = f"🔥 ¡Se quemó {receta.nombre.lower() if receta else 'la comida'}!"
        if a.ejercicio:
            racha, j.energia_max, subio = V.registrar_ejercicio(
                json.loads(j.racha or "{}"), self._hoy(j, accion["rfin"]), j.energia_max
            )
            j.racha = json.dumps(racha)
            if subio:
                texto += f"\n💪 ¡Constancia! {racha['dias']} días seguidos: la energía máxima sube a {j.energia_max}."
        return texto

    def _descongelar(self, j: Jugador, ahora: float) -> None:
        if j.estado == "activo" and self._congelado(j, ahora):
            self._congelar(j, ahora)
            j.reloj_desde = ahora
            j.ultima_jugada = ahora
            self.db.guardar_jugador(j)

    def _empezar(self, j: Jugador, a: V.Accion, extra: str, con: int | None, ahora: float,
                 minutos: int | None = None) -> dict:
        s = self._segundos_juego(j, ahora)
        datos = V.preparar(a, s, self._nec(j), j.energia_max, extra, juntos=con is not None,
                           hora=self._hora_local(j, ahora))
        datos["ef"] = self._con_objetos(j, a.clave, datos["ef"])
        if minutos is not None:
            datos["fin"] = datos["ini"] + minutos * 60
        datos.update(rini=ahora, rfin=ahora + (datos["fin"] - datos["ini"]), con=con)
        j.accion = json.dumps(datos)
        j.ultima_jugada = ahora
        if a.habitacion == V.FUERA:
            j.lugar = f"{V.FUERA}:{a.clave}"
        elif a.clave == "limpiar" and extra in V.ZONAS:
            j.lugar = extra
        elif a.habitacion:
            j.lugar = a.habitacion
        self.db.guardar_jugador(j)
        h = self._hogar(j.sala_id)
        if a.zona and a.ensucia:
            zonas = json.loads(h.zonas)
            ensucia = a.ensucia / 2 if "pintar" in self._objetos(h) else a.ensucia  # casa pintada y decorada
            zonas[a.zona] = min(100, zonas.get(a.zona, 0) + ensucia)
            h.zonas = json.dumps(zonas)
        h.ropa_sucia += a.ropa
        self.db.guardar_hogar(h)
        return datos

    def _texto_accion(self, j: Jugador, ahora: float) -> str | None:
        """'😴 durmiendo hasta las 06:00' si está haciendo algo."""
        accion = self._accion(j)
        if not accion or accion["rfin"] <= ahora:
            return None
        a = V.ACCIONES.get(accion["k"])
        if a is None:
            return None
        verbo = a.verbo
        if a.clave == "cocinar" and accion.get("x") in C.RECETAS:
            verbo += f" {C.RECETAS[accion['x']].nombre.lower()}"
        con = ""
        if accion.get("con"):
            otro = self.db.jugador(accion["con"])
            con = f" con {otro.personaje}" if otro else ""
        if a.clave == "cocinar":
            return f"{a.emoji} {verbo}{con}"
        return f"{a.emoji} {verbo}{con} hasta las {self._hora(j, accion['rfin'])}"

    def _pareja_en_sala(self, j: Jugador) -> Jugador | None:
        return next((m for m in self._companeros(j) if m.estado == "activo"), None)

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _pantalla_sim(self, j: Jugador, aviso: str | None = None):
        """👤 Estado → Mis necesidades."""
        from .juego import Pantalla

        ahora = self.reloj()
        s = self._segundos_juego(j, ahora)
        nec, accion = self._nec(j), self._accion(j)
        animo = P.animo(j.ap)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"🧍 {self._firma(j)}{' · ' + animo if animo else ''}",
            f"🕒 {self._reloj(j)}{' · 🎉 fin de semana' if self._finde(j) else ''}",
            f"📍 {V.nombre_habitacion(j.lugar)}",
        ]
        haciendo = self._texto_accion(j, ahora)
        if haciendo:
            lineas.append(f"▶️ Está {haciendo} (faltan {_dur(accion['fin'] - s)})")
        elif self._congelado(j, ahora):
            lineas.append("❄️ En pausa")
        else:
            lineas.append("🧍 Sin hacer nada")
        if V.de_mal_humor(nec):
            lineas.append("😡 <b>De mal humor</b>: tiene alguna necesidad en 0.")
        lineas.append("")
        for n in V.NECESIDADES:
            tope = V.maximo(n.clave, j.energia_max)
            valor = nec.get(n.clave, 0)
            cifra = f"{round(valor)}/{tope}" if n.clave == "energia" and tope != 100 else f"{round(valor)}"
            lineas.append(f"{n.emoji} {V.barra(valor, tope)} {cifra} {n.nombre}")
        h = self._hogar(j.sala_id)
        lineas += ["", f"🏦 Compartida {D.dinero(h.cuenta)} · 👛 Tu cartera {D.dinero(j.cartera)}"]
        lineas.append(f"💼 {self._texto_puesto(j) or 'Sin trabajo todavía'}")
        if j.taper in C.RECETAS:
            lineas.append(f"🥡 Táper para el trabajo: {C.RECETAS[j.taper].nombre.lower()}")
        cortados = D.servicios_cortados(json.loads(h.pendientes))
        if cortados:
            lineas.append("❌ Servicio cortado: " + ", ".join(D.POR_CLAVE_FACTURA[c].nombre.lower() for c in cortados))
        avisos_casa = []
        if h.ropa_sucia >= V.ROPA_LIMITE:
            avisos_casa.append("🧺 No queda ropa limpia: la higiene baja más rápido.")
        if json.loads(h.zonas).get("salon", 0) >= V.SUCIO:
            avisos_casa.append("🪳 La sala está sucia: se divierte menos.")
        if avisos_casa:
            lineas += [""] + avisos_casa
        botones = []
        if haciendo:
            botones.append([("⏹️ Parar lo que está haciendo", "parar")])
        if self._trabajando(j):
            botones.append([("📱 Descanso: ver redes", "rapida:redes"), ("🤗 Mandar un abrazo", "rapida:abrazo")])
        botones.append([("⚡ Acciones", "macc"), ("🔄 Actualizar", "sim")])
        botones.append([("⬅️ Atrás", "mest"), ("🎮 Menú", "menu")])
        return Pantalla("\n".join(lineas), botones, clave="sim")

    def _b_sim(self, j: Jugador, arg: str, res) -> None:
        res.pantalla = self._pantalla_sim(j)

    def _b_categoria(self, j: Jugador, categoria: str, res, aviso: str | None = None) -> None:
        """⚡ Acciones → una categoría (o 📍 Lugares → un lugar): la lista de acciones."""
        from .juego import Pantalla

        info = next((c for c in V.CATEGORIAS if c[0] == categoria), None)
        if info is None:
            self._b_menu_acciones(j, "", res)
            return
        pareja = self._pareja_en_sala(j)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            f"{info[1]} <b>{info[2]}</b> · 🕒 {self._reloj(j)}",
            f"📍 Estás en: {V.nombre_habitacion(j.lugar)}",
        ]
        if categoria == "limpieza":
            h = self._hogar(j.sala_id)
            zonas = json.loads(h.zonas)
            lineas.append("")
            for z, (e, nombre) in self._zonas(j.sala_id).items():
                lineas.append(f"{e} {nombre}: {V.estado_zona(zonas.get(z, 0))}")
            lineas.append(f"🧺 Ropa sucia: {h.ropa_sucia} prendas" + (" (¡no queda limpia!)" if h.ropa_sucia >= V.ROPA_LIMITE else ""))
        botones = []
        faltan_pareja = []
        for a in V.ACCIONES.values():
            if a.categoria != categoria:
                continue
            if a.juntos == V.OBLIGATORIO and pareja is None:
                faltan_pareja.append(a.nombre.lower())
                continue
            titulo = a.titulo(a.juntos == V.OBLIGATORIO)
            if a.clave == "comer":
                _, comida, valor = V.comida_del_momento(self._hora_local(j))
                titulo = f"Comer lo que hay ({comida.lower()}, +{valor})"
            donde = ""
            if a.habitacion and a.habitacion != V.FUERA and a.habitacion != j.lugar:
                donde = f" · {V.ZONAS[a.habitacion][0]}"
            botones.append([(f"{a.emoji} {titulo}{donde}", f"a:{a.clave}")])
        if faltan_pareja:
            lineas += ["", f"💞 Con tu pareja en la sala también podrán: {', '.join(faltan_pareja)}."]
        lineas += ["", "💡 Juntos terminan más rápido."] if pareja else []
        if categoria == "comer":
            botones.append([("🧊 Nevera y despensa", "nevera")])
        botones.append([("⬅️ Atrás", "macc"), ("🎮 Menú", "menu")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave=f"acc:{categoria}")

    def _volver_a(self, a: V.Accion) -> str:
        """A qué menú vuelve el botón Atrás desde la ficha de una acción."""
        if a.categoria in dict((c[0], c) for c in V.CATEGORIAS):
            return f"acc:{a.categoria}"
        if a.categoria == "influencer":
            return "influ"
        return "mlug"

    # ------------------------------------------------------------------
    # Hacer acciones: ficha con efecto y tiempo, y confirmar
    # ------------------------------------------------------------------

    def _b_accion(self, j: Jugador, arg: str, res) -> None:
        """a:<acción>[:<extra>]: pide lo que falte (zona, horas…) y muestra la ficha para confirmar."""
        from .juego import Pantalla

        clave, _, extra = arg.partition(":")
        a = V.ACCIONES.get(clave)
        if a is None:
            self._b_menu_acciones(j, "", res)
            return
        # Acciones con su propio menú: el súper, las recetas, el táper y qué comer.
        if clave == "super" and extra != "ir":
            self._b_super(j, "", res)
            return
        if clave == "cocinar":
            self._b_recetas(j, "", res)
            return
        if clave == "taper":
            self._b_elegir_taper(j, res)
            return
        if clave == "comer" and not extra:
            self._b_elegir_comida(j, res)
            return
        if self._ocupado(j, res):
            return
        nec = self._nec(j)
        volver = self._volver_a(a)
        if clave == "dormir" and not extra:
            horas = V.horas_para_descansar(nec["energia"], j.energia_max)
            opciones = [(f"⚡ Hasta recuperarse ({horas} h)", "a:dormir:max")] + [
                (f"🕗 {h} horas", f"a:dormir:{h}") for h in (8, 6, 4) if h != horas
            ]
            res.pantalla = Pantalla(
                "😴 <b>¿Cuánto quieres dormir?</b>\nDormir recupera unos 12 de energía por hora.",
                [[o] for o in opciones] + [[("⬅️ Atrás", volver)]],
                clave=volver,
            )
            return
        if clave == "limpiar" and extra not in self._zonas(j.sala_id):
            zonas = json.loads(self._hogar(j.sala_id).zonas)
            res.pantalla = Pantalla(
                "🧹 <b>¿Qué zona quieres limpiar?</b>",
                [[(f"{e} {n} · {V.estado_zona(zonas.get(z, 0))}", f"a:limpiar:{z}")]
                 for z, (e, n) in self._zonas(j.sala_id).items()]
                + [[("⬅️ Atrás", volver)]],
                clave=volver,
            )
            return
        motivo = V.no_hace_falta(a, nec, j.energia_max) or self._bloqueo_accion(j, a)
        if motivo:
            res.alerta = motivo
            if volver.startswith("acc:"):
                self._b_categoria(j, a.categoria, res)
            else:
                self._b_menu_lugares(j, "", res)
            return
        pareja = self._pareja_en_sala(j)
        if a.juntos == V.OBLIGATORIO and pareja is None:
            res.alerta = "Para esto necesitas a tu pareja en la sala."
            self._b_categoria(j, a.categoria, res)
            return
        res.pantalla = self._ficha(j, a, extra, pareja)

    def _titulo_accion(self, a: V.Accion, extra: str, juntos: bool) -> str:
        titulo = a.titulo(juntos)
        if a.clave == "limpiar" and extra in V.ZONAS:
            titulo = f"{'Limpiar juntos' if juntos else 'Limpiar'}: {V.ZONAS[extra][1].lower()}"
        elif a.clave == "comer" and extra in C.RECETAS:
            titulo = f"{titulo}: {C.RECETAS[extra].nombre.lower()}"
        elif a.clave == "comer" and extra == "taper":
            titulo = "Comer tu táper"
        return titulo

    def _ficha(self, j: Jugador, a: V.Accion, extra: str, pareja: Jugador | None):
        """Ficha de la acción: efecto, tiempo, costo y dónde. ¿Confirmar? Sí / No."""
        from .juego import Pantalla

        s = self._segundos_juego(j, self.reloj())
        nec = self._nec(j)
        sufijo = f":{extra}" if extra else ""
        volver = self._volver_a(a)
        lineas = []
        botones = []
        opciones = []
        if a.juntos != V.OBLIGATORIO:
            opciones.append(False)
        if a.juntos != V.SOLO and pareja is not None:
            opciones.append(True)
        for juntos in opciones:
            datos = V.preparar(a, s, nec, j.energia_max, extra, juntos=juntos, hora=self._hora_local(j))
            datos["ef"] = self._con_objetos(j, a.clave, datos["ef"])
            costo, _ = self._costo_accion(j, a, extra, juntos, pareja if juntos else None)
            quien = f"💞 Con {self._firma(pareja)}" if juntos else "👤 Solo"
            detalle = f"{V.texto_efectos(datos['ef'])} · ⏱️ {_dur(datos['fin'] - datos['ini'])}"
            if costo:
                detalle += f" · 💵 {D.dinero(costo)}"
            if len(opciones) > 1:
                lineas.append(f"{quien}: {detalle}")
            else:
                lineas.append(detalle)
            etiqueta = "✅ Sí" if not juntos else f"💞 Sí, con {pareja.personaje}"
            if len(opciones) > 1 and not juntos:
                etiqueta = "✅ Sí, solo"
            botones.append([(etiqueta, f"{'aj' if juntos else 'as'}:{a.clave}{sufijo}")])
        titulo = self._titulo_accion(a, extra, len(opciones) == 1 and opciones[0])
        cabecera = [f"{a.emoji} <b>{titulo}</b>"]
        if a.habitacion == V.FUERA:
            cabecera.append("📍 Fuera de casa")
        elif a.habitacion and a.habitacion != j.lugar:
            cabecera.append(f"🚶 Irá a {V.nombre_habitacion(a.habitacion)}")
        elif a.clave == "limpiar" and extra in V.ZONAS and extra != j.lugar:
            cabecera.append(f"🚶 Irá a {V.nombre_habitacion(extra)}")
        if True in opciones and False in opciones:
            cabecera.append("💡 Juntos terminan más rápido.")
        botones.append([("❌ No, atrás", volver)])
        return Pantalla("\n".join(cabecera + [""] + lineas + ["", "¿Confirmar?"]), botones, clave=volver)

    def _ocupado(self, j: Jugador, res) -> bool:
        haciendo = self._texto_accion(j, self.reloj())
        if haciendo:
            res.alerta = f"Tu Sim está {haciendo.split(' ', 1)[1]}. Para esa acción primero."
            res.pantalla = self._pantalla_sim(j)
            return True
        return False

    def _b_solo(self, j: Jugador, arg: str, res) -> None:
        clave, _, extra = arg.partition(":")
        if clave == "cocinar":
            self._b_cocinar_solo(j, extra, res)
            return
        a = V.ACCIONES.get(clave)
        if a is None or a.juntos == V.OBLIGATORIO or self._ocupado(j, res):
            if a is None or a.juntos == V.OBLIGATORIO:
                res.pantalla = self._pantalla_sim(j)
            return
        self._hacer(j, a, extra, res)

    def _b_juntos(self, j: Jugador, arg: str, res) -> None:
        clave, _, extra = arg.partition(":")
        a = V.ACCIONES.get(clave)
        pareja = self._pareja_en_sala(j)
        if a is None or a.juntos == V.SOLO or pareja is None:
            res.alerta = "Ahora no se puede hacer juntos."
            res.pantalla = self._pantalla_sim(j)
            return
        if not self._ocupado(j, res):
            self._proponer(j, a, extra, pareja, res)

    def _hacer(self, j: Jugador, a: V.Accion, extra: str, res) -> None:
        error = self._cobrar_accion(j, a, extra=extra)
        if error:
            res.alerta = error
            res.pantalla = self._ficha(j, a, extra, self._pareja_en_sala(j))
            return
        datos = self._empezar(j, a, extra, None, self.reloj())
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        res.pantalla = self._pantalla_sim(
            j, f"▶️ Empezó: {a.emoji} {self._titulo_accion(a, extra, False)} · termina a las {self._hora(j, datos['rfin'])}."
        )

    def _proponer(self, j: Jugador, a: V.Accion, extra: str, pareja: Jugador, res) -> None:
        from .juego import Aviso, Pantalla

        ahora = self.reloj()
        if self._estado_presencia(pareja, ahora) == "fuera":
            res.alerta = f"{pareja.personaje} no está en línea ahora."
            self._b_categoria(j, a.categoria, res)
            return
        pid = self.db.guardar_propuesta(Propuesta(None, j.id, pareja.id, a.clave, extra, ahora))
        duracion = _dur(round(a.minutos * V.FACTOR_JUNTOS) * 60) if a.clave != "dormir" else "a dormir"
        receta = C.RECETAS.get(extra.partition(":")[0]) if a.clave in ("cocinar", "comer") else None
        if receta and a.clave == "cocinar":
            duracion = f"{receta.nombre.lower()}, unos {round(receta.minutos * V.FACTOR_JUNTOS)} min"
        elif receta:
            duracion += f", {receta.nombre.lower()} de la nevera"
        res.avisos.append(Aviso(
            pareja.id,
            f"💞 {self._firma(j)} te propone: <b>{a.emoji} {a.titulo(True)}</b> ({duracion}). ¿Vamos?",
            [[("✅ ¡Vamos!", f"pj:{pid}:1"), ("❌ Ahora no", f"pj:{pid}:0")]],
        ))
        res.pantalla = Pantalla(
            f"⏳ Le propusiste a {self._firma(pareja)}: {a.emoji} <b>{a.titulo(True)}</b>.\n"
            "En cuanto acepte, empiezan juntos.",
            [[("❌ Cancelar la propuesta", f"pjx:{pid}")], [("🧍 Mi Sim", "sim")]],
        )

    def _b_respuesta(self, j: Jugador, arg: str, res) -> None:
        """pj:<id>:<1|0>: la pareja acepta o rechaza hacer algo juntos."""
        from .juego import Aviso

        ahora = self.reloj()
        pid, _, si = arg.partition(":")
        p = self.db.propuesta(int(pid)) if pid.isdigit() else None
        de = self.db.jugador(p.de) if p else None
        a = V.ACCIONES.get(p.accion) if p else None
        if (
            p is None or a is None or de is None or p.para != j.id or p.estado != "pendiente"
            or ahora - p.creada > PROPUESTA_VENCE or de.sala_id != j.sala_id
        ):
            res.alerta = "Esa propuesta ya no está disponible."
            res.pantalla = self._pantalla_sim(j)
            return
        if si != "1":
            p.estado = "rechazada"
            self.db.guardar_propuesta(p)
            res.avisos.append(Aviso(de.id, f"🙈 {self._firma(j)} dijo que ahora no: {a.emoji} {a.titulo(True)}."))
            res.pantalla = self._pantalla_sim(j)
            return
        if self._trabajando(j):
            res.alerta = "Estás trabajando: en el descanso puedes mandarle un abrazo rápido 🤗"
            self._b_trabajo(j, "", res)
            return
        self._vivir(de, ahora)
        if self._texto_accion(de, ahora):
            p.estado = "caducada"
            self.db.guardar_propuesta(p)
            res.alerta = f"{de.personaje} ya está haciendo otra cosa."
            res.pantalla = self._pantalla_sim(j)
            return
        error = self._cobrar_accion(de, a, juntos=True, extra=p.extra, pareja=j)
        if error:
            p.estado = "caducada"
            self.db.guardar_propuesta(p)
            res.alerta = error
            res.avisos.append(Aviso(de.id, f"No pudieron empezar {a.titulo(True).lower()}: {error}"))
            res.pantalla = self._pantalla_sim(j)
            return
        self._descongelar(j, ahora)
        self._descongelar(de, ahora)
        if j.accion:  # quien acepta deja lo que estaba haciendo
            self._vivir(j, ahora)
            j.accion = None
            self.db.guardar_jugador(j)
        if a.clave == "cocinar":
            error = self._iniciar_coccion([de, j], p.extra, juntos=True)
            if error:
                p.estado = "caducada"
                self.db.guardar_propuesta(p)
                res.alerta = error
                res.pantalla = self._pantalla_sim(j)
                return
            datos = self._accion(self.db.jugador(j.id))
        else:
            datos = self._empezar(j, a, p.extra, de.id, ahora)
            self._empezar(de, a, p.extra, j.id, ahora)
        p.estado = "aceptada"
        self.db.guardar_propuesta(p)
        hasta = self._hora(j, datos["rfin"])
        res.avisos.append(Aviso(
            de.id,
            f"💞 {self._firma(j)} aceptó. ¡Empiezan juntos: {a.emoji} {a.titulo(True)}!",
            [[("🧍 Mi Sim", "sim")]],
        ))
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        if a.clave == "cocinar":
            self._b_coccion(self.db.jugador(j.id), "", res, "💞 ¡A cocinar juntos!")
            return
        res.pantalla = self._pantalla_sim(j, f"💞 ¡Empiezan juntos: {a.emoji} {a.titulo(True)}! (hasta las {hasta})")

    def _b_cancelar_propuesta(self, j: Jugador, pid: str, res) -> None:
        p = self.db.propuesta(int(pid)) if pid.isdigit() else None
        if p is not None and p.de == j.id and p.estado == "pendiente":
            p.estado = "cancelada"
            self.db.guardar_propuesta(p)
            res.alerta = "Propuesta cancelada"
        res.pantalla = self._pantalla_sim(j)

    def _b_parar(self, j: Jugador, arg: str, res) -> None:
        accion = self._accion(j)
        if accion and accion.get("k") == "cocinar":
            h = self._hogar(j.sala_id)
            coccion = self._coccion(h)
            if coccion:
                self._terminar_coccion(h, coccion, quien=j)
                res.pantalla = self._pantalla_sim(j, "🗑️ Dejaste de cocinar. Los ingredientes usados se perdieron.")
                return
        if accion:
            ahora = self.reloj()
            self._vivir(j, ahora)
            j.accion = None
            self.db.guardar_jugador(j)
            res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
            a = V.ACCIONES.get(accion["k"])
            texto = f"⏹️ Paró: {a.emoji} {a.titulo(bool(accion.get('con')))}." if a else None
            if accion["k"] == "trabajar":
                texto += self._cobrar_turno(j, accion, self._segundos_juego(j, ahora), completo=False)
            if j.lugar.startswith(V.FUERA):
                j.lugar = V.HABITACION_INICIAL
                self.db.guardar_jugador(j)
            res.pantalla = self._pantalla_sim(j, texto)
            return
        res.pantalla = self._pantalla_sim(j)

    # ------------------------------------------------------------------
    # Cada minuto
    # ------------------------------------------------------------------

    def _tick_vida(self, ahora: float, res) -> None:
        from .juego import Aviso

        for j in self.db.jugadores_en_sala():
            j = self.db.jugador(j.id) or j  # al día: otro Sim pudo cambiarlo en este mismo minuto
            if j.estado != "activo":
                continue
            eventos = self._vivir(j, ahora)
            for texto, avisar in eventos:
                if avisar:
                    res.avisos.append(Aviso(j.id, texto, [[("🧍 Mi Sim", "sim")]]))
            if eventos:
                res.ediciones += self._refrescar_sala(j.sala_id)
            nec = self._nec(j)
            bajas = [n for n in V.NECESIDADES if nec.get(n.clave, 100) < V.ALERTA]
            if bajas and not self._congelado(j, ahora) and ahora - j.aviso_necesidad_ts > AVISO_NECESIDAD_CADA:
                j.aviso_necesidad_ts = ahora
                self.db.guardar_jugador(j)
                detalle = ", ".join(f"{n.emoji} {n.nombre} {round(nec[n.clave])}" for n in bajas)
                res.avisos.append(Aviso(
                    j.id, f"⚠️ {self._firma(j)} necesita atención: {detalle}.", [[("🧍 Mi Sim", "sim")]]
                ))
