"""Arranque: `python -m simpareja`."""

import logging
import sys

from telegram import Update

from .bot import BotSimPareja
from .config import Config
from .db import DB
from .juego import Juego


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
        stream=sys.stdout,  # Railway marca como error todo lo que sale por stderr
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = Config.desde_entorno()
    if not cfg.token:
        sys.exit("Falta BOT_TOKEN. Copia .env.example a .env y pon el token de @BotFather.")
    if not cfg.admins:
        logging.warning(
            "ADMIN_IDS está vacío: si todavía no hay jugadores, la primera persona que "
            "abra el bot entrará como administradora."
        )
    juego = Juego(DB(cfg.db_ruta), cfg)
    app = BotSimPareja(juego, cfg).construir()
    app.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])


if __name__ == "__main__":
    main()
