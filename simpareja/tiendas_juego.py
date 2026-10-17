"""Objetos de la casa, tiendas y remodelación (actualización 2, parte 13).

`TiendasMixin` se mezcla con `Juego`. Los objetos son de la pareja (se mudan con ellos) y se
guardan en `extras` del hogar: "objetos" [claves].
"""

from __future__ import annotations

from . import dinero as D
from . import objetos as O
from .db import Hogar, Jugador


class TiendasMixin:
    def _objetos(self, h: Hogar) -> set[str]:
        return set(self._extras_hogar(h).get("objetos", []))

    def _tiene(self, j: Jugador, clave: str) -> bool:
        return j.sala_id is not None and clave in self._objetos(self._hogar(j.sala_id))

    def _nivel_tiendas(self, h: Hogar) -> int:
        """Las tiendas sacan más cosas con el progreso: 1 + los hitos que han celebrado."""
        return 1 + len(self._extras_hogar(h).get("hitos_celebrados", {}))

    def _falta_objeto(self, j: Jugador, a) -> str | None:
        """Si la acción necesita un objeto que no tienen, el motivo."""
        if a.objeto and not self._tiene(j, a.objeto):
            o = O.OBJETOS[a.objeto]
            tienda = O.TIENDAS[o.tienda].split(" ", 1)[1].lower()
            return f"{o.emoji} No tienen {o.nombre.lower()}: cómprenla en la {tienda} ({D.dinero(o.precio)})."
        return None

    def _con_objetos(self, j: Jugador, clave: str, efectos: dict) -> dict:
        return O.aplicar_bonos(clave, efectos, self._objetos(self._hogar(j.sala_id)))

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_objetos(self, j: Jugador, arg: str, res) -> None:
        """🏠 Casa → 🪑 Objetos: los que tienen y los que les faltan."""
        from .juego import Pantalla

        tienen = self._objetos(self._hogar(j.sala_id))
        lineas = ["🪑 <b>Objetos de la casa</b>", "", "Incluidos con la casa: " + ", ".join(O.INCLUIDOS) + ".", ""]
        propios = [O.OBJETOS[c] for c in O.OBJETOS if c in tienen]
        if propios:
            lineas.append("<b>Tienen</b>")
            lineas += [f"✅ {o.emoji} {o.nombre}: <i>{o.efecto}</i>" for o in propios]
            lineas.append("")
        faltan = [o for o in O.OBJETOS.values() if o.clave not in tienen and o.tienda != "reforma" and o.nivel == 1]
        if faltan:
            lineas.append("<b>Les faltan</b>")
            lineas += [f"▫️ {o.emoji} {o.nombre} · {D.dinero(o.precio)}: <i>{o.efecto}</i>" for o in faltan]
        botones = [
            [("🛋️ Tienda de muebles", "tienda:muebles"), ("📺 Electrónica", "tienda:electronica")],
            [("⬅️ Atrás", "mcasa")],
        ]
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="objetos")

    def _b_tienda(self, j: Jugador, tienda: str, res, aviso: str | None = None) -> None:
        """tienda:<muebles|electronica|reforma>"""
        from .juego import Pantalla

        if tienda not in O.TIENDAS:
            self._b_objetos(j, "", res)
            return
        h = self._hogar(j.sala_id)
        if tienda == "reforma" and not self._casa(h).propia:
            self._b_remodelar(j, "", res)
            return
        tienen = self._objetos(h)
        venta, bloqueados = O.del_nivel(tienda, self._nivel_tiendas(h))
        lineas = [aviso, ""] if aviso else []
        lineas += [f"<b>{O.TIENDAS[tienda]}</b>", f"🏦 Compartida {D.dinero(h.cuenta)} · 👛 Tu cartera {D.dinero(j.cartera)}", ""]
        botones = []
        for o in venta:
            if o.clave in tienen:
                lineas.append(f"✅ {o.emoji} {o.nombre} (ya lo tienen)")
            else:
                lineas.append(f"{o.emoji} <b>{o.nombre}</b> · {D.dinero(o.precio)}\n   <i>{o.efecto}</i>")
                botones.append([(f"🛍️ {o.nombre} · {D.dinero(o.precio)}", f"comprar:{o.clave}")])
        if bloqueados:
            lineas += ["", "🔒 <i>Con más hitos de pareja la tienda saca más cosas.</i>"]
        volver = "casa" if tienda == "reforma" else "mlug"
        botones.append([("🪑 Objetos", "objetos"), ("⬅️ Atrás", volver)])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="tienda")

    def _b_comprar(self, j: Jugador, clave: str, res) -> None:
        from .juego import Aviso

        o = O.OBJETOS.get(clave)
        h = self._hogar(j.sala_id)
        if o is None:
            self._b_objetos(j, "", res)
            return
        venta, _ = O.del_nivel(o.tienda, self._nivel_tiendas(h))
        if o.clave in self._objetos(h) or o not in venta or (o.tienda == "reforma" and not self._casa(h).propia):
            res.alerta = "Eso no se puede comprar ahora."
            self._b_tienda(j, o.tienda, res)
            return
        if not self._pagar(j, o.precio, f"{o.emoji} {o.nombre}"):
            res.alerta = f"No alcanza: {o.nombre.lower()} cuesta {D.dinero(o.precio)}."
            self._b_tienda(j, o.tienda, res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        ex = self._extras_hogar(h)
        ex["objetos"] = sorted(set(ex.get("objetos", [])) | {o.clave})
        self._guardar_extras_hogar(h, ex)
        for m in self._companeros(j):
            if m.estado == "activo":
                res.avisos.append(Aviso(m.id, f"🛍️ {self._firma(j)} compró {o.emoji} {o.nombre.lower()} para la casa."))
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        self._b_tienda(j, o.tienda, res, f"✅ ¡Compraron {o.emoji} {o.nombre.lower()}! {o.efecto}")
