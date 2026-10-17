"""Mascota (actualización 2, parte 14).

`MascotaMixin` se mezcla con `Juego`. Adoptan un perro o un gato por $150, de acuerdo los dos
(eligen tipo, aspecto y nombre); la comida cuesta $40 al mes y va con las facturas. Tiene sus
barras: hambre, felicidad y limpieza, que bajan mientras alguno de los dos juega. Se le da de
comer, se juega con ella, se la baña y al perro se lo pasea (cuenta como salida al parque).
Hacerlo juntos sube la relación. Si se la descuida se pone triste, rompe cosas o hace ruido de
noche y no deja dormir. En el plano aparece con su inicial entre paréntesis, y en la leyenda con 🐶 o 🐱.

En `extras` del hogar: "mascota" {tipo, nombre, aspecto, nec, adoptada, rompio, ruido} y
"adopcion" (la propuesta). En `extras` del jugador: "mascota_nombre" mientras escribe el nombre.
"""

from __future__ import annotations

import json

from . import dinero as D
from . import vida as V
from .db import Hogar, Jugador

ADOPCION = 150
COMIDA_MES = 40
CUIDADOR_DIA = 20  # si se van de viaje
TIPOS = {"perro": ("🐶", "Perro", "Perra"), "gato": ("🐱", "Gato", "Gata")}
ASPECTOS = ("🤎 marrón", "🖤 negro", "🤍 blanco", "🧡 naranja", "🩶 gris", "🐾 con manchas")
BARRAS = (("hambre", "🍖", "Hambre", 8), ("felicidad", "😊", "Felicidad", 5), ("limpieza", "🛁", "Limpieza", 3))
TRISTE = 20  # por debajo, se pone triste
ROMPE = (30, 80)
RUIDO_ENERGIA = 10
NOMBRE_MAX = 20
# Acción del Sim → lo que le da a la mascota.
EFECTOS = {
    "dar_comida": {"hambre": 60},
    "jugar_mascota": {"felicidad": 35},
    "banar_mascota": {"limpieza": 70},
    "pasear": {"felicidad": 40, "hambre": -5},
}
JUNTOS_RELACION = 2  # cada vez que la pasean o juegan con ella juntos


class MascotaMixin:
    def _mascota(self, h: Hogar) -> dict | None:
        return self._extras_hogar(h).get("mascota")

    def _guardar_mascota(self, h: Hogar, mascota: dict) -> None:
        ex = self._extras_hogar(h)
        ex["mascota"] = mascota
        self._guardar_extras_hogar(h, ex)

    def _emoji_mascota(self, m: dict) -> str:
        return TIPOS[m["tipo"]][0]

    def _triste(self, m: dict) -> bool:
        return any(m["nec"][clave] < TRISTE for clave, *_ in BARRAS)

    def _falta_mascota(self, j: Jugador, a) -> str | None:
        """Las acciones con la mascota necesitan tenerla (y pasear, que sea un perro)."""
        if a.clave not in EFECTOS:
            return None
        m = self._mascota(self._hogar(j.sala_id)) if j.sala_id is not None else None
        if m is None:
            return "🐾 No tienen mascota: adóptenla en 🏠 Casa → Mascota."
        if a.clave == "pasear" and m["tipo"] != "perro":
            return f"🐱 A {m['nombre']} no se la pasea: los gatos prefieren jugar en casa."
        return None

    def _texto_mascota(self, m: dict) -> str:
        from .juego import esc

        barras = " · ".join(f"{e} {round(m['nec'][clave])}" for clave, e, _, _ in BARRAS)
        return f"{self._emoji_mascota(m)} {esc(m['nombre'])}: {barras}" + (" · 😢 triste" if self._triste(m) else "")

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------

    def _b_mascota(self, j: Jugador, arg: str, res, aviso: str | None = None) -> None:
        """🏠 Casa → 🐾 Mascota."""
        from .juego import Pantalla, esc

        h = self._hogar(j.sala_id)
        m = self._mascota(h)
        lineas = [aviso, ""] if aviso else []
        botones = []
        if m is None:
            lineas += [
                "🐾 <b>Mascota</b>",
                f"Adopten un perro o un gato por {D.dinero(ADOPCION)}. La comida cuesta {D.dinero(COMIDA_MES)} al mes.",
                "Tiene sus barras de hambre, felicidad y limpieza. Si la descuidan se pone triste, rompe cosas o "
                "hace ruido de noche.",
            ]
            propuesta = self._extras_hogar(h).get("adopcion")
            if propuesta:
                de = self.db.jugador(propuesta["de"])
                emoji, nombre, _ = TIPOS[propuesta["tipo"]]
                lineas += ["", f"💌 {esc(de.personaje) if de else '…'} propuso adoptar a {esc(propuesta['nombre'])}: "
                               f"{emoji} {nombre.lower()} {propuesta['aspecto']}."]
                if propuesta["de"] != j.id:
                    botones.append([("✅ ¡Sí, adoptémosla!", "mascok"), ("❌ Ahora no", "mascno")])
                else:
                    lineas.append("⏳ Esperando que acepte.")
            else:
                botones.append([("🐶 Adoptar un perro", "mascad:perro"), ("🐱 Adoptar un gato", "mascad:gato")])
        else:
            emoji, nombre, _ = TIPOS[m["tipo"]]
            lineas += [f"{emoji} <b>{esc(m['nombre'])}</b> · {nombre.lower()} {m['aspecto']}", ""]
            for clave, e, titulo, _ in BARRAS:
                lineas.append(f"{e} {V.barra(m['nec'][clave])} {round(m['nec'][clave])} {titulo}")
            if self._triste(m):
                lineas += ["", f"😢 {esc(m['nombre'])} está triste: necesita atención."]
            lineas += ["", f"🍖 Su comida: {D.dinero(COMIDA_MES)} al mes (con las facturas)."]
            botones.append([("🍖 Darle de comer", "a:dar_comida"), ("🎾 Jugar", "a:jugar_mascota")])
            fila = [("🛁 Bañarla", "a:banar_mascota")]
            if m["tipo"] == "perro":
                fila.append(("🐕 Pasearlo", "a:pasear"))
            botones.append(fila)
        botones.append([("⬅️ Atrás", "mcasa")])
        res.pantalla = Pantalla("\n".join(lineas), botones, clave="mascota")

    def _b_adoptar(self, j: Jugador, arg: str, res) -> None:
        """mascad:<tipo> · mascad:<tipo>:<aspecto> (luego pide el nombre)."""
        from .juego import Pantalla

        h = self._hogar(j.sala_id)
        if self._mascota(h) or self._extras_hogar(h).get("adopcion"):
            self._b_mascota(j, "", res)
            return
        tipo, _, aspecto = arg.partition(":")
        if tipo not in TIPOS:
            self._b_mascota(j, "", res)
            return
        emoji, nombre, _ = TIPOS[tipo]
        if not aspecto.isdigit() or int(aspecto) >= len(ASPECTOS):
            res.pantalla = Pantalla(
                f"{emoji} ¿Cómo es su {nombre.lower()}?",
                [[(a, f"mascad:{tipo}:{i}") for i, a in enumerate(ASPECTOS[k:k + 3], k)] for k in (0, 3)]
                + [[("⬅️ Atrás", "mascota")]],
                clave="mascota",
            )
            return
        extras = self._extras(j)
        extras["mascota_nombre"] = {"tipo": tipo, "aspecto": ASPECTOS[int(aspecto)], "ts": self.reloj()}
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        res.pantalla = Pantalla(f"{emoji} ✍️ ¿Cómo se va a llamar? Escribe su nombre:", [[("⬅️ Atrás", "mascota")]],
                                clave="mascnombre")

    def _nombre_mascota(self, j: Jugador, texto: str, res) -> None:
        """El nombre que escribió: con pareja, se lo propone; sin pareja, la adopta."""
        from .juego import Aviso, esc

        extras = self._extras(j)
        pendiente = extras.pop("mascota_nombre", None)
        j.extras = json.dumps(extras)
        self.db.guardar_jugador(j)
        nombre = " ".join(texto.split())[:NOMBRE_MAX]
        h = self._hogar(j.sala_id)
        if pendiente is None or not nombre or self._mascota(h):
            self._b_mascota(j, "", res)
            return
        propuesta = {"de": j.id, "tipo": pendiente["tipo"], "aspecto": pendiente["aspecto"], "nombre": nombre}
        pareja = self._pareja_en_sala(j)
        if pareja is None:
            self._adoptar(j, propuesta, res)
            return
        ex = self._extras_hogar(h)
        ex["adopcion"] = propuesta
        self._guardar_extras_hogar(h, ex)
        emoji, tipo, _ = TIPOS[propuesta["tipo"]]
        res.avisos.append(Aviso(
            pareja.id,
            f"🐾 {self._firma(j)} quiere adoptar a <b>{esc(nombre)}</b>: {emoji} {tipo.lower()} {propuesta['aspecto']} "
            f"({D.dinero(ADOPCION)}, y {D.dinero(COMIDA_MES)} al mes de comida). ¿Aceptas?",
            [[("✅ ¡Sí, adoptémosla!", "mascok"), ("❌ Ahora no", "mascno")]],
        ))
        self._b_mascota(j, "", res, "💌 Propuesta enviada: la adoptan cuando tu pareja acepte.")

    def _b_adopcion_si(self, j: Jugador, arg: str, res) -> None:
        h = self._hogar(j.sala_id)
        propuesta = self._extras_hogar(h).get("adopcion")
        if not propuesta or propuesta["de"] == j.id or self._mascota(h):
            res.alerta = "Esa propuesta ya no está."
            self._b_mascota(j, "", res)
            return
        self._adoptar(j, propuesta, res)

    def _b_adopcion_no(self, j: Jugador, arg: str, res) -> None:
        from .juego import Aviso

        h = self._hogar(j.sala_id)
        ex = self._extras_hogar(h)
        propuesta = ex.get("adopcion")
        if propuesta and propuesta["de"] != j.id:
            ex.pop("adopcion")
            self._guardar_extras_hogar(h, ex)
            res.avisos.append(Aviso(propuesta["de"], f"🙈 {self._firma(j)} prefiere esperar para adoptar."))
        self._b_mascota(j, "", res)

    def _adoptar(self, j: Jugador, propuesta: dict, res) -> None:
        from .juego import Aviso, esc

        if not self._pagar(j, ADOPCION, "🐾 Adopción"):
            res.alerta = f"No alcanza: la adopción cuesta {D.dinero(ADOPCION)}."
            self._b_mascota(j, "", res)
            return
        h = self._hogar(j.sala_id)  # _pagar ya guardó la cuenta
        ex = self._extras_hogar(h)
        ex.pop("adopcion", None)
        ex["mascota"] = {
            "tipo": propuesta["tipo"], "aspecto": propuesta["aspecto"], "nombre": propuesta["nombre"],
            "nec": {clave: 100 for clave, *_ in BARRAS}, "adoptada": self.reloj(),
        }
        self._guardar_extras_hogar(h, ex)
        self._lograr_hito(h, "mascota")
        emoji = TIPOS[propuesta["tipo"]][0]
        texto = f"{emoji}🎉 <b>¡{esc(propuesta['nombre'])} llegó a casa!</b> Cuídenla bien."
        for m in self._companeros(j):
            if m.estado == "activo":
                res.avisos.append(Aviso(m.id, texto, [[("🐾 Mascota", "mascota")]]))
        res.ediciones += self._refrescar_sala(j.sala_id, excepto=j.id)
        self._b_mascota(j, "", res, texto)

    # ------------------------------------------------------------------
    # Efectos y paso del tiempo
    # ------------------------------------------------------------------

    def _efecto_mascota(self, j: Jugador, accion: dict) -> str:
        """Al terminar una acción con la mascota: sus barras y, si fue juntos, la relación."""
        efectos = EFECTOS.get(accion["k"])
        h = self._hogar(j.sala_id)
        m = self._mascota(h)
        if not efectos or m is None:
            return ""
        ya = accion["rini"] in m.get("contados", [])
        if not ya:
            for clave, valor in efectos.items():
                m["nec"][clave] = max(0, min(100, m["nec"][clave] + valor))
            m["contados"] = (m.get("contados", []) + [accion["rini"]])[-10:]
            self._guardar_mascota(h, m)
        if accion.get("con") and accion["k"] in ("pasear", "jugar_mascota"):
            self._cambiar_relacion(j, JUNTOS_RELACION, f"{self._emoji_mascota(m)} Con {m['nombre']}, juntos", auto=True)
        return f" {self._emoji_mascota(m)} {m['nombre']} está feliz." if not ya else ""

    def _tick_mascota(self, res) -> None:
        """Las barras bajan mientras alguno juega; si se la descuida, se pone triste, rompe cosas o hace ruido."""
        from .juego import Aviso

        ahora = self.reloj()
        for h in self.db.hogares():
            ex = self._extras_hogar(h)
            if not ex.get("mascota"):
                continue
            miembros = [x for x in self.db.miembros_sala(h.sala_id) if x.estado == "activo"]
            if not miembros:
                continue
            h = self._hogar(h.sala_id)
            m = self._mascota(h)
            desde = m.get("vivo", ahora)
            m["vivo"] = ahora
            jugando = any(not self._congelado(x, ahora) for x in miembros) and not any(self._de_viaje(x) for x in miembros)
            if jugando and ahora > desde:
                horas = (ahora - desde) / V.HORA
                for clave, _, _, baja in BARRAS:
                    m["nec"][clave] = max(0.0, m["nec"][clave] - baja * horas)
            noticias = []
            hoy = self._local(miembros[0]).date().toordinal()
            if jugando and m["nec"]["felicidad"] < TRISTE and m.get("rompio") != hoy and self.rng.random() < 0.02:
                m["rompio"] = hoy  # como mucho una vez al día
                costo = self.rng.randint(*ROMPE)
                h.cuenta -= costo
                self._anotar_movimiento(h.sala_id, None, "compartida", -costo, f"{self._emoji_mascota(m)} {m['nombre']} rompió algo")
                noticias.append(f"💥 {self._emoji_mascota(m)} {m['nombre']} está triste y rompió algo: {D.dinero(costo)}.")
            hora = self._local(miembros[0]).hour
            de_noche = hora >= 22 or hora < 7
            if de_noche and self._triste(m) and m.get("ruido") != hoy:
                dormidos = [x for x in miembros if (self._accion(x) or {}).get("k") == "dormir"]
                if dormidos:
                    m["ruido"] = hoy
                    for x in dormidos:
                        self._sumar_necesidades(x, {"energia": -RUIDO_ENERGIA})
                    ruido = "ladró" if m["tipo"] == "perro" else "maulló"
                    noticias.append(f"🌙 {self._emoji_mascota(m)} {m['nombre']} {ruido} toda la noche y no los dejó "
                                    f"dormir bien (−{RUIDO_ENERGIA} ⚡). Está triste: necesita atención.")
            h.extras = json.dumps({**self._extras_hogar(h), "mascota": m})
            self.db.guardar_hogar(h)
            for texto in noticias:
                for x in miembros:
                    res.avisos.append(Aviso(x.id, texto, [[("🐾 Mascota", "mascota")]]))
