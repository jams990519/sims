"""Fotos estilo anime de las acciones: la descripción para la IA, la imagen liviana y cómo llegan por Telegram."""

import asyncio
import io
import json
import random

import pytest
from PIL import Image, ImageDraw

from simpareja import ilustraciones as IL
from simpareja import intimo_juego as I
from simpareja import mascota_juego as M
from simpareja import narracion as N
from simpareja import vida as V
from simpareja.bot import BotSimPareja
from simpareja.config import Config
from simpareja.db import DB
from simpareja.imagenes_ia import ImagenesIA
from simpareja.juego import Aviso, Juego
from test_bot import TelegramFalso
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, poner, Reloj

ELLA = dict(genero="mujer", etapa="joven", piel="clara", cuerpo="curvas", estatura="media", peinado="largo",
            pelo="rojizo", ojos="azules", estilo="casual", detalles=["pecas"])
EL = dict(genero="hombre", etapa="joven", piel="triguena", cuerpo="atletica", estatura="alta", peinado="corto",
          pelo="negro", ojos="marrones", estilo="urbano", detalles=[])


def test_momentos_del_dia():
    assert [N.momento(h) for h in (6, 10.9, 11, 17.4, 18, 19.6, 23, 3)] == [
        "manana", "manana", "tarde", "tarde", "atardecer", "noche", "noche", "noche"]


def test_cada_accion_trae_su_foto():
    con_foto = {k for k, etapas in N.ETAPAS.items() if any(e.escena for e in etapas)}
    sin_foto = {"trabajar", "cocinar", "abrazados"}  # el trabajo no; la cocina y el momento íntimo, aparte
    assert con_foto == set(V.ACCIONES) - sin_foto
    assert {"masaje", "besar", "pasear", "dormir"} <= con_foto
    for etapas in N.ETAPAS.values():
        assert all(e.escena.split(".")[0] in IL.ESCENAS for e in etapas if e.escena)
    assert len(IL.COLORES_MASCOTA) == len(M.ASPECTOS)
    assert all(f"intimo_{lugar}" in IL.ESCENAS for lugar in I.LUGARES)


def test_la_clave_de_cada_foto():
    ella, el = IL.figura(ELLA), IL.figura(EL)
    assert ella == "mujer,joven,clara,curvas,media,largo,rojizo,azules,casual,pecas"
    # la misma foto para los dos (en orden), y bajo techo la mañana y la tarde son la misma luz
    assert IL.clave("masaje", "manana", [ella, el]) == IL.clave("masaje", "tarde", [el, ella]) == \
        f"masaje:dia:{'|'.join(sorted([ella, el]))}"
    assert IL.clave("parque_banca", "manana", [ella]).startswith("parque_banca:manana:")  # afuera, las cuatro
    assert IL.clave("trabajar", "noche", [ella]) is None and IL.clave("masaje", "mediodia", [ella]) is None


def test_la_descripcion_lleva_los_rasgos_de_cada_uno():
    ella, el = IL.figura(ELLA), IL.figura(EL)
    texto = IL.prompt(IL.clave("parque_banca", "noche", [ella, el]))
    assert "anime TV series" in texto and "Studio Ghibli" in texto and "No text" in texto
    assert "a young woman in her twenties" in texto and "long bright red hair" in texto
    assert "bright blue eyes" in texto and "freckles" in texto and "curvy figure" in texto
    assert "a young man in his twenties" in texto and "short black hair" in texto and "streetwear" in texto
    assert "a couple sitting close together on a wooden bench" in texto and "crescent moon" in texto
    solo = IL.prompt(IL.clave("ducha", "manana", [ella]))
    assert "The character:" in solo and "wearing a fluffy white bath towel" in solo and "(2)" not in solo
    assert "their orange cat" in IL.prompt(IL.clave("jugar_mascota.gato.3", "tarde", [ella]))
    assert "cooking pasta with tomato sauce" in IL.prompt(IL.clave("cocina.pasta", "noche", [ella]))
    assert "shoulder massage" in IL.prompt(IL.clave("masaje", "noche", [ella, el]))
    beso = IL.prompt(IL.clave("besar", "noche", [ella, el]))
    assert "romance anime" in beso and "blushing" in beso and "sofa" in beso and "Ghibli" not in beso
    intima = IL.prompt(IL.clave("intimo_salon", "noche", [ella, el]))
    assert "sofa" in intima and "non-explicit" in intima and "fully clothed" in intima and "pajamas" not in intima
    assert "pajamas" in IL.prompt(IL.clave("intimo_cuarto", "noche", [ella, el]))
    for mala in ("parque_banca:noche", "nada:dia:x", "masaje:mediodia:x", "masaje:dia:"):
        with pytest.raises(ValueError):
            IL.prompt(mala)


def _imagen_de_la_ia(ancho=1536, alto=1024) -> bytes:
    """Una imagen con detalle (para que el JPEG no salga trivial), como las que devuelve la IA."""
    rng = random.Random(5)
    img = Image.effect_noise((ancho, alto), 60).convert("RGB")
    d = ImageDraw.Draw(img)
    for _ in range(300):
        x, y = rng.randrange(ancho), rng.randrange(alto)
        d.ellipse([x, y, x + 60, y + 60], fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    salida = io.BytesIO()
    img.save(salida, "PNG")
    return salida.getvalue()


def test_la_foto_queda_liviana_y_la_intima_pixelada_abajo():
    original = _imagen_de_la_ia()
    jpeg = IL.procesar(original, "masaje:dia:x")
    img = Image.open(io.BytesIO(jpeg))
    assert jpeg[:2] == b"\xff\xd8" and img.size == (768, 512) and len(jpeg) < 200_000
    assert Image.open(io.BytesIO(IL.procesar(_imagen_de_la_ia(1024, 1024), "masaje:dia:x"))).size == (768, 512)
    intima = Image.open(io.BytesIO(IL.procesar(original, "intimo_salon:noche:x|y"))).convert("L")
    normal = img.convert("L")

    def variacion(im, caja):  # cuánto cambia un píxel con el de al lado (el pixelado casi no cambia)
        zona = im.crop(caja)
        w, h = zona.size
        p = zona.load()
        return sum(abs(p[x, y] - p[x + 1, y]) for y in range(h) for x in range(w - 1)) / (w * h)

    abajo, arriba = (200, 380, 560, 500), (200, 20, 560, 200)
    assert variacion(intima, abajo) < variacion(normal, abajo) / 3  # abajo, cuadritos
    assert variacion(intima, arriba) > variacion(normal, arriba) / 2  # arriba (las caras), se ve


def test_de_noche_el_parque_es_de_noche():
    reloj = Reloj()
    reloj.avanzar(13 * 60)  # 9:00 pm
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    for uid in (ADMIN, ANA):
        poner(juego, uid, energia=100)
    res = juego.boton(ADMIN, "", "aj:parque")
    si = next(d for fila in next(a for a in res.avisos if a.para == ANA).botones for _, d in fila if d.endswith(":1"))
    juego.boton(ANA, "", si)  # 15 min × 0,7 ≈ 10 min
    luis, ana = (juego.db.jugador(u) for u in (ADMIN, ANA))
    figuras = "|".join(sorted([IL.figura(luis.ap), IL.figura(ana.ap)]))
    # al empezar ya se piden las cuatro fotos del paseo (la IA tarda un poco)
    assert f"parque_banca:noche:{figuras}" in juego.pedir_fotos() and juego.pedir_fotos() == []
    inicio = reloj()
    reloj.t = inicio + 7.5 * 60  # la banca
    avisos = {a.para: a for a in juego.tick().avisos if a.silencio}
    assert avisos[ADMIN].foto == avisos[ANA].foto == f"ilus:parque_banca:noche:{figuras}"  # la misma foto
    assert "bajo la farola y conversan mirando las estrellas" in avisos[ADMIN].texto
    juego.boton(ANA, "", "fotos")  # Ana prefiere sin fotos (gasta menos datos)
    assert "Con fotos estilo anime (gastan algo más de datos): <b>No</b>" in juego.boton(ANA, "", "ajustes").pantalla.texto
    reloj.t = inicio + 9.5 * 60
    avisos = {a.para: a for a in juego.tick().avisos if a.silencio}
    assert avisos[ANA].foto is None and avisos[ADMIN].foto.startswith("ilus:parque_regreso:noche:")


def test_la_foto_del_momento_intimo_segun_el_lugar():
    from test_intimo import LLENO

    juego = nuevo_juego(Reloj())
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    for uid, ap in ((ADMIN, EL), (ANA, ELLA)):
        poner(juego, uid, **LLENO)
        j = juego.db.jugador(uid)
        j.apariencia = json.dumps(ap)
        juego.db.guardar_jugador(j)
    juego.pedir_fotos()
    juego.boton(ADMIN, "", "intp:salon:romantico")
    juego.boton(ANA, "", "intsi")
    clave = IL.clave("intimo_salon", N.momento(juego._hora_local(juego.db.jugador(ANA))), [IL.figura(EL), IL.figura(ELLA)])
    assert juego.pedir_fotos() == [clave]  # se pide en cuanto empiezan
    for opcion in ("velas", "abrazo", "ternura"):
        juego.boton(ADMIN, "", f"into:{opcion}")
        res = juego.boton(ANA, "", f"into:{opcion}")
    fotos = {a.para: a for a in res.avisos if a.foto}
    assert set(fotos) == {ADMIN, ANA} and all(a.foto == f"ilus:{clave}" and a.solo_foto for a in fotos.values())
    assert "🛋️ en el sofá" in fotos[ANA].texto


# --- el bot ---------------------------------------------------------------------------------------

class IAFalsa:
    def __init__(self):
        self.pedidas = []

    async def __call__(self, descripcion: str) -> bytes:
        self.pedidas.append(descripcion)
        await asyncio.sleep(0)
        return _imagen_de_la_ia(300, 200)


def _bot(tmp_path, ia=None, por_dia=20):
    tg = TelegramFalso()
    cfg = Config(token="123:ABC", admins=frozenset({ADMIN}))
    juego = Juego(DB(":memory:"), cfg, rng=random.Random(3))
    imagenes = ImagenesIA(juego.db, tmp_path / "imagenes", por_dia, ia)
    bot = BotSimPareja(juego, cfg, imagenes)
    return tg, juego, bot, bot.construir(peticiones=tg)


def test_la_ia_hace_la_foto_una_vez_y_despues_se_reusa(tmp_path):
    clave = IL.clave("parque_banca", "noche", [IL.figura(EL), IL.figura(ELLA)])

    async def probar():
        ia = IAFalsa()
        tg, juego, bot, app = _bot(tmp_path, ia)
        await app.initialize()
        aviso = Aviso(ADMIN, "🪑 Se sientan en una banca…", foto=f"ilus:{clave}", silencio=True)
        assert await bot._enviar_aviso(app.bot, aviso, None)
        # todavía no estaba: el texto sale ya y la foto llega sola cuando la IA termina
        assert [m for m, _ in tg.llamadas if m in ("sendMessage", "sendPhoto")] == ["sendMessage"]
        await asyncio.gather(*bot._en_curso)
        foto = tg.enviados("sendPhoto", ADMIN)[-1]
        assert foto["caption"] == "📸 La foto de este momento" and foto["disable_notification"]
        assert juego.db.meta(f"ilusid:{clave}") and bot.imagenes.ruta(clave).is_file()
        assert "long bright red hair" in ia.pedidas[0]
        # la próxima vez (también para Ana) va directo con la foto, sin pedirla otra vez
        assert await bot._enviar_aviso(app.bot, Aviso(ANA, "🪑 Otra vez…", foto=f"ilus:{clave}"), None)
        foto = tg.enviados("sendPhoto", ANA)[-1]
        assert foto["photo"] == juego.db.meta(f"ilusid:{clave}") and foto["caption"] == "🪑 Otra vez…"
        assert len(ia.pedidas) == 1 and not tg.enviados("sendMessage", ANA)
        await app.shutdown()

    asyncio.run(probar())


def test_se_piden_al_empezar_la_accion_y_hay_un_tope_por_dia(tmp_path):
    async def probar():
        ia = IAFalsa()
        tg, juego, bot, app = _bot(tmp_path, ia, por_dia=2)
        await app.initialize()
        juego.por_dibujar += [IL.clave(e, "noche", [IL.figura(ELLA)]) for e in ("masaje", "dormir", "tele")]
        await bot._aplicar(None, type("Ctx", (), {"bot": app.bot})(), juego.tick())
        await asyncio.gather(*bot.imagenes.tareas.values())
        assert len(ia.pedidas) == 2  # la tercera, mañana (va solo con texto)
        assert json.loads(juego.db.meta("imagenes_dia"))["n"] == 2
        tele = IL.clave("tele", "noche", [IL.figura(ELLA)])
        assert await bot._enviar_aviso(app.bot, Aviso(ADMIN, "📺 Enciendes la tele…", foto=f"ilus:{tele}"), None)
        assert tg.enviados("sendMessage", ADMIN)[-1]["text"] == "📺 Enciendes la tele…" and not bot._en_curso
        await app.shutdown()

    asyncio.run(probar())


def test_sin_clave_de_la_ia_va_solo_el_texto(tmp_path):
    async def probar():
        tg, juego, bot, app = _bot(tmp_path)
        await app.initialize()
        clave = IL.clave("masaje", "noche", [IL.figura(EL), IL.figura(ELLA)])
        assert await bot._enviar_aviso(app.bot, Aviso(ADMIN, "💆 Aceite tibio…", foto=f"ilus:{clave}"), None)
        assert await bot._enviar_aviso(app.bot, Aviso(ADMIN, "📸 Su momento", foto=f"ilus:{clave}",
                                                      solo_foto=True), None)
        assert [d["text"] for m, d in tg.llamadas if m == "sendMessage"] == ["💆 Aceite tibio…"]
        assert not tg.enviados("sendPhoto", ADMIN) and not bot._en_curso
        await app.shutdown()

    asyncio.run(probar())


def test_la_foto_intima_llega_tapada(tmp_path):
    async def probar():
        tg, juego, bot, app = _bot(tmp_path, IAFalsa())
        await app.initialize()
        clave = IL.clave("intimo_cuarto", "noche", [IL.figura(EL), IL.figura(ELLA)])
        aviso = Aviso(ADMIN, "📸 Su momento 🛏️ en la cama. 💞", foto=f"ilus:{clave}", silencio=True, solo_foto=True)
        assert await bot._enviar_aviso(app.bot, aviso, None)
        assert not tg.enviados("sendMessage", ADMIN)  # solo la foto, cuando esté
        await asyncio.gather(*bot._en_curso)
        foto = tg.enviados("sendPhoto", ADMIN)[-1]
        assert foto["caption"] == "📸 Su momento 🛏️ en la cama. 💞" and foto["has_spoiler"]
        await app.shutdown()

    asyncio.run(probar())


def test_asi_se_le_pide_la_foto_a_openai(monkeypatch):
    import base64

    import httpx

    from simpareja import imagenes_ia as IA

    pedidos = []

    def responder(peticion):
        pedidos.append((peticion.headers["Authorization"], json.loads(peticion.content)))
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"IMAGEN").decode()}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(responder), **kw))
    assert asyncio.run(IA.generador_openai("sk-prueba", "gpt-image-2", "medium")("Una escena")) == b"IMAGEN"
    clave, cuerpo = pedidos[0]
    assert clave == "Bearer sk-prueba"
    assert cuerpo == {"model": "gpt-image-2", "prompt": "Una escena", "n": 1, "size": "1536x1024",
                      "quality": "medium", "output_format": "jpeg"}
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"message": "rechazada"}})), **kw))
    with pytest.raises(RuntimeError, match="400"):
        asyncio.run(IA.generador_openai("sk-prueba", "gpt-image-2", "medium")("Otra"))


def test_si_la_ia_rechaza_una_escena_no_insiste(tmp_path):
    async def probar():
        intentos = []

        async def rechaza(descripcion):
            intentos.append(descripcion)
            raise RuntimeError("OpenAI respondió 400: rechazada")

        tg, juego, bot, app = _bot(tmp_path, rechaza)
        await app.initialize()
        clave = IL.clave("ducha", "noche", [IL.figura(ELLA)])
        for _ in range(2):
            assert await bot._enviar_aviso(app.bot, Aviso(ADMIN, "🚿 Agua caliente…", foto=f"ilus:{clave}"), None)
            await asyncio.gather(*bot._en_curso)
        assert len(intentos) == 1 and len(tg.enviados("sendMessage", ADMIN)) == 2  # el texto llega igual
        assert not tg.enviados("sendPhoto", ADMIN)
        await app.shutdown()

    asyncio.run(probar())
