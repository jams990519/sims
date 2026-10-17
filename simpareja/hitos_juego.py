"""Hitos de pareja (actualización 2, parte 12).

`HitosMixin` se mezcla con `Juego`. Los hitos son opcionales: cada pareja va a su ritmo. Cuando
logran uno, se celebra con los dos conectados: pantalla especial, recuerdo en el álbum y subida
del medidor de los dos. En 💕 Pareja → Hitos se ven los logrados y los pendientes.

En `extras` del hogar: "hitos" {clave: cuándo se logró} y "hitos_celebrados" {clave: cuándo}.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import vida as V
from .db import Hogar, Jugador

PRIMER_MES = 30 * V.DIA
RECUERDOS = 50


@dataclass(frozen=True)
class Hito:
    clave: str
    emoji: str
    nombre: str
    requisito: str
    relacion: int
    recompensa: str = ""
    listo: bool = True  # False: todavía no se puede lograr en el juego


HITOS = (
    Hito("primera_cita", "🌹", "Primera cita", "Su primera salida juntos (restaurante, cine o parque).", 10,
         "Se estrena el álbum de recuerdos."),
    Hito("primer_mes", "📅", "Primer mes", "30 días en la misma sala.", 15, "Se activa el aniversario mensual."),
    Hito("mudanza", "🚚", "Mudanza", "Mudarse a una casa más grande (unos $3.900 ahorrados; aceptan los dos).", 10,
         "Cuarto extra: cambian la renta y el plano."),
    Hito("mascota", "🐾", "Mascota", "Adoptar un perro o un gato ($150, de acuerdo los dos).", 10,
         "+$40 al mes de comida."),
    Hito("viaje", "✈️", "Primer viaje", "Un viaje juntos ($800 a $2.000) con días libres.", 20,
         "Diversión y energía al máximo."),
    Hito("compromiso", "💍", "Compromiso", "Relación de los dos por encima del 80 %, viaje hecho y un anillo.", 20,
         "Si la respuesta es no, se conserva el anillo."),
    Hito("boda", "💒", "Boda", "Estar comprometidos: planifican lugar, invitados, comida y fecha.", 25,
         "Estado «casados» y opción de unir el dinero."),
    Hito("casa_propia", "🏠", "Casa propia", "Comprar «nuestra casa» con unos $15.000 de entrada (aceptan los dos).", 20,
         "Pueden remodelar; la renta pasa a hipoteca."),
)
POR_CLAVE = {h.clave: h for h in HITOS}


class HitosMixin:
    def _lograr_hito(self, h: Hogar, clave: str) -> None:
        """Marca un hito como logrado (se celebra cuando estén los dos conectados)."""
        ex = self._extras_hogar(h)
        hitos = ex.setdefault("hitos", {})
        if clave not in hitos:
            hitos[clave] = self.reloj()
            self._guardar_extras_hogar(h, ex)

    def _b_hitos(self, j: Jugador, arg: str, res) -> None:
        """💕 Pareja → 🏆 Hitos."""
        from .juego import Pantalla

        if self._pareja_en_sala(j) is None:
            res.alerta = "Los hitos son para jugar en pareja: invita a alguien con 💌."
            self._b_menu_pareja(j, "", res)
            return
        ex = self._extras_hogar(self._hogar(j.sala_id))
        logrados, celebrados = ex.get("hitos", {}), ex.get("hitos_celebrados", {})
        lineas = ["🏆 <b>Hitos de pareja</b>", "Son opcionales: cada pareja va a su ritmo. Se celebran con los dos conectados.", ""]
        for hito in HITOS:
            if hito.clave in celebrados:
                local = self._local(j, celebrados[hito.clave])
                lineas.append(f"✅ {hito.emoji} <b>{hito.nombre}</b> · {local.day}/{local.month}")
            elif hito.clave in logrados:
                lineas.append(f"🎉 {hito.emoji} <b>{hito.nombre}</b>: ¡logrado! Se celebra cuando estén los dos conectados.")
            else:
                pronto = " 🚧" if not hito.listo else ""
                lineas.append(f"⬜ {hito.emoji} {hito.nombre}{pronto}: <i>{hito.requisito}</i>")
        lineas += ["", f"Llevan {len(celebrados)} de {len(HITOS)}."]
        res.pantalla = Pantalla(
            "\n".join(lineas),
            [[("✈️ Viajes", "viaje"), ("💍 Compromiso", "comp"), ("💒 Boda", "boda")],
             [("📸 Álbum", "album"), ("⬅️ Atrás", "mpar")]],
            clave="hitos",
        )

    def _tick_hitos(self, res) -> None:
        """Detecta el primer mes y celebra los hitos logrados cuando los dos están conectados."""
        from .juego import Aviso

        ahora = self.reloj()
        for h in self.db.hogares():
            miembros = [m for m in self.db.miembros_sala(h.sala_id) if m.estado == "activo"]
            if len(miembros) < 2 or not h.casa:
                continue
            h = self._hogar(h.sala_id)
            if ahora - max(m.creado for m in miembros) >= PRIMER_MES:
                self._lograr_hito(h, "primer_mes")
            ex = self._extras_hogar(h)
            pendientes = [c for c in ex.get("hitos", {}) if c not in ex.get("hitos_celebrados", {}) and c in POR_CLAVE]
            if not pendientes or any(self._estado_presencia(m, ahora) != "en_linea" for m in miembros):
                continue
            for clave in pendientes:
                hito = POR_CLAVE[clave]
                for m in miembros:
                    self._cambiar_relacion(m, hito.relacion, f"🏆 Hito: {hito.nombre}", auto=True)
                h = self._hogar(h.sala_id)
                ex = self._extras_hogar(h)
                ex.setdefault("hitos_celebrados", {})[clave] = ahora
                recuerdo = {"tipo": "hito", "texto": f"{hito.emoji} {hito.nombre}", "ts": ahora}
                ex["recuerdos"] = (ex.get("recuerdos", []) + [recuerdo])[-RECUERDOS:]
                self._guardar_extras_hogar(h, ex)
                texto = (
                    "🏆✨ <b>¡HITO DE PAREJA!</b> ✨🏆\n\n"
                    f"{hito.emoji} <b>{hito.nombre}</b>\n<i>{hito.requisito}</i>\n\n"
                    f"💗 +{hito.relacion} en el medidor de los dos · 📸 Guardado en el álbum"
                    + (f"\n🎁 {hito.recompensa}" if hito.recompensa else "")
                )
                for m in miembros:
                    res.avisos.append(Aviso(m.id, texto, [[("🏆 Hitos", "hitos"), ("📸 Álbum", "album")]]))
