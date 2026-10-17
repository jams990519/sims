"""Notas de cada actualización. Al arrancar una versión nueva, el bot las envía a todos los jugadores.

Para publicar un parche: sube VERSION y añade su entrada AL PRINCIPIO de NOVEDADES.
"""

VERSION = "0.9"

NOVEDADES: list[tuple[str, list[str]]] = [
    ("0.9", [
        "🔑 <b>Casa en renta</b>: ahora empiezan rentando la casita por $900 al mes, con un depósito de $900 "
        "(de los $3.000 les quedan $2.100). Si ya jugaban, les devolví los $600 de diferencia de la entrada.",
        "🎯 <b>Meta de ahorro</b>: en 💰 Dinero aparece «nuestra casa» con lo que falta para comprarla.",
        "🚚 <b>Mudanza</b> (🏠 Casa → Renta y mudanza): con $3.900 ahorrados pueden mudarse a un apartamento "
        "grande ($1.300 al mes) con un 🧸 cuarto extra. Les devuelven el depósito y aceptan los dos.",
        "🏠 <b>Comprar «nuestra casa»</b> con $15.000 de entrada: la hipoteca ($1.200) es parecida a la renta, "
        "pero la casa es suya.",
        "🔨 Remodelar solo se puede en casa propia; en la de renta solo se ponen muebles.",
    ]),
    ("0.8", [
        "🗓️ <b>Horario de trabajo real</b>: en 💼 Trabajo → Mi horario eliges los días, la hora de entrada y las "
        "horas (como mucho 8 al día). El sueldo es horas × pago por hora.",
        "🕒 Tu Sim vive con <b>tu hora real</b>: el bot te pregunta qué hora es donde estás (puedes cambiarla en "
        "⚙️ Ajustes → Mi hora local).",
        "🕗 <b>Trabajo automático</b>: a la hora de tu horario tu Sim se va solo a trabajar, aunque no estés "
        "conectado, y cobra al terminar.",
        "💞 <b>Tiempo juntos protegido</b>: si están conectados los dos a esa hora, nunca se les obliga. Te pregunto "
        "si vas ahora o «cuando me desconecte»: tu Sim trabaja sin ti en cuanto te vayas y cobra igual.",
        "⚠️ Si ese día no repones el turno, no cobras.",
        "💬 Mientras trabajas el chat sigue abierto y, cada media hora, hay acciones rápidas: 📱 ver redes en el "
        "descanso o 🤗 mandarle un abrazo a tu pareja.",
        "❄️ El reloj ya no se para: lo que se congela en la pausa son las necesidades de tu Sim.",
    ]),
    ("0.7", [
        "🎮 <b>Menú nuevo</b> (/menu): 🏠 Casa · ⚡ Acciones · 📍 Lugares · 💼 Trabajo · 💕 Pareja · 👤 Estado · 💬 Chat. "
        "Todos los submenús tienen ⬅️ Atrás.",
        "📋 Antes de cada acción ves una ficha con su efecto, su tiempo y su precio, y confirmas Sí o No "
        "(o «Sí, con tu pareja», que termina antes).",
        "🚶 Tu Sim está en una habitación (cuarto, baño, clóset o sala-cocina-comedor) y va solo a donde toque.",
        "📍 Lugares: súper, restaurante ($20, o $40 para dos), cine ($13, o $25 para dos), parque y gimnasio "
        "($30 al mes). Restaurante y cine salen más caros el fin de semana; salir juntos cuenta como cita.",
        "🛵 Pedir a domicilio (cuesta el doble y tarda 30 min) y «Comer lo que hay» (nevera o táper).",
        "💬 Más social: redes +5/h, tele +3/h, tele o redes juntos +15/h y hablar por teléfono +20.",
        "💼 Ir a trabajar pide confirmación (con o sin táper) y al terminar ves lo que gastaste. Nuevo: 📈 Mi carrera.",
    ]),
    ("0.6", [
        "🛒 <b>Súper</b> (/super): compren ingredientes que van a la 🧊 nevera y despensa compartidas. "
        "Los sábados y domingos hay ofertas.",
        "🍳 <b>Cocinar</b> (/cocina): 6 recetas (huevos revueltos, café con tostadas, arroz con pollo, pasta, "
        "sopa de verduras y sándwich) que se preparan paso a paso en tiempo real. Te aviso cuando cada paso "
        "está listo… ¡y si te pasas de tiempo, se quema! 🔥",
        "💞 Cocinar juntos es más rápido y cualquiera de los dos puede pasar al siguiente paso.",
        "🍽️ Comer lo cocinado es gratis; si no hay nada en la nevera, pueden comprar algo hecho.",
        "🥡 Guarda una porción en un táper para el trabajo. Sin táper, trabajando el hambre baja más rápido.",
    ]),
    ("0.5", [
        "💼 <b>¡Trabajos!</b> (/trabajo) Elige uno de 7: manicurista, estudio de fotografía, supermercado, "
        "reparto, cocina de restaurante, oficina o taller mecánico. Cada uno tiene 3 niveles y sueldo por hora.",
        "🕗 Es automático: decides cuántas horas trabajas (4, 6, 8 o 10) y cobras en tu 👛 cartera al terminar. "
        "Gasta 8 de energía por hora y $4 de transporte al día.",
        "🗓️ Horarios: de lunes a viernes, de lunes a sábado o rotativo (incluye fines de semana, con dos días "
        "libres entre semana).",
        "📈 Ascensos: 5 días trabajados para el nivel 2 y 10 más para el nivel 3, siempre que no vayas con "
        "necesidades en rojo. Con mal humor no se puede trabajar.",
        "🚪 Puedes renunciar, pero el siguiente trabajo empieza desde abajo.",
    ]),
    ("0.4", [
        "🏡 <b>¡Ya tienen casa!</b> Empezaron con $3.000 entre los dos y compraron la Casita "
        "(baño, clóset, un cuarto y una sala-cocina-comedor grande) con $1.500 de entrada y una hipoteca "
        "de $700 al mes. Mírala con /casa.",
        "💰 <b>Dinero</b> (/dinero): cada quien tiene su 👛 cartera y hay una 🏦 cuenta compartida para la "
        "casa y los gastos. Pueden pasar dinero de una a otra.",
        "📄 Facturas del mes: hipoteca $700, luz $90 y agua $40 (suben con el uso), internet $50 y gas $30. "
        "Se cobran solas cada 30 días; si no alcanza, hay un recargo del 10 % y se corta el servicio.",
        "🍽️ Comer cuesta: $3 el desayuno, $5 el almuerzo y $4 la cena por persona.",
        "🔧 Ojo con los imprevistos: averías y multas que llegan cuando menos lo esperan.",
        "➡️ Lo siguiente: los trabajos, para ganar dinero.",
    ]),
    ("0.3", [
        "🧍 <b>Mi Sim</b> (/sim): tu Sim ya tiene necesidades: 🍔 hambre, ⚡ energía, 🚿 higiene, 🎉 diversión "
        "y 💬 social. Bajan con su reloj; si alguna llega a 0 se pone de mal humor, y sin energía se duerme "
        "donde esté.",
        "🎬 Acciones: comer (desayuno, almuerzo o cena según la hora), cocinar, dormir, siesta, ducharse, "
        "bañarse juntos, lavarse los dientes, tele, redes, parque, hablar, abrazar, besar, masaje, cita, "
        "limpiar una zona y lavar la ropa.",
        "💞 Casi todo se puede hacer juntos: tu pareja recibe la propuesta y, si acepta, terminan antes.",
        "😴 Mientras tu Sim hace algo (por ejemplo dormir 8 horas), su reloj sigue aunque no estés; "
        "se congela 5 minutos después de terminar.",
        "💪 Constancia: 3 días seguidos de parque suben 5 la energía máxima (hasta 130).",
        "🗓️ El reloj muestra el día de la semana y los fines de semana.",
        "🎭 Nuevos estados de ánimo: 🟢 feliz, 🌸 coqueto, 🔵 triste, 🔴 enojado, 🟡 con energía, "
        "🔘 cansado y 🟣 inspirado. Elige el tuyo con /animo.",
        "🎮 Puedes jugar sin esperar a que tu pareja acepte la invitación.",
    ]),
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
