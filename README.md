# 💞 SimPareja: un Sims por Telegram

Un juego de texto tipo *Los Sims* para jugar **en pareja** por Telegram ([@sims000bot](https://t.me/sims000bot)).
Se entra **solo por invitación** y funciona en **cualquier país donde abra Telegram**, Cuba incluida.

## Qué hay hasta ahora (versión 0.17)

| | |
|---|---|
| 🔐 **Entrada solo por invitación** | Quien abre el bot sin estar invitado ve su **código personal**. Se lo pasa a alguien que ya juega, que escribe `invitar_CÓDIGO` y elige si entra como pareja (a su sala) o con sala propia. A la persona invitada le llega un aviso para **aceptar o rechazar**. Cada código solo sirve para su dueño. |
| 🧑‍🎨 **Creador de personaje** | **Aspecto**: género, edad, piel, forma del cuerpo, estatura, peinado, color de pelo, ojos, detalles y estilo. **Personalidad**: hasta 3 rasgos, una aspiración de vida y un estado de ánimo con su color. Botón 🎲 al azar en cada paso, ficha editable, textos en masculino, femenino o neutro y avatar en emoji (👩🏾‍🦱, 🧔🏽‍♂️, 👱🏼‍♀️…). |
| 🎮 **Menú** | 🏠 Casa · ⚡ Acciones · 📍 Lugares · 💼 Trabajo · 💕 Pareja · 👤 Estado · 💬 Chat, con ⬅️ Atrás en cada submenú. Cada acción termina en una ficha con efecto, tiempo y precio para confirmar (solo o juntos). El Sim está en una habitación y va solo a donde toca. Lo que aún no existe aparece como 🚧. |
| 🎮 **Jugar o invitar** | Al terminar el personaje eliges **Jugar** (también sin compañía, sin esperar a nadie) o **Invitar**. |
| 🧍 **Necesidades** | Hambre (−6/h), energía (máx. 100, sube a 130 con constancia), higiene (−4/h), diversión (−5/h) y social (−3/h), de 0 a 100, que cambian con el reloj del Sim. Con alguna en 0 se pone de mal humor; sin energía se duerme donde esté. |
| 🎬 **Acciones** | Comer (desayuno +30, almuerzo +45, cena +40 según la hora), cocinar, dormir (+12/h), siesta, ducha, bañarse juntos, dientes, tele, redes, parque, hablar, abrazar, besar, masaje, cita, limpiar una zona y lavar la ropa (la ropa sucia se acumula). Casi todas se pueden hacer **solo o juntos**: juntos terminan antes. |
| 💗 **Medidor de relación** | Cada quien tiene un medidor de 0 a 100 % (empieza en 50 %) de lo que siente por el otro. Lo sube o lo baja cuando quiere eligiendo el motivo (o escribiéndolo); la pareja recibe un aviso y queda un historial de los dos. |
| 🎯 **Retos semanales** | Cada lunes, un reto para hacer juntos (cocinar juntos 3 veces, una cita el fin de semana, 5 abrazos, limpiar juntos, comer juntos, responder preguntas, parque, tele…). Al cumplirlo ganan dinero ($100 a $200) o +5 en el medidor de los dos. |
| 🎂 **Aniversario y álbum** | Cada mes cumplen un mes más (desde que juegan juntos). Aviso tres días antes; planean juntos el día, el plan (cena en casa, restaurante, cine o parque) y el presupuesto; ese día, con los dos conectados, brindan y se dan un regalo: +10 en el medidor de los dos y un recuerdo. Si no se celebra, solo se pierde la recompensa. El 📸 álbum guarda aniversarios, citas, respuestas que gustaron y fotos de ánimo. |
| 🎲 **Eventos sorpresa** | Uno o dos por semana, al azar. Buenos: bono en el trabajo, súper a mitad de precio ese día, regalo que sube el ánimo. Malos: avería de la nevera o la ducha (se arregla o se deja así), resfriado (menos energía y sin trabajar uno o dos días), apagón de unas horas, gasto inesperado. De pareja: día de lluvia (sin salidas), visita familiar (limpiar y cocinar), antojo (si el otro prepara esa comida sube la relación) o una pregunta de pareja. `EVENTOS=0` los apaga. |
| 📝 **Notas en la nevera** | Un jugador deja un mensaje en la nevera y su pareja lo ve al entrar al juego (o al volver de la pausa); mientras no lo lea, el menú y la sala lo marcan. También se dejan desde el trabajo. |
| ❓ **Preguntas de pareja** | Según el color del ánimo aparecen preguntas (70, 10 por estado, de temas buenos y difíciles): al cambiar de ánimo o pidiendo una nueva. Los dos responden; el otro marca «me gustó» (sube su medidor y la respuesta va al álbum) o «no me gustó» (no baja nada solo: se ofrece hablarlo en el chat o bajar el medidor). Queda el registro de los temas que más gustan. |
| 🎭 **Ánimo con foto** | Al cambiar de ánimo se elige el color y, si se quiere, una foto y una frase corta. La pareja recibe un aviso con la foto; en el perfil ve el color, la frase, la hora y la foto, y las fotos anteriores quedan en el 📸 álbum. Las fotos usan el almacenamiento de Telegram (se guarda solo su `file_id`). |
| 🗺️ **Plano de la casa** | `/plano` dibuja la casa en texto monoespaciado (cuarto arriba a la izquierda, clóset y baño a la derecha, sala-cocina-comedor abajo; con cuarto extra si se mudan) y pone a cada Sim con su inicial donde está, con lo que hace y el tiempo que le falta. Se actualiza solo mientras está abierto. |
| 🏠 **Sala** | Muestra a cada quien con su avatar, su ánimo, si está 🟢 en línea (y qué hace), ❄️ en pausa o ⚫ fuera de línea, y la hora de su Sim. **Se actualiza sola.** |
| 🏡 **Casa y dinero** | Empiezan con **$3.000** entre los dos y **rentan** la casita (baño, clóset, cuarto y sala-cocina-comedor) por **$900 al mes** con **$900 de depósito**: les quedan $2.100. En 💰 Dinero está la **meta de ahorro «nuestra casa»** con lo que falta. **Mudanza** (aceptan los dos): con $3.900 ahorrados, a un apartamento grande de $1.300 al mes con cuarto extra (se devuelve el depósito y el camión cuesta $150). **Comprar** «nuestra casa» con $15.000 de entrada y $1.200 de hipoteca; remodelar solo en casa propia. Cada quien tiene su 👛 cartera y hay una 🏦 cuenta compartida. Facturas mensuales: renta o hipoteca, luz $90 y agua $40 (suben con el uso), internet $50 y gas $30; comida $3/$5/$4 por persona; gastos inesperados como eventos sorpresa; si no pagan, recargo del 10 % y corte del servicio. |
| 💼 **Trabajos** | 7 trabajos de la tabla del diseño, con 3 niveles y sueldo por hora ($10 a $26). Cada quien pone su **horario real** (días, hora de entrada y de 4 a 8 horas, como mucho 8 al día) y el sueldo es horas × pago por hora, en la cartera al terminar (menos $4 de transporte); gasta 8 de energía por hora. **Automático**: a su hora el Sim se va solo a trabajar, aunque el jugador no esté. **Tiempo juntos protegido**: si los dos están conectados nunca se les obliga; se les pregunta si van ahora o «cuando me desconecte» (el Sim trabaja sin el jugador y cobra igual). Si ese día no se repone el turno, no se cobra. Durante el turno el chat sigue abierto y hay acciones rápidas cada media hora (ver redes, mandar un abrazo). Ascensos a los 5 y 10 días trabajados sin necesidades en rojo; con mal humor no se trabaja; renunciar devuelve al nivel 1. |
| 🛒 **Súper y cocina** | Ingredientes del súper (ofertas el fin de semana) que van a una nevera y despensa compartidas. 6 recetas (2 desayunos, 2 almuerzos, 2 cenas) que se cocinan paso a paso en tiempo real: el bot avisa cuando un paso está listo y, si se pasan del margen, se quema. Juntos es más rápido. Lo cocinado se come gratis o se guarda en un táper para el trabajo (sin táper, el hambre baja más rápido trabajando). |
| 🕒 **Hora real y pausa** | Cada Sim vive con la **hora real de su jugador** (se elige en Mi horario o en ⚙️ Ajustes → Mi hora local). Si pasan **5 minutos sin ninguna acción**, tu Sim se congela ❄️ y deja de gastar necesidades; al volver tocas **▶️ Continuar**. Mientras hace algo largo (dormir, trabajar), sigue. La pausa es solo tuya. |
| 🔁 **Última conexión** | Se guarda **solo la última**: en qué pantalla estabas, qué hacías, en qué sala y cuándo entraste y saliste. Al volver retomas justo ahí (`/conexion` lo muestra). |
| 💬 **Chat interno** | Todo lo que escribas en el bot (texto, fotos, stickers, notas de voz) le llega a tu pareja con tu nombre y avatar. Chatear no descongela al Sim. |
| 📢 **Novedades** | Cada vez que se despliega una versión nueva, el bot avisa a todos los jugadores de lo que cambió (`/novedades`). |

**Actualización 2 (en curso, manda sobre lo anterior):** 1. ✅ Menús y submenús · 2. ✅ Horario de trabajo real y automático (máx. 8 h) · 3. ✅ Casa en renta · 4. ✅ Plano en texto · 5. ✅ Necesidad social · 6. ✅ Ánimo con foto · 7. ✅ Preguntas de pareja · 8. ✅ Notas en la nevera · 9. ✅ Eventos sorpresa · 10. ✅ Aniversario y álbum · 11. ✅ Retos semanales · 12. Hitos · 13. Objetos y tiendas · 14. Mascota

**Primer diseño (una parte cada vez, cada una se sube sola):**
1. ✅ Crear el personaje · 2. ✅ Sala y chat interno · 3. ✅ Reloj individual y pausa · 4. ✅ Necesidades y acciones básicas
5. ✅ Casa, dinero y gastos · 6. ✅ Trabajos y días de la semana · 7. ✅ Súper y minijuego de cocina · 8. ✅ Medidor de relación
9. Influencer y ayuda de la pareja · 10. Estudios · 11. Lugares y mejoras de la casa

### ¿Por qué funciona en cualquier país?
- Quien juega **solo necesita Telegram**: no hay pagos, ni tarjetas, ni correo, ni apps aparte.
- Es **solo texto**: los menús se editan en el mismo mensaje y no se cargan imágenes, así gasta muy pocos datos (importante con los datos de ETECSA).
- Para invitar basta pasarse un código de 6 letras por WhatsApp, SMS o en persona.
- Lo único que necesita conexión con Telegram es el **servidor**. Si lo pones en un país donde Telegram está bloqueado, usa `TELEGRAM_PROXY`.

### Sobre el estado "en línea"
Telegram **no deja que un bot vea si alguien tiene la app abierta**. Por eso "en línea" significa *"usó el juego en los últimos 5 minutos"*. Después aparece ❄️ en pausa y, a la hora, ⚫ fuera de línea con "visto hace…" (`PAUSA_MIN`, `EN_LINEA_MIN` y `AUSENTE_MIN`). Con **🚪 Salir** apareces fuera de línea al instante.

### Publicar un parche
1. Sube `VERSION` en `simpareja/novedades.py` y añade sus notas al principio de `NOVEDADES`.
2. Fusiona en `main`: Railway lo despliega solo y, al arrancar, el bot envía las notas a todos los jugadores (una sola vez por versión).

## Cómo ponerlo en marcha

### 1. El bot
Ya existe: **@sims000bot**. Necesitas su **token**, que te dio @BotFather (si lo perdiste: @BotFather → `/mybots` → sims000bot → *API Token*). No lo publiques en ningún sitio: quien lo tenga controla el bot.

### 2. Configurar
```bash
cp .env.example .env
# Edita .env y pon BOT_TOKEN=... y ADMIN_IDS=tu_id
```
Los IDs de `ADMIN_IDS` entran sin invitación. Si lo dejas vacío, **la primera persona que abra el bot** (cuando aún no hay jugadores) entra como administradora; desde ahí invita a los demás. Tu ID aparece en ⚙️ Ajustes.

### 3a. Con Docker (recomendado en un servidor)
```bash
docker build -t simpareja .
docker run -d --name simpareja --restart unless-stopped \
  --env-file .env -v simpareja-datos:/app/datos simpareja
```

### 3b. En Railway
1. **New Project → Deploy from GitHub repo → `jams990519/sims`**. Railway detecta el `Dockerfile` solo.
2. En el servicio, pestaña **Variables**: añade `BOT_TOKEN` y `ADMIN_IDS` (y si quieres, las demás de `.env.example`).
3. Añade un **Volume** al servicio con *mount path* `/app/datos`. Sin él, las partidas se borran en cada despliegue.
4. Deja **una sola réplica**: si corren dos copias del bot a la vez, Telegram da error `Conflict`.

No hace falta generar un dominio público: el bot no recibe visitas web.

### 3c. Sin Docker (Python 3.10 o más nuevo)
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m simpareja
```

El bot usa *long polling*: **no necesita dominio, HTTPS ni abrir puertos**. Sirve cualquier VPS, una PC encendida o un servicio tipo Railway/Render/Fly. La partida se guarda en un archivo SQLite (`datos/simpareja.db`), que basta con copiar para respaldar.

## Desarrollo
```bash
pip install -r requirements-dev.txt
pytest
```

```
simpareja/
├── personaje.py    # creador de personaje: aspecto, personalidad, ánimo, avatar y descripción
├── juego.py        # lógica: invitaciones, creador, sala, presencia, reloj y chat (sin Telegram)
├── vida.py         # necesidades, acciones y calendario (lógica pura)
├── vida_juego.py   # pantallas de Mi Sim, acciones en pareja y avisos
├── dinero.py       # casas, renta, facturas, precios e imprevistos (lógica pura)
├── dinero_juego.py # pantallas de dinero, facturas, casa y mudanza; cobros de cada mes
├── trabajo.py      # trabajos, horarios y ascensos (lógica pura)
├── trabajo_juego.py # horario real, turnos automáticos y flexibles, sueldos
├── cocina.py       # ingredientes, recetas y tiempos (lógica pura)
├── cocina_juego.py # súper, nevera, minijuego de cocina y táper
├── animo_juego.py  # estado de ánimo con foto y frase, perfil y álbum
├── relacion_juego.py # medidor de relación y su historial
├── preguntas.py    # banco de preguntas por estado de ánimo (lógica pura)
├── preguntas_juego.py # preguntas de pareja: responder, valorar, temas
├── notas_juego.py  # notas en la nevera
├── eventos.py      # eventos sorpresa: cuáles, cada cuánto (lógica pura)
├── eventos_juego.py # eventos sorpresa dentro del juego
├── aniversario_juego.py # aniversario mensual, citas y recuerdos
├── retos_juego.py  # retos semanales de pareja
├── novedades.py    # notas de cada versión (se anuncian solas al desplegar)
├── menus.py        # menú principal, submenús y plano de la casa
├── plano.py        # dibujo del plano en texto (lógica pura)
├── bot.py          # adaptador de Telegram (python-telegram-bot)
├── db.py           # SQLite
├── config.py       # variables de entorno
└── __main__.py     # arranque
```
`juego.py` no sabe nada de Telegram: cada acción devuelve la pantalla que hay que mostrar, los avisos para otras personas y las salas que hay que actualizar. Por eso se puede probar entero sin conexión (`tests/`).
