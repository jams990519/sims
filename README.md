# 💞 SimPareja: un Sims por Telegram

Un juego de texto tipo *Los Sims* para jugar **en pareja** por Telegram ([@sims000bot](https://t.me/sims000bot)).
Se entra **solo por invitación** y funciona en **cualquier país donde abra Telegram**, Cuba incluida.

## Qué hay hasta ahora (fase 1)

| | |
|---|---|
| 🔐 **Entrada solo por invitación** | Cada enlace (`https://t.me/sims000bot?start=CÓDIGO`) sirve **una sola vez** y vence a los 7 días. Si el enlace no abre, se puede escribir el código a mano. Quien no tiene invitación ve un candado. |
| 🧑‍🎨 **Creador de personaje** | Nombre, género, edad, tono de piel, forma del cuerpo, estatura, peinado, color de pelo, ojos, detalles (lentes, pecas, barba, tatuajes…) y estilo de ropa. Botón 🎲 al azar en cada paso, ficha final editable y avatar en emoji (👩🏾‍🦱, 🧔🏽‍♂️, 👱🏼‍♀️…). |
| 🎮 **Jugar o invitar** | Al terminar el personaje eliges **Jugar** (puedes jugar sin compañía) o **Invitar jugador**. |
| 🏠 **Sala** | La invitación "💞 a mi pareja" mete a la otra persona en **tu sala**. La de "👋 otra persona" le da una sala propia. |
| 🟢 **En línea / ausente / fuera de línea** | La sala muestra el estado de cada quien y **se actualiza sola** cuando alguien entra o sale, aunque esté sin hacer nada. Además llega un aviso "🟢 Ana entró a la sala" (desactivable en Ajustes). |
| 💬 **Chat interno** | Todo lo que escribas en el bot (texto, fotos, stickers, notas de voz) le llega a tu pareja con tu nombre y avatar. |

**Próximamente:** necesidades (hambre, energía…), casa y muebles, trabajo, citas, noviazgo y boda.

### ¿Por qué funciona en cualquier país?
- Quien juega **solo necesita Telegram**: no hay pagos, ni tarjetas, ni correo, ni apps aparte.
- Es **solo texto**: los menús se editan en el mismo mensaje y no se cargan imágenes, así gasta muy pocos datos (importante con los datos de ETECSA).
- Las invitaciones se pueden mandar por WhatsApp, SMS o correo, y si el enlace falla se escribe el código.
- Lo único que necesita conexión con Telegram es el **servidor**. Si lo pones en un país donde Telegram está bloqueado, usa `TELEGRAM_PROXY`.

### Sobre el estado "en línea"
Telegram **no deja que un bot vea si alguien tiene la app abierta**. Por eso "en línea" significa *"usó el juego en los últimos 15 minutos"*. Después aparece 🟡 ausente y, a la hora, ⚫ fuera de línea con "visto hace…". Ambos tiempos se cambian con `EN_LINEA_MIN` y `AUSENTE_MIN`. Con el botón **🚪 Salir** apareces fuera de línea al instante.

## Cómo ponerlo en marcha

### 1. El bot
Ya existe: **@sims000bot**. Necesitas su **token**, que te dio @BotFather (si lo perdiste: @BotFather → `/mybots` → sims000bot → *API Token*). No lo publiques en ningún sitio: quien lo tenga controla el bot.

### 2. Configurar
```bash
cp .env.example .env
# Edita .env y pon BOT_TOKEN=... y ADMIN_IDS=tu_id
```
Para saber tu ID: arranca el bot una vez sin `ADMIN_IDS`, escríbele `/start` y te lo muestra. Ponlo en `ADMIN_IDS` y reinicia. El administrador entra sin invitación y desde ahí invita a los demás.

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
