"""Notas de cada actualización. Al arrancar una versión nueva, el bot las envía a todos los jugadores.

Para publicar un parche: sube VERSION y añade su entrada AL PRINCIPIO de NOVEDADES.
"""

VERSION = "0.2"

NOVEDADES: list[tuple[str, list[str]]] = [
    ("0.2", [
        "🧑‍🎨 Personaje completo: además del aspecto, ahora tiene hasta 3 <b>rasgos de personalidad</b>, "
        "una <b>aspiración de vida</b> y un <b>estado de ánimo</b> con su color (cámbialo cuando quieras con /animo). "
        "Si ya tenías personaje, complétalo en 🪪 Personajes → 🪞 Cambiar mi personaje.",
        "🕒 Tu Sim tiene su propio <b>reloj</b>, como un día real. Si pasas 5 minutos sin jugar se congela ❄️; "
        "al volver tocas ▶️ <b>Continuar</b>. La pausa es solo tuya: tu pareja sigue jugando.",
        "🔁 Al volver retomas justo donde lo dejaste (pantalla, sala y lo que hacías). Míralo con /conexion.",
        "💌 Nueva forma de invitar, más segura: la otra persona abre el bot y ve su <b>código personal</b>; "
        "tú escribes <code>invitar_CÓDIGO</code> y le llega la invitación para aceptarla.",
        "👀 En la sala ves el ánimo de tu pareja, qué está haciendo y la hora de su Sim.",
        "📢 Cada vez que el juego se actualice te llegará un aviso como este (también con /novedades).",
    ]),
    ("0.1", [
        "🧑‍🎨 Creador de personaje: nombre, cuerpo, piel, pelo, ojos, detalles y estilo.",
        "🏠 Sala para la pareja con estado en línea, ausente o fuera de línea.",
        "💬 Chat interno: texto, fotos, stickers y notas de voz.",
    ]),
]


def desde(version_anterior: str | None) -> list[tuple[str, list[str]]]:
    """Versiones publicadas después de `version_anterior` (la más nueva primero).

    Si no se sabe cuál fue la anterior, solo se devuelve la actual.
    """
    if version_anterior is None:
        return NOVEDADES[:1]
    nuevas = []
    for version, notas in NOVEDADES:
        if version == version_anterior:
            break
        nuevas.append((version, notas))
    return nuevas
