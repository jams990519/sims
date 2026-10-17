"""Súper y minijuego de cocina dentro del juego (parte 7).

`CocinaMixin` se mezcla con `Juego`. Hay una sola cocina por casa: mientras alguien cocina,
el estado de la receta vive en `hogar.cocina` y cualquiera de los cocineros puede tocar
"listo" para pasar al siguiente paso. Si nadie lo toca a tiempo, la comida se quema.
"""

from __future__ import annotations

import json
import math

from . import cocina as C
from . import dinero as D
from . import vida as V
from .db import Hogar, Jugador


class CocinaMixin:
    # ------------------------------------------------------------------
    # Nevera y despensa
    # ------------------------------------------------------------------

    def _despensa(self, h: Hogar) -> dict:
        return json.loads(h.despensa or "{}")

    def _nevera(self, h: Hogar) -> dict:
        return json.loads(h.nevera or "{}")

    def _coccion(self, h: Hogar) -> dict | None:
        return json.loads(h.cocina) if h.cocina else None

    def _b_nevera(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        despensa, nevera = self._despensa(h), self._nevera(h)
        lineas = ["🧊 <b>Nevera y despensa</b> (compartidas)", ""]
        if nevera:
            lineas.append("<b>Comida hecha</b>")
            lineas += [f"{C.RECETAS[r].emoji} {C.RECETAS[r].nombre}: {n} porción(es)" for r, n in nevera.items() if r in C.RECETAS]
            lineas.append("")
        for lugar, titulo in (("nevera", "🧊 <b>Nevera</b>"), ("despensa", "🥫 <b>Despensa</b>")):
            cosas = [
                f"{i.emoji} {i.nombre}: {despensa[c]}" for c, i in C.INGREDIENTES.items()
                if i.lugar == lugar and despensa.get(c)
            ]
            lineas.append(titulo)
            lineas += cosas or ["(vacía)"]
            lineas.append("")
        if j.taper and j.taper in C.RECETAS:
            lineas.append(f"🥡 Tu táper: {C.RECETAS[j.taper].nombre}")
        res.pantalla = Pantalla(
            "\n".join(lineas).rstrip(),
            [[("🛒 Ir al súper", "a:super"), ("🍳 Preparar comida", "a:cocinar")], [("⬅️ Atrás", "mcasa")]],
            clave="nevera",
        )

    # ------------------------------------------------------------------
    # Súper
    # ------------------------------------------------------------------

    def _carrito(self, j: Jugador) -> dict:
        return json.loads(j.carrito or "{}")

    def _cocinadas(self, h: Hogar) -> int:
        return self._extras_hogar(h).get("cocinadas", 0)

    def _nivel_super(self, h: Hogar) -> int:
        """El súper crece: con más recetas cocinadas trae productos y recetas nuevas."""
        return C.nivel_super(self._cocinadas(h))

    def _texto_crece(self, h: Hogar, que: str) -> list[str]:
        meta = C.siguiente_nivel(self._cocinadas(h))
        return [f"🔓 <i>Cocinen más y el súper traerá {que} ({self._cocinadas(h)}/{meta} recetas).</i>"] if meta else []

    def _contar_receta(self, h: Hogar, res) -> None:
        """Una receta más cocinada; si el súper sube de nivel, se avisa a los dos."""
        from .juego import Aviso

        antes = self._nivel_super(h)
        ex = self._extras_hogar(h)
        ex["cocinadas"] = ex.get("cocinadas", 0) + 1
        self._guardar_extras_hogar(h, ex)
        nivel = self._nivel_super(h)
        if nivel == antes:
            return
        productos = ", ".join(f"{i.emoji} {i.nombre.lower()}" for i in C.INGREDIENTES.values() if i.nivel == nivel)
        recetas = ", ".join(f"{r.emoji} {r.nombre.lower()}" for r in C.RECETAS.values() if r.nivel == nivel)
        texto = f"🛒🔓 <b>¡El súper creció!</b> Productos nuevos: {productos}.\n📖 Recetas nuevas: {recetas}."
        for m in self.db.miembros_sala(h.sala_id):
            if m.estado == "activo":
                res.avisos.append(Aviso(m.id, texto, [[("🛒 Súper", "a:super"), ("🍳 Recetas", "a:cocinar")]]))

    def _b_super(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        dia = self._finde(j)
        oferta = self._oferta_super(j)
        carrito = self._carrito(j)
        h = self._hogar(j.sala_id)
        nivel = self._nivel_super(h)
        lineas = [aviso, ""] if aviso else []
        lineas.append("🛒 <b>Súper</b>")
        if oferta:
            lineas.append("🎉 ¡Oferta sorpresa: hoy toda la compra a mitad de precio!")
        elif dia:
            lineas.append(f"🎉 ¡Ofertas de fin de semana: todo un {round(C.OFERTA_FIN_DE_SEMANA * 100)} % más barato!")
        else:
            lineas.append("💡 Los sábados y domingos hay ofertas.")
        lineas.append("")
        if carrito:
            lineas.append("🧺 <b>Tu carrito</b>")
            lineas += [
                f"{C.INGREDIENTES[i].emoji} {C.INGREDIENTES[i].nombre} ({C.INGREDIENTES[i].paquete}) ×{n}"
                for i, n in carrito.items() if i in C.INGREDIENTES
            ]
            lineas.append(f"<b>Total: ${C.total_carrito(carrito, dia, oferta):.2f}</b>")
        else:
            lineas.append("🧺 Toca un producto para añadirlo al carrito.")
        lineas.append(f"🏦 Compartida {D.dinero(h.cuenta)} · 👛 Tu cartera {D.dinero(j.cartera)}")
        productos = [
            (f"{i.emoji} {i.nombre} ${C.precio(c, dia, oferta):.2f}", f"sup:+:{c}") for c, i in C.INGREDIENTES.items()
            if i.nivel <= nivel
        ]
        lineas += self._texto_crece(h, "productos nuevos")
        botones = [productos[k:k + 2] for k in range(0, len(productos), 2)]
        if carrito:
            botones.append([(f"✅ Pagar ${C.total_carrito(carrito, dia, oferta):.2f}", "sup:pagar"), ("🗑️ Vaciar", "sup:vaciar")])
        botones.append([("🧊 Nevera", "nevera"), ("⬅️ Atrás", "mlug")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="super")

    def _b_super_accion(self, j: Jugador, arg: str, res) -> None:
        accion, _, ingrediente = arg.partition(":")
        carrito = self._carrito(j)
        nivel = self._nivel_super(self._hogar(j.sala_id))
        if accion == "+" and ingrediente in C.INGREDIENTES and C.INGREDIENTES[ingrediente].nivel <= nivel:
            carrito[ingrediente] = carrito.get(ingrediente, 0) + 1
            res.alerta = f"🧺 +1 {C.INGREDIENTES[ingrediente].nombre.lower()}"
        elif accion == "vaciar":
            carrito = {}
        elif accion == "pagar" and carrito:
            self._pagar_super(j, carrito, res)
            return
        j.carrito = json.dumps(carrito)
        self.db.guardar_jugador(j)
        self._b_super(j, "", res)

    def _pagar_super(self, j: Jugador, carrito: dict, res) -> None:
        if self._ocupado(j, res):
            return
        total = math.ceil(C.total_carrito(carrito, self._finde(j), self._oferta_super(j)))
        if not self._pagar(j, total, "🛒 Compra en el súper"):
            res.alerta = f"💸 No alcanza: la compra cuesta {D.dinero(total)}."
            self._b_super(j, "", res)
            return
        h = self._hogar(j.sala_id)
        h.despensa = json.dumps(C.guardar_compra(self._despensa(h), carrito))
        self.db.guardar_hogar(h)
        j.carrito = "{}"
        self.db.guardar_jugador(j)
        res.alerta = f"✅ Compra pagada: {D.dinero(total)}. Ya está en la nevera y la despensa."
        # Ir y volver del súper lleva su tiempo (solo o en pareja).
        self._b_accion(j, "super:ir", res)

    # ------------------------------------------------------------------
    # Cocinar
    # ------------------------------------------------------------------

    def _b_recetas(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        coccion = self._coccion(h)
        if coccion:
            self._b_coccion(j, "", res)
            return
        despensa = self._despensa(h)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            "🍳 <b>Cocinar</b>",
            "Las recetas se hacen paso a paso y en tiempo real: cuando un paso está listo te aviso, y si te "
            "pasas de tiempo, ¡se quema! 🔥 (✅ tienes los ingredientes · ❌ falta algo)",
        ]
        botones = []
        nivel = self._nivel_super(h)
        for comida, titulo in C.COMIDAS:
            lineas += ["", f"<b>{titulo}</b>"]
            for r in C.RECETAS.values():
                if r.comida != comida or r.nivel > nivel:
                    continue
                marca = "❌" if C.faltan(despensa, r, 1) else "✅"
                lineas.append(f"{marca} {r.emoji} {r.nombre} · {r.minutos} min")
                botones.append([(f"{marca} {r.emoji} {r.nombre}", f"rec:{r.clave}")])
        lineas += [""] + self._texto_crece(h, "recetas nuevas") if C.siguiente_nivel(self._cocinadas(h)) else []
        botones.append([("🛒 Súper", "a:super"), ("🧊 Nevera", "nevera")])
        botones.append([("⬅️ Atrás", "acc:comer")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="cocina")

    def _b_receta(self, j: Jugador, clave: str, res) -> None:
        from .juego import Pantalla

        r = C.RECETAS.get(clave)
        if r is None:
            self._b_recetas(j, "", res)
            return
        despensa = self._despensa(self._hogar(j.sala_id))
        lineas = [
            f"{r.emoji} <b>{r.nombre}</b> · {r.minutos} min",
            f"Por porción: {C.texto_ingredientes(r.ingredientes)}",
            "",
            "<b>Pasos</b>",
        ] + [f"{i}. {texto} · {m} min" for i, (texto, m) in enumerate(r.pasos, 1)]
        botones = []
        for porciones in (1, 2):
            falta = C.faltan(despensa, r, porciones)
            if not falta:
                botones.append([(f"👤 Cocinar {porciones} porción{'es' if porciones > 1 else ''}", f"coc:{clave}:{porciones}")])
        if self._pareja_en_sala(j) and not C.faltan(despensa, r, 2):
            botones.append([("💞 Cocinar juntos (2 porciones, más rápido)", f"aj:cocinar:{clave}:2")])
        falta = C.faltan(despensa, r, 1)
        if falta:
            lineas += ["", f"❌ Falta: {C.texto_ingredientes(falta)}"]
            botones.append([("🛒 Ir al súper", "a:super")])
        botones.append([("⬅️ Atrás", "a:cocinar")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="cocina")

    def _b_cocinar_solo(self, j: Jugador, arg: str, res) -> None:
        """coc:<receta>:<porciones> · coc:sig (siguiente paso) · coc:x (abandonar)."""
        if arg == "sig":
            self._siguiente_paso(j, res)
            return
        if arg == "x":
            h = self._hogar(j.sala_id)
            coccion = self._coccion(h)
            if coccion and j.id in coccion["cocineros"]:
                self._terminar_coccion(h, coccion, quien=j)
                res.pantalla = self._pantalla_sim(j, "🗑️ Dejaste de cocinar. Los ingredientes usados se perdieron.")
            else:
                self._b_recetas(j, "", res)
            return
        if self._ocupado(j, res):
            return
        a = V.ACCIONES["cocinar"]
        error = self._bloqueo_accion(j, a) or self._iniciar_coccion([j], arg, juntos=False)
        if error:
            res.alerta = error
            self._b_recetas(j, "", res)
            return
        self._cobrar_accion(j, a)  # suma el consumo
        self._b_coccion(j, "", res)

    def _iniciar_coccion(self, cocineros: list[Jugador], extra: str, juntos: bool) -> str | None:
        clave, _, porciones = extra.partition(":")
        r = C.RECETAS.get(clave)
        porciones = int(porciones) if porciones.isdigit() else 1
        if r is None or porciones not in (1, 2):
            return "Receta no válida."
        h = self._hogar(cocineros[0].sala_id)
        if r.nivel > self._nivel_super(h):
            return "Esa receta todavía no está en su recetario: cocinen más para que el súper crezca."
        coccion = self._coccion(h)
        if coccion:
            quien = self.db.jugador(coccion["cocineros"][0])
            return f"La cocina está ocupada: {quien.personaje if quien else 'alguien'} está cocinando."
        despensa = self._despensa(h)
        falta = C.faltan(despensa, r, porciones)
        if falta:
            return f"Falta: {C.texto_ingredientes(falta)}."
        ahora = self.reloj()
        h.despensa = json.dumps(C.usar(despensa, r, porciones))
        h.cocina = json.dumps({
            "receta": r.clave, "porciones": porciones, "paso": 0, "paso_ini": ahora,
            "cocineros": [c.id for c in cocineros], "juntos": juntos, "avisado": False,
        })
        self.db.guardar_hogar(h)
        minutos = C.duracion_maxima(r, juntos)
        for c in cocineros:
            otro = next((o.id for o in cocineros if o.id != c.id), None)
            self._empezar(c, V.ACCIONES["cocinar"], r.clave, otro, ahora, minutos=minutos)
        return None

    def _tiempos_paso(self, coccion: dict) -> tuple[str, float, float]:
        """(texto del paso, cuándo está listo, cuándo se quema) en tiempo real."""
        r = C.RECETAS[coccion["receta"]]
        texto, minutos = r.pasos[coccion["paso"]]
        minutos = C.minutos_paso(minutos, coccion["juntos"])
        listo = coccion["paso_ini"] + minutos * 60
        return texto, listo, listo + C.margen(minutos) * 60

    def _hora_sim(self, j: Jugador, real: float) -> str:
        """Hora del reloj del Sim en la que ocurrirá algo, dado un momento real futuro."""
        return self._hora(j, real)

    def _b_coccion(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        coccion = self._coccion(h)
        if not coccion:
            self._b_recetas(j, "", res, aviso)
            return
        r = C.RECETAS[coccion["receta"]]
        ahora = self.reloj()
        texto, listo, quema = self._tiempos_paso(coccion)
        cocineros = [self.db.jugador(c) for c in coccion["cocineros"]]
        lineas = [aviso, ""] if aviso else []
        lineas.append(
            f"{r.emoji} <b>{r.nombre}</b> · {coccion['porciones']} porción(es) · "
            f"paso {coccion['paso'] + 1} de {len(r.pasos)}"
        )
        if len(cocineros) > 1:
            lineas.append("💞 Cocinando juntos: cualquiera de los dos puede tocar ✅.")
        lineas.append("")
        for i, (t, m) in enumerate(r.pasos):
            marca = "✅" if i < coccion["paso"] else "👉" if i == coccion["paso"] else "▫️"
            lineas.append(f"{marca} {t} · {C.minutos_paso(m, coccion['juntos'])} min")
        lineas.append("")
        if ahora < listo:
            lineas.append(
                f"⏳ Estará listo a las {self._hora_sim(j, listo)} (faltan {math.ceil((listo - ahora) / 60)} min). "
                f"Toca ✅ entre las {self._hora_sim(j, listo)} y las {self._hora_sim(j, quema)}: si te pasas, ¡se quema! 🔥"
            )
        else:
            lineas.append(f"🔔 <b>¡Ya está!</b> Toca ✅ antes de las {self._hora_sim(j, quema)} o se quema.")
        es_cocinero = j.id in coccion["cocineros"]
        botones = [[("✅ Listo, siguiente paso", "coc:sig")], [("🔄 Actualizar", "cocina"), ("🗑️ Abandonar", "coc:x")]] if es_cocinero else []
        botones.append([("🧍 Mi Sim", "sim")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="cocina")

    def _siguiente_paso(self, j: Jugador, res) -> None:
        from .juego import Aviso, Pantalla

        h = self._hogar(j.sala_id)
        coccion = self._coccion(h)
        if not coccion or j.id not in coccion["cocineros"]:
            res.alerta = "No estás cocinando."
            self._b_recetas(j, "", res)
            return
        ahora = self.reloj()
        texto, listo, quema = self._tiempos_paso(coccion)
        if ahora < listo:
            res.alerta = f"Todavía no: faltan {math.ceil((listo - ahora) / 60)} min."
            self._b_coccion(j, "", res)
            return
        if ahora > quema:
            noticia = self._quemar(h, coccion)
            res.pantalla = self._pantalla_sim(j, noticia)
            res.avisos += [Aviso(c, noticia, [[("🧍 Mi Sim", "sim")]]) for c in coccion["cocineros"] if c != j.id]
            return
        r = C.RECETAS[coccion["receta"]]
        coccion["paso"] += 1
        coccion["paso_ini"] = ahora
        coccion["avisado"] = False
        if coccion["paso"] < len(r.pasos):
            h.cocina = json.dumps(coccion)
            self.db.guardar_hogar(h)
            self._b_coccion(j, "", res, f"👍 {texto}: ¡hecho!")
            return
        nevera = self._nevera(h)
        nevera[r.clave] = nevera.get(r.clave, 0) + coccion["porciones"]
        h.nevera = json.dumps(nevera)
        self.db.guardar_hogar(h)
        self._terminar_coccion(h, coccion)
        self._evento_cocinado(h, coccion)
        if coccion["juntos"]:
            self._avanzar_reto(h, "cocinar")
        self._contar_receta(h, res)
        noticia = f"🍽️ <b>¡{r.nombre} listo!</b> {coccion['porciones']} porción(es) en la nevera."
        res.avisos += [Aviso(c, noticia, [[("🍽️ Comer", f"a:comer:{r.clave}")]]) for c in coccion["cocineros"] if c != j.id]
        res.pantalla = Pantalla(
            noticia + "\n¿Lo comes ahora o lo guardas en un táper para el trabajo?",
            [
                [("🍽️ Comer ahora", f"a:comer:{r.clave}"), ("🥡 Guardar en táper", f"taper:{r.clave}")],
                [("🧊 Nevera", "nevera"), ("🧍 Mi Sim", "sim")],
            ],
            clave="nevera",
        )

    def _terminar_coccion(self, h: Hogar, coccion: dict, quien: Jugador | None = None) -> None:
        """Libera la cocina y termina la acción de cocinar de todos los cocineros."""
        h.cocina = ""
        self.db.guardar_hogar(h)
        ahora = self.reloj()
        for cid in coccion["cocineros"]:
            c = quien if quien is not None and quien.id == cid else self.db.jugador(cid)
            accion = self._accion(c) if c else None
            if accion and accion.get("k") == "cocinar":
                self._vivir(c, ahora)
                c.accion = None
                c.ultima_jugada = max(c.ultima_jugada, ahora)
                self.db.guardar_jugador(c)

    def _quemar(self, h: Hogar, coccion: dict) -> str:
        self._terminar_coccion(h, coccion)
        return f"🔥 <b>¡Se quemó {C.RECETAS[coccion['receta']].nombre.lower()}!</b> Se perdieron los ingredientes."

    def _tick_cocina(self, res) -> None:
        from .juego import Aviso

        ahora = self.reloj()
        for h in self.db.hogares():
            coccion = self._coccion(h)
            if not coccion:
                continue
            texto, listo, quema = self._tiempos_paso(coccion)
            if ahora > quema:
                noticia = self._quemar(h, coccion)
                res.avisos += [Aviso(c, noticia, [[("🧍 Mi Sim", "sim")]]) for c in coccion["cocineros"]]
            elif ahora >= listo and not coccion.get("avisado"):
                coccion["avisado"] = True
                h.cocina = json.dumps(coccion)
                self.db.guardar_hogar(h)
                for cid in coccion["cocineros"]:
                    c = self.db.jugador(cid)
                    if c:
                        res.avisos.append(Aviso(
                            cid,
                            f"🔔 <b>{texto}: ¡listo!</b> Toca ✅ antes de las {self._hora_sim(c, quema)} o se quema.",
                            [[("✅ Listo, siguiente paso", "coc:sig")]],
                        ))

    # ------------------------------------------------------------------
    # Comer de la nevera y táper
    # ------------------------------------------------------------------

    def _b_elegir_comida(self, j: Jugador, res) -> None:
        """⚡ Acciones → Comer → Comer lo que hay: lo que queda en la nevera o en el táper."""
        from .juego import Pantalla

        nevera = self._nevera(self._hogar(j.sala_id))
        _, nombre_comida, valor = V.comida_del_momento(self._hora_local(j))
        botones = [
            [(f"{C.RECETAS[r].emoji} {C.RECETAS[r].nombre} ({n})", f"a:comer:{r}")]
            for r, n in nevera.items() if r in C.RECETAS and n > 0
        ]
        if j.taper in C.RECETAS:
            botones.append([(f"🥡 Tu táper: {C.RECETAS[j.taper].nombre.lower()}", "a:comer:taper")])
        if botones:
            texto = (
                f"🍽️ <b>Comer lo que hay</b> · {nombre_comida.lower()} (+{valor} de hambre)\n"
                "Esto ya está pagado: elige qué comer."
            )
        else:
            texto = (
                "🍽️ <b>Comer lo que hay</b>\nNo queda nada hecho en la nevera. "
                "Preparen comida o pidan a domicilio."
            )
        botones.append([("🍳 Preparar comida", "a:cocinar"), ("🛵 Pedir a domicilio", "a:domicilio")])
        botones.append([("⬅️ Atrás", "acc:comer")])
        res.pantalla = Pantalla(texto, botones, clave="acc:comer")

    def _b_elegir_taper(self, j: Jugador, res) -> None:
        from .juego import Pantalla

        nevera = self._nevera(self._hogar(j.sala_id))
        botones = [
            [(f"{C.RECETAS[r].emoji} {C.RECETAS[r].nombre} ({n})", f"taper:{r}")]
            for r, n in nevera.items() if r in C.RECETAS and n > 0
        ]
        texto = "🥡 <b>Preparar un táper</b>\nElige qué te llevas al trabajo:"
        if j.taper in C.RECETAS:
            texto = f"🥡 Ya tienes un táper con {C.RECETAS[j.taper].nombre.lower()}."
            botones = []
        elif not botones:
            texto = "🥡 No hay comida hecha en la nevera. Cocina primero y guarda una porción."
        botones.append([("🍳 Preparar comida", "a:cocinar"), ("⬅️ Atrás", "acc:comer")])
        res.pantalla = Pantalla(texto, botones, clave="acc:comer")

    def _b_taper(self, j: Jugador, receta: str, res) -> None:
        if self._ocupado(j, res):
            return
        h = self._hogar(j.sala_id)
        nevera = self._nevera(h)
        if receta not in C.RECETAS or nevera.get(receta, 0) < 1 or j.taper:
            res.alerta = "No se puede preparar ese táper."
            self._b_elegir_taper(j, res)
            return
        nevera[receta] -= 1
        if not nevera[receta]:
            nevera.pop(receta)
        h.nevera = json.dumps(nevera)
        self.db.guardar_hogar(h)
        j.taper = receta
        self.db.guardar_jugador(j)
        self._hacer(j, V.ACCIONES["taper"], "", res)
        res.pantalla.texto = f"🥡 Táper listo con {C.RECETAS[receta].nombre.lower()} para el trabajo.\n\n" + res.pantalla.texto

    def _sacar_de_la_nevera(self, j: Jugador, receta: str, porciones: int) -> str | None:
        h = self._hogar(j.sala_id)
        nevera = self._nevera(h)
        if receta not in C.RECETAS or nevera.get(receta, 0) < porciones:
            return f"No hay {porciones} porción(es) de eso en la nevera."
        nevera[receta] -= porciones
        if not nevera[receta]:
            nevera.pop(receta)
        h.nevera = json.dumps(nevera)
        self.db.guardar_hogar(h)
        return None
