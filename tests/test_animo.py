"""Actualización 2, parte 6: estado de ánimo con foto, frase, aviso, perfil y álbum."""

import pytest

from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import nuevo_juego, Reloj


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def pareja(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    return juego


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def test_animo_con_frase(pareja, reloj):
    res = pareja.boton(ANA, "", "animo:triste")
    assert "mándame una foto" in res.pantalla.texto and "animop" in datos(res.pantalla)
    assert "Triste" not in str(pareja.db.jugador(ANA).ap.get("animo"))  # todavía no se publicó
    res = pareja.texto(ANA, "", "hoy fue un día largo")
    assert not res.avisos  # la frase no se manda al chat
    assert "💬 Frase: «hoy fue un día largo»" in res.pantalla.texto
    reloj.avanzar(1)
    res = pareja.boton(ANA, "", "animop")
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert "ahora se siente: <b>🔵 😢 Triste</b>" in aviso.texto and "«hoy fue un día largo»" in aviso.texto
    assert aviso.foto is None and ("👀 Ver su perfil", "perfil") in aviso.botones[0]
    texto = pareja.boton(ADMIN, "", "perfil").pantalla.texto
    assert "🎭 🔵 😢 Triste · desde las 08:01" in texto and "💬 «hoy fue un día largo»" in texto
    assert "fotoan" not in str(pareja.boton(ADMIN, "", "perfil").pantalla.botones)


def test_animo_con_foto(pareja):
    pareja.boton(ANA, "", "animo:coqueto")
    res = pareja.media(ANA, "FOTO1", "pensando en ti")
    aviso = next(a for a in res.avisos if a.para == ADMIN)
    assert aviso.foto == "FOTO1" and "«pensando en ti»" in aviso.texto and not aviso.copiar
    assert "con tu foto" in res.pantalla.texto
    perfil = pareja.boton(ADMIN, "", "perfil").pantalla
    assert "📸 Con foto" in perfil.texto and f"fotoan:{ANA}" in datos(perfil)
    res = pareja.boton(ADMIN, "", f"fotoan:{ANA}")
    assert res.avisos[0].para == ADMIN and res.avisos[0].foto == "FOTO1"


def test_el_album_guarda_las_fotos_anteriores(pareja, reloj):
    for animo, foto in (("feliz", "F1"), ("cansado", "F2")):
        pareja.boton(ANA, "", f"animo:{animo}")
        pareja.media(ANA, foto)
        reloj.avanzar(2)
    pareja.boton(ANA, "", "animo:feliz")
    pareja.boton(ANA, "", "animop")  # sin foto: no entra al álbum
    pareja.boton(ADMIN, "", "continuar")
    res = pareja.boton(ADMIN, "", "album")
    assert "Ana</b>: 2 foto(s) de ánimo" in res.pantalla.texto
    assert datos(res.pantalla)[:2] == [f"fotoan:{ANA}:1", f"fotoan:{ANA}:0"]  # la más nueva primero
    assert pareja.boton(ADMIN, "", f"fotoan:{ANA}:0").avisos[0].foto == "F1"
    assert "album" in datos(pareja.boton(ADMIN, "", "mpar").pantalla)


def test_cancelar_o_irse_no_cambia_el_animo(pareja, reloj):
    antes = pareja.db.jugador(ANA).ap.get("animo")
    pareja.boton(ANA, "", "animo:enojado")
    pareja.boton(ANA, "", "animos")  # ❌ Cancelar
    assert pareja.db.jugador(ANA).ap.get("animo") == antes
    res = pareja.texto(ANA, "", "hola")
    assert any(a.para == ADMIN and a.chat for a in res.avisos)  # el texto vuelve a ser chat
    pareja.boton(ANA, "", "animo:enojado")
    reloj.avanzar(11)  # la foto se espera 10 min
    assert any(a.chat for a in pareja.texto(ANA, "", "sigo aquí").avisos)
    assert any(a.copiar for a in pareja.media(ANA, "FOTO").avisos)  # y la foto va al chat


def test_sin_pareja_tambien_se_puede(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    juego.boton(ADMIN, "", "animo:inspirado")
    res = juego.media(ADMIN, "F", "")
    assert not res.avisos and "¡Listo!" in res.pantalla.texto
    assert juego.db.jugador(ADMIN).ap["animo"] == "inspirado"
    assert "fotoan:1000:0" in datos(juego.boton(ADMIN, "", "album").pantalla)
