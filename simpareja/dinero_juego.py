"""Casa, dinero y gastos dentro del juego (parte 5).

`DineroMixin` se mezcla con `Juego`. La cuenta compartida es de la sala; cada jugador
tiene su cartera. Los días del hogar avanzan con el reloj del Sim que vaya más adelantado.
"""

from __future__ import annotations

import json

from . import cocina as C
from . import dinero as D
from . import vida as V
from .db import Hogar, Jugador, Movimiento

MONTOS = (50, 100, 500)
MAX_DIAS_POR_VEZ = 400


class DineroMixin:
    # ------------------------------------------------------------------
    # Cuentas
    # ------------------------------------------------------------------

    def _dia_hogar(self, sala_id: int) -> int:
        """Los días del hogar son días reales: facturas cada 30 días."""
        return int(self.reloj() // V.DIA)

    def _anotar_movimiento(self, sala_id: int, jugador_id: int | None, cuenta: str, monto: int, concepto: str) -> None:
        self.db.anotar_movimiento(Movimiento(None, sala_id, jugador_id, cuenta, monto, concepto, self.reloj()))

    def _preparar_casa(self, h: Hogar) -> None:
        """La primera vez: los ahorros de la pareja y la compra de la casita con entrada."""
        if h.casa:
            return
        dia = self._dia_hogar(h.sala_id)
        h.casa = "casita"
        h.cuenta = D.DINERO_INICIAL - D.ENTRADA_CASA
        h.dia_hogar = dia
        h.proximo_cobro = dia + D.DIAS_POR_MES
        self.db.guardar_hogar(h)
        self._anotar_movimiento(h.sala_id, None, "compartida", D.DINERO_INICIAL, "💵 Ahorros iniciales de la pareja")
        self._anotar_movimiento(h.sala_id, None, "compartida", -D.ENTRADA_CASA, "🔑 Entrada de la Casita")

    def _pagar(self, j: Jugador, monto: int, concepto: str) -> bool:
        """Paga desde la cuenta compartida y, si no alcanza, desde la cartera del jugador."""
        h = self._hogar(j.sala_id)
        if h.cuenta >= monto:
            h.cuenta -= monto
            self.db.guardar_hogar(h)
            self._anotar_movimiento(j.sala_id, j.id, "compartida", -monto, concepto)
            return True
        if j.cartera >= monto:
            j.cartera -= monto
            self.db.guardar_jugador(j)
            self._anotar_movimiento(j.sala_id, j.id, "cartera", -monto, concepto)
            return True
        return False

    # ------------------------------------------------------------------
    # Lo que cuesta cada acción
    # ------------------------------------------------------------------

    def _bloqueo_accion(self, j: Jugador, a: V.Accion) -> str | None:
        h = self._hogar(j.sala_id)
        return D.falta_servicio(a.clave, D.servicios_cortados(json.loads(h.pendientes)))

    def _extras(self, j: Jugador) -> dict:
        return json.loads(j.extras or "{}")

    def _gimnasio_al_dia(self, j: Jugador, dia: int) -> bool:
        return self._extras(j).get("gimnasio_hasta", 0) >= dia

    def _costo_accion(self, j: Jugador, a: V.Accion, extra: str = "", juntos: bool = False,
                      pareja: Jugador | None = None) -> tuple[int, str]:
        """Lo que cuesta empezar la acción en total (para uno o para los dos) y el concepto."""
        personas = 2 if juntos else 1
        dia = self._hoy(j)
        if a.clave == "comer":
            return 0, ""  # de la nevera o del táper: ya se pagó
        if a.clave == "domicilio" or (a.comida and extra == "comprar"):
            comida, _, _ = V.comida_del_momento(self._hora_local(j))
            return D.precio_comida(comida) * D.DOMICILIO * personas, f"🛵 Pedido a domicilio ({comida})"
        if a.clave in D.PRECIO_SALIDA:
            precio = D.PRECIO_SALIDA[a.clave][1 if juntos else 0]
            if self._finde(j):
                precio = round(precio * (1 + D.RECARGO_FIN_DE_SEMANA))
            return precio, f"{a.emoji} {a.titulo(juntos)}"
        if a.clave == "gimnasio":
            sin_cuota = [x for x in (j, pareja) if x is not None and not self._gimnasio_al_dia(x, dia)]
            return D.GIMNASIO_MES * len(sin_cuota), "🏋️ Cuota del gimnasio (30 días)"
        if a.clave == "picar":
            return D.PRECIO_PICAR, "🍎 Algo para picar"
        return 0, ""

    def _cobrar_accion(self, j: Jugador, a: V.Accion, juntos: bool = False, extra: str = "",
                       pareja: Jugador | None = None) -> str | None:
        """Cobra lo que cuesta empezar la acción y suma su consumo. Devuelve un error si no se puede."""
        bloqueo = self._bloqueo_accion(j, a)
        if bloqueo:
            return bloqueo
        if a.clave == "comer" and extra in C.RECETAS:
            error = self._sacar_de_la_nevera(j, extra, 2 if juntos else 1)
            if error:
                return error
        elif a.clave == "comer" and extra == "taper":
            if not j.taper:
                return "No tienes ningún táper."
            j.taper = ""
            self.db.guardar_jugador(j)
        elif a.clave == "comer":
            return "Elige qué comer de la nevera."
        costo, concepto = self._costo_accion(j, a, extra, juntos, pareja)
        if costo:
            if not self._pagar(j, costo, concepto):
                return (
                    f"💸 No alcanza el dinero ({D.dinero(costo)}). "
                    "Pasen dinero a la cuenta compartida en 💰 Dinero."
                )
            if a.clave == "gimnasio":
                dia = self._hoy(j)
                for x in (j, pareja):
                    if x is not None and not self._gimnasio_al_dia(x, dia):
                        extras = self._extras(x)
                        extras["gimnasio_hasta"] = dia + D.DIAS_POR_MES - 1
                        x.extras = json.dumps(extras)
                        self.db.guardar_jugador(x)
        consumo = D.CONSUMO.get(a.clave)
        if consumo:
            h = self._hogar(j.sala_id)
            total_consumo = json.loads(h.consumo)
            for servicio, monto in consumo.items():
                total_consumo[servicio] = round(total_consumo.get(servicio, 0) + monto, 2)
            h.consumo = json.dumps(total_consumo)
            self.db.guardar_hogar(h)
        return None

    # ------------------------------------------------------------------
    # El paso de los días: imprevistos y facturas del mes
    # ------------------------------------------------------------------

    def _procesar_hogar(self, h: Hogar) -> list[str]:
        """Avanza los días del hogar hasta hoy. Devuelve las noticias para avisar a la pareja."""
        if not h.casa:
            return []
        noticias = []
        dia = self._dia_hogar(h.sala_id)
        if h.dia_hogar < 10000:  # contado con el reloj antiguo del juego: pasarlo a días reales
            faltaban = max(1, h.proximo_cobro - h.dia_hogar)
            h.dia_hogar, h.proximo_cobro = dia, dia + faltaban
            self.db.guardar_hogar(h)
        pasos = 0
        while h.dia_hogar < dia and pasos < MAX_DIAS_POR_VEZ:
            pasos += 1
            h.dia_hogar += 1
            suceso = D.imprevisto(self.rng)
            if suceso:
                texto, costo = suceso
                if h.cuenta >= costo:
                    h.cuenta -= costo
                    self._anotar_movimiento(h.sala_id, None, "compartida", -costo, texto)
                    noticias.append(f"{texto}: {D.dinero(costo)}, pagado de la cuenta compartida.")
                else:
                    pendientes = json.loads(h.pendientes)
                    pendientes.append({"clave": "imprevisto", "monto": costo, "concepto": texto})
                    h.pendientes = json.dumps(pendientes)
                    noticias.append(f"{texto}: {D.dinero(costo)}. No alcanzó la cuenta: queda pendiente.")
            if h.dia_hogar >= h.proximo_cobro:
                noticias.append(self._cobrar_mes(h))
        if pasos:
            self.db.guardar_hogar(h)
        return noticias

    def _cobrar_mes(self, h: Hogar) -> str:
        h.cuenta, pagado, impagos = D.cobrar_mes(h.cuenta, json.loads(h.consumo))
        for clave, monto in pagado:
            f = D.POR_CLAVE_FACTURA[clave]
            self._anotar_movimiento(h.sala_id, None, "compartida", -monto, f"{f.emoji} {f.nombre} del mes")
        h.pendientes = json.dumps(json.loads(h.pendientes) + impagos)
        h.consumo = "{}"
        h.proximo_cobro += D.DIAS_POR_MES
        lineas = [f"📄 <b>Se cobraron las facturas del mes</b>: {D.dinero(sum(m for _, m in pagado))}."]
        for impago in impagos:
            f = D.POR_CLAVE_FACTURA[impago["clave"]]
            corte = f" Se cortó el servicio: {f.sin_servicio}." if f.clave in D.SERVICIOS else ""
            lineas.append(f"⚠️ No alcanzó para {f.emoji} {f.nombre}: ahora deben {D.dinero(impago['monto'])} (con recargo del 10 %).{corte}")
        lineas.append(f"🏦 Quedan {D.dinero(h.cuenta)} en la cuenta compartida.")
        return "\n".join(lineas)

    def _tick_dinero(self, res) -> None:
        from .juego import Aviso

        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if not miembros:
                continue
            noticias = self._procesar_hogar(h)
            if noticias:
                texto = "\n\n".join(noticias)
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("💰 Dinero", "dinero")]]))

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _pendientes_texto(self, pendientes: list[dict]) -> list[str]:
        lineas = []
        for p in pendientes:
            if p["clave"] in D.POR_CLAVE_FACTURA:
                f = D.POR_CLAVE_FACTURA[p["clave"]]
                cortado = " · ❌ servicio cortado" if f.clave in D.SERVICIOS else ""
                lineas.append(f"⚠️ {f.emoji} {f.nombre}: {D.dinero(p['monto'])}{cortado}")
            else:
                lineas.append(f"⚠️ {p.get('concepto', 'Imprevisto')}: {D.dinero(p['monto'])}")
        return lineas

    def _b_dinero(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla, duracion

        h = self._hogar(j.sala_id)
        res.notas += self._procesar_hogar(h)
        ahora = self.reloj()
        dia = self._dia_hogar(j.sala_id)
        pendientes = json.loads(h.pendientes)
        consumo = json.loads(h.consumo)
        lineas = [aviso, ""] if aviso else []
        lineas += [
            "💰 <b>Dinero</b>",
            "",
            f"👛 Tu cartera: <b>{D.dinero(j.cartera)}</b>",
            f"🏦 Cuenta compartida: <b>{D.dinero(h.cuenta)}</b>",
            f"📄 Facturas del mes: {D.dinero(D.total_mes(consumo))} · se cobran en "
            f"{max(0, h.proximo_cobro - dia)} días",
        ]
        if pendientes:
            lineas += ["", "<b>Por pagar</b>"] + self._pendientes_texto(pendientes)
        movimientos = self.db.movimientos(j.sala_id, 6)
        if movimientos:
            lineas += ["", "<b>Últimos movimientos</b>"]
            for m in movimientos:
                quien = self.db.jugador(m.jugador_id) if m.jugador_id else None
                cuenta = "👛" if m.cuenta == "cartera" else "🏦"
                signo = "+" if m.monto > 0 else ""
                de_quien = f" ({quien.personaje})" if quien else ""
                lineas.append(f"{cuenta} {signo}{D.dinero(m.monto)} {m.concepto}{de_quien} · hace {duracion(ahora - m.ts)}")
        botones = [
            [("⬆️ Cartera → compartida", "mover:dep"), ("⬇️ Compartida → cartera", "mover:ret")],
            [("📄 Facturas", "facturas"), ("🏡 Casa", "casa")],
            [("⬅️ Atrás", "mest"), ("🎮 Menú", "menu")],
        ]
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="dinero")

    def _b_mover(self, j: Jugador, direccion: str, res) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        if direccion == "dep":
            titulo, disponible = "⬆️ <b>Pasar de tu cartera a la cuenta compartida</b>", j.cartera
        else:
            direccion = "ret"
            titulo, disponible = "⬇️ <b>Pasar de la cuenta compartida a tu cartera</b>", h.cuenta
        opciones = [(D.dinero(m), f"mv:{direccion}:{m}") for m in MONTOS if m <= disponible]
        if disponible > 0:
            opciones.append((f"Todo ({D.dinero(disponible)})", f"mv:{direccion}:{disponible}"))
        texto = f"{titulo}\n\nDisponible: {D.dinero(disponible)}"
        if not opciones:
            texto += "\n\nNo hay dinero para mover."
        res.pantalla = Pantalla(texto, [opciones[i:i + 2] for i in range(0, len(opciones), 2)] + [[("⬅️ Dinero", "dinero")]], clave=f"mover:{direccion}")

    def _b_mover_monto(self, j: Jugador, arg: str, res) -> None:
        direccion, _, monto = arg.partition(":")
        monto = int(monto) if monto.isdigit() else 0
        h = self._hogar(j.sala_id)
        aviso = None
        if monto <= 0:
            res.alerta = "Cantidad no válida."
        elif direccion == "dep" and j.cartera >= monto:
            j.cartera -= monto
            h.cuenta += monto
            self._anotar_movimiento(j.sala_id, j.id, "cartera", -monto, "⬆️ A la cuenta compartida")
            self._anotar_movimiento(j.sala_id, j.id, "compartida", monto, "⬆️ Desde la cartera")
            aviso = f"✅ Pasaste {D.dinero(monto)} a la cuenta compartida."
        elif direccion == "ret" and h.cuenta >= monto:
            h.cuenta -= monto
            j.cartera += monto
            self._anotar_movimiento(j.sala_id, j.id, "compartida", -monto, "⬇️ A una cartera")
            self._anotar_movimiento(j.sala_id, j.id, "cartera", monto, "⬇️ Desde la compartida")
            aviso = f"✅ Pasaste {D.dinero(monto)} a tu cartera."
        else:
            res.alerta = "No hay suficiente dinero."
        if aviso:
            self.db.guardar_jugador(j)
            self.db.guardar_hogar(h)
        self._b_dinero(j, "", res, aviso)

    def _b_facturas(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        res.notas += self._procesar_hogar(h)
        dia = self._dia_hogar(j.sala_id)
        consumo = json.loads(h.consumo)
        pendientes = json.loads(h.pendientes)
        lineas = [aviso, ""] if aviso else []
        lineas += [f"📄 <b>Facturas del mes</b> · se cobran en {max(0, h.proximo_cobro - dia)} días", ""]
        for f, monto in D.factura_del_mes(consumo):
            extra = f" (base {D.dinero(f.base)} + uso {D.dinero(monto - f.base)})" if monto != f.base else ""
            lineas.append(f"{f.emoji} {f.nombre}: {D.dinero(monto)}{extra}")
        lineas += [
            f"<b>Total: {D.dinero(D.total_mes(consumo))}</b>",
            "",
            "🍽️ La comida se paga en cada comida: $3 el desayuno, $5 el almuerzo y $4 la cena por persona.",
            "ℹ️ Se cobran solas de la cuenta compartida. Si no alcanza, hay un recargo del 10 % y se corta el servicio hasta que paguen.",
        ]
        botones = []
        if pendientes:
            lineas += ["", "<b>Por pagar</b>"] + self._pendientes_texto(pendientes)
            for i, p in enumerate(pendientes):
                nombre = D.POR_CLAVE_FACTURA[p["clave"]].nombre if p["clave"] in D.POR_CLAVE_FACTURA else "imprevisto"
                botones.append([(f"💳 Pagar {nombre} ({D.dinero(p['monto'])})", f"pagar:{i}")])
        botones.append([("⬅️ Dinero", "dinero")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="facturas")

    def _b_pagar(self, j: Jugador, arg: str, res) -> None:
        h = self._hogar(j.sala_id)
        pendientes = json.loads(h.pendientes)
        i = int(arg) if arg.isdigit() else -1
        if not 0 <= i < len(pendientes):
            res.alerta = "Esa deuda ya no está."
            self._b_facturas(j, "", res)
            return
        p = pendientes[i]
        nombre = D.POR_CLAVE_FACTURA[p["clave"]].nombre if p["clave"] in D.POR_CLAVE_FACTURA else p.get("concepto", "imprevisto")
        if not self._pagar(j, p["monto"], f"💳 Pago atrasado: {nombre}"):
            res.alerta = f"No alcanza: hacen falta {D.dinero(p['monto'])} en la cuenta compartida o en tu cartera."
            self._b_facturas(j, "", res)
            return
        h = self._hogar(j.sala_id)
        pendientes = json.loads(h.pendientes)
        pendientes.pop(i)
        h.pendientes = json.dumps(pendientes)
        self.db.guardar_hogar(h)
        aviso = f"✅ Pagaste {nombre}: {D.dinero(p['monto'])}."
        if p["clave"] in D.SERVICIOS and p["clave"] not in D.servicios_cortados(pendientes):
            aviso += " Ya volvió el servicio."
        self._b_facturas(j, "", res, aviso)

    def _b_casa(self, j: Jugador, arg: str, res) -> None:
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        cortados = D.servicios_cortados(json.loads(h.pendientes))
        zonas = json.loads(h.zonas)
        lineas = [
            f"{D.CASA_INICIAL['emoji']} <b>{D.CASA_INICIAL['nombre']}</b>",
            f"<i>{D.CASA_INICIAL['descripcion']}</i>",
            "",
        ]
        for z, (e, nombre) in V.ZONAS.items():
            lineas.append(f"{e} {nombre}: {V.estado_zona(zonas.get(z, 0))}")
        lineas.append(f"🧺 Ropa sucia: {h.ropa_sucia} prendas")
        lineas += ["", f"🔑 Hipoteca: {D.dinero(D.POR_CLAVE_FACTURA['hipoteca'].base)} al mes", "<b>Servicios</b>"]
        for clave in D.SERVICIOS:
            f = D.POR_CLAVE_FACTURA[clave]
            lineas.append(f"{f.emoji} {f.nombre}: {'❌ cortado' if clave in cortados else '✅ funciona'}")
        lineas += ["", "🛋️ <i>Muebles y mejoras de la casa llegarán más adelante.</i>"]
        res.pantalla = Pantalla(
            "\n".join(lineas),
            [[("🧹 Limpieza", "acc:limpieza"), ("💰 Dinero", "dinero")], [("⬅️ Atrás", "mcasa")]],
            clave="casa",
        )
