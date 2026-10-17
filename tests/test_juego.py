import random

import pytest

from simpareja import apariencia as A
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Juego, normalizar_codigo

ADMIN = 1000
ANA = 2000
LUIS = 3000
EXTRA = 4000


class Reloj:
    def __init__(self):
        self.t = 1_700_000_000.0

    def __call__(self):
        return self.t

    def avanzar(self, minutos):
        self.t += minutos * 60


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def juego(reloj):
    cfg = Config(token="x", admins=frozenset({ADMIN}))
    return Juego(DB(":memory:"), cfg, reloj=reloj, rng=random.Random(7))


def botones(pantalla):
    return [dato for fila in pantalla.botones for _, dato in fila]


def crear_personaje(juego, uid, nombre):
    """Recorre el creador eligiendo la primera opción de cada paso."""
    res = juego.texto(uid, "tg", nombre)
    assert juego.db.jugador(uid).estado == "creando"
    for _ in range(20):
        datos = botones(res.pantalla)
        if "apok" in datos:
            break
        if "apdl" in datos:
            res = juego.boton(uid, "tg", "apd:lentes")
            res = juego.boton(uid, "tg", "apdl")
        else:
            res = juego.boton(uid, "tg", datos[0])
    return juego.boton(uid, "tg", "apok")


def invitar(juego, uid, tipo="pareja"):
    res = juego.boton(uid, "tg", f"inv:{tipo}")
    codigo = res.pantalla.texto.split("?start=")[1].split()[0]
    return codigo


def admin_listo(juego):
    juego.inicio(ADMIN, "Admin", None)
    return crear_personaje(juego, ADMIN, "Luis")


# --- entrada solo por invitación -------------------------------------------

def test_sin_invitacion_no_se_puede_entrar(juego):
    res = juego.inicio(ANA, "Ana", None)
    assert "solo por invitación" in res.pantalla.texto
    assert str(ANA) in res.pantalla.texto
    assert juego.db.jugador(ANA) is None


def test_admin_entra_sin_invitacion_y_elige_jugar_o_invitar(juego):
    res = admin_listo(juego)
    assert "Personaje creado" in res.pantalla.texto
    assert botones(res.pantalla) == ["sala", "invitar"]
    j = juego.db.jugador(ADMIN)
    assert j.estado == "activo" and j.sala_id is not None
    assert A.completa(j.ap)


def test_jugar_sin_compania(juego):
    admin_listo(juego)
    res = juego.boton(ADMIN, "Admin", "sala")
    assert res.pantalla.es_sala
    assert "sin compañía" in res.pantalla.texto


def test_invitacion_de_pareja_entra_a_la_misma_sala(juego):
    admin_listo(juego)
    codigo = invitar(juego, ADMIN)
    res = juego.inicio(ANA, "Ana", codigo)
    assert "¿Cómo se llamará?" in res.pantalla.texto
    assert "Luis" in res.pantalla.texto
    assert any(a.para == ADMIN and "abrió tu invitación" in a.texto for a in res.avisos)

    res = crear_personaje(juego, ANA, "Ana")
    assert "Entraste a la sala" in res.pantalla.texto
    assert any(a.para == ADMIN and "entró a tu sala" in a.texto for a in res.avisos)
    assert juego.db.jugador(ANA).sala_id == juego.db.jugador(ADMIN).sala_id
    sala = juego.boton(ANA, "Ana", "sala").pantalla.texto
    assert "Sala de Luis y Ana" in sala


def test_enlace_sirve_una_sola_vez(juego):
    admin_listo(juego)
    codigo = invitar(juego, ADMIN, "amigo")
    assert "vence en 7 días" in juego.boton(ADMIN, "", f"ver:{codigo}").pantalla.texto
    juego.inicio(ANA, "Ana", codigo)
    res = juego.inicio(LUIS, "Luis", codigo)
    assert "no es válido" in res.pantalla.texto
    assert juego.db.jugador(LUIS) is None


def test_codigo_escrito_a_mano(juego):
    admin_listo(juego)
    codigo = invitar(juego, ADMIN, "amigo")
    escrito = f"{codigo[:4].lower()} {codigo[4:].lower()}"
    assert normalizar_codigo(escrito) == codigo
    res = juego.texto(ANA, "Ana", escrito)
    assert "¿Cómo se llamará?" in res.pantalla.texto


def test_invitacion_a_amigo_tiene_sala_propia(juego):
    admin_listo(juego)
    codigo = invitar(juego, ADMIN, "amigo")
    juego.inicio(ANA, "Ana", codigo)
    res = crear_personaje(juego, ANA, "Ana")
    assert juego.db.jugador(ANA).sala_id != juego.db.jugador(ADMIN).sala_id
    assert any(a.para == ADMIN and "aceptó tu invitación" in a.texto for a in res.avisos)


def test_sala_llena_no_ofrece_invitar_pareja(juego):
    admin_listo(juego)
    juego.inicio(ANA, "Ana", invitar(juego, ADMIN))
    crear_personaje(juego, ANA, "Ana")
    res = juego.boton(ADMIN, "Admin", "invitar")
    assert "inv:pareja" not in botones(res.pantalla)
    res = juego.boton(ADMIN, "Admin", "inv:pareja")
    assert res.alerta == "Tu sala ya está completa."


def test_segunda_invitacion_de_pareja_reutiliza_la_pendiente(juego):
    admin_listo(juego)
    primera = invitar(juego, ADMIN)
    segunda = invitar(juego, ADMIN)
    assert primera == segunda


def test_invitacion_vencida_y_anulada(juego, reloj):
    admin_listo(juego)
    vieja = invitar(juego, ADMIN, "amigo")
    reloj.avanzar(8 * 24 * 60)
    assert "no es válido" in juego.inicio(ANA, "Ana", vieja).pantalla.texto
    nueva = invitar(juego, ADMIN, "amigo")
    res = juego.boton(ADMIN, "Admin", f"anular:{nueva}")
    assert res.alerta == "🚫 Invitación anulada"
    assert "no es válido" in juego.inicio(ANA, "Ana", nueva).pantalla.texto


def test_limite_de_intentos_con_codigos_falsos(juego):
    for _ in range(5):
        juego.texto(ANA, "Ana", "ZZZZZZZZ")
    res = juego.texto(ANA, "Ana", "ZZZZZZZZ")
    assert "Demasiados intentos" in res.pantalla.texto


# --- creación del personaje ---------------------------------------------------

def test_nombre_invalido(juego):
    juego.inicio(ADMIN, "Admin", None)
    res = juego.texto(ADMIN, "Admin", "1")
    assert "no me sirve" in res.pantalla.texto
    assert juego.db.jugador(ADMIN).estado == "nombrando"


def test_creador_paso_a_paso(juego):
    juego.inicio(ADMIN, "Admin", None)
    res = juego.texto(ADMIN, "Admin", "Luis")
    assert "Paso 1 de 10" in res.pantalla.texto and "género" in res.pantalla.texto
    res = juego.boton(ADMIN, "", "ap:genero:hombre")
    assert "Paso 2" in res.pantalla.texto
    res = juego.boton(ADMIN, "", "ape:genero")  # atrás
    assert "Paso 1" in res.pantalla.texto
    for dato in ["ap:genero:mujer", "ap:etapa:joven", "ap:piel:morena", "ap:cuerpo:atletica",
                 "ap:estatura:media", "ap:peinado:rizado", "ap:pelo:castano_oscuro", "ap:ojos:verdes"]:
        res = juego.boton(ADMIN, "", dato)
    assert "Detalles" in res.pantalla.texto
    res = juego.boton(ADMIN, "", "apd:lentes")
    assert "✅ 👓 Lentes" in [t for fila in res.pantalla.botones for t, _ in fila]
    juego.boton(ADMIN, "", "apd:pecas")
    res = juego.boton(ADMIN, "", "apdl")
    res = juego.boton(ADMIN, "", "ap:estilo:deportivo")
    assert "Ficha de Luis" in res.pantalla.texto
    assert (
        "Luis es una mujer joven de complexión atlética y estatura media. "
        "Tiene la piel morena y ojos verdes. Lleva el pelo rizado de color castaño oscuro. "
        "Además, usa lentes y tiene pecas. Viste con estilo deportivo."
    ) in res.pantalla.texto
    # mientras se crea, los demás botones no funcionan
    assert juego.boton(ADMIN, "", "invitar").alerta
    res = juego.boton(ADMIN, "", "apok")
    assert juego.db.jugador(ADMIN).ap["detalles"] == ["lentes", "pecas"]


def test_sin_pelo_salta_el_color(juego):
    juego.inicio(ADMIN, "Admin", None)
    juego.texto(ADMIN, "Admin", "Luis")
    for dato in ["ap:genero:hombre", "ap:etapa:adulta", "ap:piel:clara", "ap:cuerpo:robusta",
                 "ap:estatura:alta", "ap:peinado:sin"]:
        res = juego.boton(ADMIN, "", dato)
    assert "Paso 7 de 9" in res.pantalla.texto and "ojos" in res.pantalla.texto
    for dato in ["ap:ojos:azules", "apdl", "ap:estilo:clasico"]:
        res = juego.boton(ADMIN, "", dato)
    assert "Tiene la piel clara y ojos azules. No tiene pelo." in res.pantalla.texto
    assert "Color de pelo" not in res.pantalla.texto


def test_editar_apariencia_y_cancelar(juego):
    admin_listo(juego)
    antes = juego.db.jugador(ADMIN).apariencia
    juego.boton(ADMIN, "", "apedit")
    juego.boton(ADMIN, "", "ap:genero:nobinario")
    res = juego.boton(ADMIN, "", "apx")
    assert juego.db.jugador(ADMIN).apariencia == antes
    assert "Personajes de la sala" in res.pantalla.texto
    juego.boton(ADMIN, "", "apedit")
    juego.boton(ADMIN, "", "ap:genero:nobinario")
    res = juego.boton(ADMIN, "", "apok")
    assert res.alerta == "✅ Apariencia guardada"
    assert juego.db.jugador(ADMIN).ap["genero"] == "nobinario"


def test_avatar_en_emoji():
    assert A.avatar({"genero": "mujer", "piel": "morena", "peinado": "rizado"}) == "👩🏾‍🦱"
    assert A.avatar({"genero": "hombre", "piel": "clara", "peinado": "corto", "pelo": "rubio"}) == "👱🏼‍♂️"
    assert A.avatar({"genero": "mujer", "etapa": "mayor", "piel": "oscura"}) == "👵🏿"


def test_todo_al_azar_siempre_completo():
    rng = random.Random(1)
    for _ in range(200):
        assert A.completa(A.todo_al_azar(rng))


# --- chat interno ---------------------------------------------------------------

@pytest.fixture
def pareja(juego):
    admin_listo(juego)
    juego.inicio(ANA, "Ana", invitar(juego, ADMIN))
    crear_personaje(juego, ANA, "Ana")
    return juego


def test_chat_le_llega_a_la_pareja(pareja):
    res = pareja.texto(ANA, "Ana", "hola <amor> & más")
    assert len(res.avisos) == 1
    aviso = res.avisos[0]
    assert aviso.para == ADMIN and aviso.chat
    assert "<b>Ana</b>: hola &lt;amor&gt; &amp; más" in aviso.texto
    assert res.pantalla is None


def test_chat_sin_compania(juego):
    admin_listo(juego)
    res = juego.texto(ADMIN, "Admin", "¿hay alguien?")
    assert not res.avisos
    assert "nadie más" in res.pantalla.texto


def test_fotos_y_stickers_se_copian(pareja):
    res = pareja.media(ADMIN)
    assert res.avisos[0].para == ANA and res.avisos[0].copiar


# --- presencia ---------------------------------------------------------------------

def test_presencia_en_vivo(pareja, reloj):
    pareja.registrar_pantalla(ADMIN, 55, es_sala=True)
    texto = pareja.boton(ANA, "Ana", "sala").pantalla.texto
    assert "Luis</b> — 🟢 en línea" in texto

    reloj.avanzar(20)
    res = pareja.tick()
    assert [e.para for e in res.ediciones] == [ADMIN]
    assert "🟡 ausente" in res.ediciones[0].pantalla.texto

    reloj.avanzar(60)
    res = pareja.tick()
    assert "⚫ fuera de línea · visto hace 1 h" in res.ediciones[0].pantalla.texto
    assert not pareja.tick().ediciones  # sin cambios, no se edita nada


def test_salir_y_volver_avisa_a_la_pareja(pareja, reloj):
    pareja.registrar_pantalla(ADMIN, 55, es_sala=True)
    res = pareja.boton(ANA, "Ana", "salir")
    assert "fuera de línea" in res.pantalla.texto
    assert "Ana</b> — ⚫ fuera de línea" in res.ediciones[0].pantalla.texto

    reloj.avanzar(40)
    res = pareja.boton(ANA, "Ana", "sala")
    assert any(a.para == ADMIN and "entró a la sala" in a.texto for a in res.avisos)
    assert "Ana</b> — 🟢 en línea" in res.ediciones[0].pantalla.texto


def test_avisos_de_conexion_desactivables(pareja, reloj):
    pareja.boton(ADMIN, "Admin", "avisos")
    pareja.boton(ANA, "Ana", "salir")
    reloj.avanzar(40)
    res = pareja.boton(ANA, "Ana", "sala")
    assert not res.avisos


def test_renombrar(pareja):
    pareja.boton(ANA, "Ana", "renombrar")
    res = pareja.texto(ANA, "Ana", "Anita")
    assert "Anita" in res.pantalla.texto
    assert pareja.db.jugador(ANA).estado == "activo"
    assert pareja.texto(ANA, "Ana", "hola").avisos  # vuelve a chatear normal
