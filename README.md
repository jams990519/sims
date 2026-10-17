# 💞 SimPareja: un Sims por Telegram

Un juego de texto tipo *Los Sims* para jugar **en pareja** por Telegram ([@sims000bot](https://t.me/sims000bot)).
Se entra **solo por invitación** y funciona en **cualquier país donde abra Telegram**, Cuba incluida.

## Qué hay hasta ahora (versión 0.2)

| | |
|---|---|
| 🔐 **Entrada solo por invitación** | Quien abre el bot sin estar invitado ve su **código personal**. Se lo pasa a alguien que ya juega, que escribe `invitar_CÓDIGO` y elige si entra como pareja (a su sala) o con sala propia. A la persona invitada le llega un aviso para **aceptar o rechazar**. Cada código solo sirve para su dueño. |
| 🧑‍🎨 **Creador de personaje** | **Aspecto**: género, edad, piel, forma del cuerpo, estatura, peinado, color de pelo, ojos, detalles y estilo. **Personalidad**: hasta 3 rasgos, una aspiración de vida y un estado de ánimo con su color. Botón 🎲 al azar en cada paso, ficha editable, textos en masculino, femenino o neutro y avatar en emoji (👩🏾‍🦱, 🧔🏽‍♂️, 👱🏼‍♀️…). |
| 🎮 **Jugar o invitar** | Al terminar el personaje eliges **Jugar** (también sin compañía) o **Invitar**. |
| 🏠 **Sala** | Muestra a cada quien con su avatar, su ánimo, si está 🟢 en línea (y qué hace), ❄️ en pausa o ⚫ fuera de línea, y la hora de su Sim. **Se actualiza sola.** |
| 🕒 **Reloj propio** | Cada Sim tiene su reloj, que corre como un día real (empieza el Día 1 a las 08:00). Si pasas **5 minutos sin jugar**, tu Sim se congela ❄️ y su reloj se para; al volver tocas **▶️ Continuar**. La pausa es solo tuya: tu pareja sigue jugando. |
| 🔁 **Última conexión** | Se guarda **solo la última**: en qué pantalla estabas, qué hacías, en qué sala y cuándo entraste y saliste. Al volver retomas justo ahí (`/conexion` lo muestra). |
| 💬 **Chat interno** | Todo lo que escribas en el bot (texto, fotos, stickers, notas de voz) le llega a tu pareja con tu nombre y avatar. Chatear no descongela al Sim. |
| 📢 **Novedades** | Cada vez que se despliega una versión nueva, el bot avisa a todos los jugadores de lo que cambió (`/novedades`). |

**Próximas partes, una a una:** casa y dinero (3.000 para empezar, cartera de cada uno y cuenta compartida) → compras → acciones del día solos o juntos (tele, cocinar, bañarse, limpiar, lavar la ropa) → cocina como minijuego → trabajo automático por horas → medidor de relación.

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
├── apariencia.py   # opciones del creador de personaje, avatar en emoji y descripción
├── juego.py        # lógica: invitaciones, creador, sala, presencia y chat (sin Telegram)
├── bot.py          # adaptador de Telegram (python-telegram-bot)
├── db.py           # SQLite
├── config.py       # variables de entorno
└── __main__.py     # arranque
```
`juego.py` no sabe nada de Telegram: cada acción devuelve la pantalla que hay que mostrar, los avisos para otras personas y las salas que hay que actualizar. Por eso se puede probar entero sin conexión (`tests/`).
