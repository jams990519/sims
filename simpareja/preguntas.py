"""Banco de preguntas de pareja según el estado de ánimo (actualización 2, parte 7). Lógica pura.

Hay temas buenos y temas difíciles, no solo discusiones. Cada pregunta tiene un tema, para
saber qué temas les gustan más.
"""

from __future__ import annotations

import random

TEMAS = {
    "recuerdos": "📷 Recuerdos", "risas": "😂 Risas", "gratitud": "🙏 Gratitud", "cariño": "💞 Cariño",
    "citas": "🌹 Citas", "planes": "🗓️ Planes", "metas": "🎯 Metas", "futuro": "🔮 Futuro",
    "sueños": "✨ Sueños", "apoyo": "🤝 Apoyo", "preocupaciones": "😟 Preocupaciones",
    "conflictos": "⚡ Conflictos", "cambios": "🔁 Cambios", "descanso": "😴 Descanso", "energía": "🔋 Energía",
}

BANCO: dict[str, tuple[tuple[str, str], ...]] = {
    "feliz": (
        ("recuerdos", "¿Cuál es tu recuerdo favorito de nosotros?"),
        ("risas", "¿Qué te hizo reír hoy?"),
        ("gratitud", "¿Qué es lo que más agradeces de esta semana?"),
        ("recuerdos", "¿Qué momento juntos repetirías mañana mismo?"),
        ("risas", "¿Cuál es la cosa más graciosa que nos ha pasado?"),
        ("cariño", "¿Qué es lo que más te gusta de cómo nos tratamos?"),
        ("planes", "¿Cómo celebramos un buen día como hoy?"),
        ("gratitud", "¿Qué pequeño detalle mío te alegra el día?"),
        ("recuerdos", "¿Qué foto nuestra guardarías para siempre?"),
        ("risas", "¿Qué canción te pone de buen humor y por qué?"),
    ),
    "coqueto": (
        ("cariño", "¿Qué fue lo primero que te gustó de mí?"),
        ("citas", "¿Cómo sería nuestra cita perfecta?"),
        ("cariño", "¿Qué es lo que más te atrae de mí?"),
        ("citas", "Si esta noche saliéramos, ¿a dónde me llevarías?"),
        ("recuerdos", "¿Cuándo supiste que te gustaba de verdad?"),
        ("cariño", "¿Qué detalle mío te derrite?"),
        ("citas", "¿Cena romántica en casa o fuera? ¿Qué comemos?"),
        ("cariño", "¿Qué te gustaría que te dijera más seguido?"),
        ("recuerdos", "¿Cuál fue nuestro beso más especial?"),
        ("cariño", "¿Qué ropa mía es tu favorita?"),
    ),
    "energia": (
        ("planes", "¿Qué plan hacemos este fin de semana?"),
        ("metas", "¿Qué meta tienes este mes?"),
        ("planes", "¿Qué actividad nueva te gustaría que probáramos juntos?"),
        ("metas", "¿Qué hábito quieres empezar y cómo te ayudo?"),
        ("planes", "Si mañana tuviéramos el día libre, ¿qué haríamos?"),
        ("metas", "¿Qué te gustaría aprender este año?"),
        ("planes", "¿A qué lugar cercano te gustaría ir que todavía no conocemos?"),
        ("metas", "¿Cuánto quieres que ahorremos este mes y para qué?"),
        ("planes", "¿Qué deporte o ejercicio podríamos hacer juntos?"),
        ("metas", "¿Qué pendiente de la casa terminamos juntos esta semana?"),
    ),
    "inspirado": (
        ("futuro", "¿Dónde te ves en cinco años?"),
        ("sueños", "¿Qué sueño quieres cumplir conmigo?"),
        ("sueños", "¿Cuál sería el viaje de nuestra vida?"),
        ("futuro", "¿Cómo te imaginas nuestra casa ideal?"),
        ("sueños", "Si el dinero no importara, ¿a qué te dedicarías?"),
        ("futuro", "¿Qué tradición te gustaría que tuviéramos como pareja?"),
        ("sueños", "¿Qué es algo que siempre quisiste hacer y aún no has hecho?"),
        ("futuro", "¿Qué te gustaría que dijeran de nosotros dentro de 20 años?"),
        ("sueños", "¿Qué proyecto podríamos crear juntos?"),
        ("futuro", "¿Qué cambiarías de tu vida para ser más feliz?"),
    ),
    "triste": (
        ("apoyo", "¿Qué necesitas de mí ahora mismo?"),
        ("preocupaciones", "¿Qué te preocupa últimamente?"),
        ("apoyo", "¿Qué puedo hacer hoy para que te sientas un poco mejor?"),
        ("apoyo", "¿Prefieres que hablemos o que solo te acompañe?"),
        ("preocupaciones", "¿Hay algo que te está costando y no me has contado?"),
        ("recuerdos", "¿Qué recuerdo bonito te ayuda en días así?"),
        ("apoyo", "¿Qué te reconforta cuando te sientes así?"),
        ("preocupaciones", "¿Qué pensamiento te quita la calma hoy?"),
        ("apoyo", "¿Qué comida o qué plan te levanta el ánimo?"),
        ("cariño", "¿Qué te gustaría escuchar de mí hoy?"),
    ),
    "enojado": (
        ("conflictos", "¿Qué te molestó y cómo lo arreglamos?"),
        ("cambios", "¿Qué puedo hacer distinto?"),
        ("conflictos", "¿Qué necesitas ahora: espacio o hablarlo ya?"),
        ("conflictos", "¿Hubo algo que dije o hice que te dolió?"),
        ("cambios", "¿Qué acuerdo podríamos hacer para que no se repita?"),
        ("conflictos", "¿Qué es lo que más te frustró esta semana?"),
        ("cambios", "¿Cómo prefieres que te diga las cosas cuando algo me molesta?"),
        ("conflictos", "Del 1 al 10, ¿qué tan grave fue lo que pasó? ¿Por qué?"),
        ("cambios", "¿Qué tarea de la casa te gustaría que repartiéramos distinto?"),
        ("cariño", "¿Qué te ayudaría a sentir que estamos en el mismo equipo?"),
    ),
    "cansado": (
        ("descanso", "¿Cómo te puedo ayudar a descansar?"),
        ("energía", "¿Qué te quitó la energía hoy?"),
        ("descanso", "¿Qué plan tranquilo te apetece para esta noche?"),
        ("descanso", "¿Qué tarea te quito de encima hoy?"),
        ("energía", "¿Estás durmiendo bien? ¿Qué te ayudaría?"),
        ("descanso", "¿Película, música o silencio? ¿Qué necesitas?"),
        ("energía", "¿Qué parte del día se te hace más pesada?"),
        ("descanso", "¿Qué te gustaría que hiciera por ti mañana temprano?"),
        ("energía", "¿Qué cambiarías de tu rutina para cansarte menos?"),
        ("cariño", "¿Un masaje, un abrazo o dormir temprano?"),
    ),
}


def elegir(animo: str, recientes: list[str], rng: random.Random) -> tuple[str, str]:
    """Una pregunta (tema, texto) para ese estado de ánimo, sin repetir las recientes si se puede."""
    banco = BANCO.get(animo) or BANCO["feliz"]
    nuevas = [p for p in banco if p[1] not in recientes]
    return rng.choice(nuevas or list(banco))
