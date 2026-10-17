import random
import sqlite3

import pytest

from simpareja import novedades as N
from simpareja import personaje as P
from simpareja.config import Config
from simpareja.db import DB
from simpareja.juego import Juego

ADMIN = 1000
ANA = 2000
LUIS = 3000
EXTRA = 4000


INICIO = 1_704_110_400.0  # lunes 1 de enero de 2024, 08:00 en UTC−4 (la zona por defecto)


class Reloj:
    def __init__(self):
        self.t = INICIO

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


def datos(pantalla):
    return [dato for fila in pantalla.botones for _, dato in fila]


def etiquetas(pantalla):
    return [texto for fila in pantalla.botones for texto, _ in fila]


def crear_personaje(juego, uid, nombre):
    juego.texto(uid, "tg", nombre)
    assert juego.db.jugador(uid).estado == "creando"
    juego.boton(uid, "tg", "apr")
    return juego.boton(uid, "tg", "apok")


def admin_listo(juego):
    juego.inicio(ADMIN, "Admin", None)
    return crear_personaje(juego, ADMIN, "Luis")


def codigo_personal(juego, uid, nombre="Ana"):
    res = juego.inicio(uid, nombre, None)
    return res.pantalla.texto.split("invitar_")[1].split("<")[0]


def invitar(juego, de, para, tipo="pareja", nombre="Ana"):
    codigo = codigo_personal(juego, para, nombre)
    juego.texto(de, "tg", f"invitar_{codigo}")
    res = juego.boton(de, "tg", f"invc:{codigo}:{tipo}")
    return next(a for a in res.avisos if a.para == para)


def aceptar(juego, uid, aviso, nombre="Ana"):
    acepto = next(d for fila in aviso.botones for _, d in fila if d.startswith("acepto:"))
    return juego.boton(uid, nombre, acepto)


@pytest.fixture
def pareja(juego):
    admin_listo(juego)
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    return juego


# --- entrada solo por invitación ------------------------------------------------

def test_visitante_ve_su_codigo_personal(juego):
    admin_listo(juego)
    res = juego.inicio(ANA, "Ana", None)
    assert "solo por invitación" in res.pantalla.texto
    codigo = res.pantalla.texto.split("Tu código personal: <code>")[1][:6]
    assert f"invitar_{codigo}" in res.pantalla.texto
    assert juego.db.jugador(ANA) is None
    # siempre el mismo código para la misma persona
    assert codigo_personal(juego, ANA) == codigo


def test_primer_jugador_entra_si_no_hay_admins(reloj):
    juego = Juego(DB(":memory:"), Config(token="x"), reloj=reloj)
    assert "¿Cómo se llamará?" in juego.inicio(ANA, "Ana").pantalla.texto
    assert "solo por invitación" in juego.inicio(LUIS, "Luis").pantalla.texto


def test_invitar_con_codigo_a_la_pareja(juego):
    admin_listo(juego)
    codigo = codigo_personal(juego, ANA)
    res = juego.texto(ADMIN, "Admin", f"/invitar_{codigo.lower()}")
    assert "es de <b>Ana</b>" in res.pantalla.texto
    assert f"invc:{codigo}:pareja" in datos(res.pantalla)
    res = juego.boton(ADMIN, "Admin", f"invc:{codigo}:pareja")
    assert "Invitación enviada a Ana" in res.pantalla.texto
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "te invitó" in aviso.texto and "como pareja" in aviso.texto

    # Ana vuelve a abrir el bot y ve la invitación
    assert "¡Tienes una invitación!" in juego.inicio(ANA, "Ana").pantalla.texto
    res = aceptar(juego, ANA, aviso)
    assert "¿Cómo se llamará?" in res.pantalla.texto
    assert any(a.para == ADMIN and "aceptó tu invitación" in a.texto for a in res.avisos)

    juego.registrar_pantalla(ADMIN, 55, es_sala=True)
    res = crear_personaje(juego, ANA, "Ana")
    assert "Entraste a la sala" in res.pantalla.texto
    assert [e.para for e in res.ediciones] == [ADMIN]  # la sala abierta de Luis se redibuja
    assert juego.db.jugador(ANA).sala_id == juego.db.jugador(ADMIN).sala_id
    assert "Sala de Luis y Ana" in juego.boton(ANA, "Ana", "sala").pantalla.texto


def test_codigo_equivocado_y_quien_ya_juega(pareja):
    res = pareja.texto(ADMIN, "Admin", "invitar_ZZZZZZ")
    assert "No encontré el código" in res.pantalla.texto
    codigo = pareja.db.visitante(ANA).codigo
    assert "ya está jugando" in pareja.texto(ADMIN, "Admin", f"invitar_{codigo}").pantalla.texto


def test_la_invitacion_solo_sirve_a_su_duena(juego):
    admin_listo(juego)
    aviso = invitar(juego, ADMIN, ANA)
    juego.inicio(LUIS, "Luis")  # Luis es otro visitante
    res = aceptar(juego, LUIS, aviso, "Luis")
    assert res.alerta == "Esa invitación ya no está disponible."
    assert juego.db.jugador(LUIS) is None


def test_rechazar_invitacion(juego):
    admin_listo(juego)
    aviso = invitar(juego, ADMIN, ANA)
    rechazo = next(d for fila in aviso.botones for _, d in fila if d.startswith("rechazo:"))
    res = juego.boton(ANA, "Ana", rechazo)
    assert "rechazada" in res.pantalla.texto
    assert any(a.para == ADMIN and "no aceptó" in a.texto for a in res.avisos)
    assert aceptar(juego, ANA, aviso).alerta == "Esa invitación ya no está disponible."


def test_anular_invitacion(juego):
    admin_listo(juego)
    aviso = invitar(juego, ADMIN, ANA)
    codigo = next(d for fila in aviso.botones for _, d in fila if d.startswith("acepto:")).split(":")[1]
    res = juego.boton(ADMIN, "Admin", "invs")
    assert "esperando respuesta" in res.pantalla.texto
    res = juego.boton(ADMIN, "Admin", f"anular:{codigo}")
    assert res.alerta == "🚫 Invitación anulada"
    assert aceptar(juego, ANA, aviso).alerta == "Esa invitación ya no está disponible."


def test_sala_llena_solo_ofrece_sala_propia(pareja):
    codigo = codigo_personal(pareja, LUIS, "Luis")
    res = pareja.texto(ADMIN, "Admin", f"invitar_{codigo}")
    assert f"invc:{codigo}:pareja" not in datos(res.pantalla)
    assert pareja.boton(ADMIN, "Admin", f"invc:{codigo}:pareja").alerta == "Tu sala ya está completa."
    aceptar(pareja, LUIS, invitar(pareja, ADMIN, LUIS, "amigo", "Luis"), "Luis")
    crear_personaje(pareja, LUIS, "Pepe")
    assert pareja.db.jugador(LUIS).sala_id != pareja.db.jugador(ADMIN).sala_id


# --- creación del personaje -------------------------------------------------------

def test_creador_paso_a_paso_con_personalidad(juego):
    juego.inicio(ADMIN, "Admin", None)
    res = juego.texto(ADMIN, "Admin", "Luis")
    assert "Paso 1 de 13" in res.pantalla.texto
    for dato in ["ap:genero:mujer", "ap:etapa:joven", "ap:piel:morena", "ap:cuerpo:atletica",
                 "ap:estatura:media", "ap:peinado:rizado", "ap:pelo:castano_oscuro", "ap:ojos:verdes",
                 "apm:detalles:lentes", "apml:detalles", "ap:estilo:deportivo"]:
        res = juego.boton(ADMIN, "", dato)
    assert "Personalidad: 🧠 Rasgos" in res.pantalla.texto
    assert "💘 Romántica" in etiquetas(res.pantalla)  # en femenino porque es mujer
    assert juego.boton(ADMIN, "", "apml:rasgos").alerta == "Elige al menos 1."
    for r in ["romantico", "divertido", "ordenado"]:
        juego.boton(ADMIN, "", f"apm:rasgos:{r}")
    res = juego.boton(ADMIN, "", "apm:rasgos:gloton")
    assert res.alerta and "máximo 3" in res.alerta
    assert "✅ Listo (3/3)" in etiquetas(res.pantalla)
    juego.boton(ADMIN, "", "apml:rasgos")
    juego.boton(ADMIN, "", "ap:aspiracion:amor")
    res = juego.boton(ADMIN, "", "ap:animo:coqueto")
    assert "Ficha de Luis" in res.pantalla.texto
    assert "<b>Personalidad</b>" in res.pantalla.texto
    assert (
        "Es romántica, divertida y ordenada. Sueña con un amor para toda la vida. "
        "Ahora mismo se siente coqueta 🌸."
    ) in res.pantalla.texto
    assert juego.boton(ADMIN, "", "invitar").alerta  # mientras se crea, el resto no funciona
    juego.boton(ADMIN, "", "apok")
    j = juego.db.jugador(ADMIN)
    assert j.ap["rasgos"] == ["romantico", "divertido", "ordenado"]
    assert j.estado == "activo"


def test_sin_pelo_salta_el_color(juego):
    juego.inicio(ADMIN, "Admin", None)
    juego.texto(ADMIN, "Admin", "Luis")
    for dato in ["ap:genero:hombre", "ap:etapa:adulta", "ap:piel:clara", "ap:cuerpo:robusta",
                 "ap:estatura:alta", "ap:peinado:sin"]:
        res = juego.boton(ADMIN, "", dato)
    assert "Paso 7 de 12" in res.pantalla.texto and "ojos" in res.pantalla.texto


def test_editar_personaje_y_cancelar(pareja):
    antes = pareja.db.jugador(ADMIN).apariencia
    pareja.boton(ADMIN, "", "apedit")
    pareja.boton(ADMIN, "", "ap:genero:nobinario")
    res = pareja.boton(ADMIN, "", "apx")
    assert pareja.db.jugador(ADMIN).apariencia == antes
    assert "Personajes de la sala" in res.pantalla.texto
    pareja.boton(ADMIN, "", "apedit")
    pareja.boton(ADMIN, "", "ap:genero:nobinario")
    res = pareja.boton(ADMIN, "", "apok")
    assert res.alerta == "✅ Personaje guardado"
    assert pareja.db.jugador(ADMIN).ap["genero"] == "nobinario"


def test_cambiar_animo_se_ve_en_la_sala_de_la_pareja(pareja):
    pareja.registrar_pantalla(ADMIN, 55, es_sala=True)
    res = pareja.boton(ANA, "Ana", "animos")
    assert "animo:triste" in datos(res.pantalla)
    res = pareja.boton(ANA, "Ana", "animo:triste")
    assert "mándame una foto" in res.pantalla.texto
    res = pareja.boton(ANA, "Ana", "animop")
    assert "Triste" in res.alerta
    assert "🔵 😢 Triste" in res.ediciones[0].pantalla.texto
    assert any(a.para == ADMIN and "ahora se siente" in a.texto for a in res.avisos)


def test_avatar_en_emoji():
    assert P.avatar({"genero": "mujer", "piel": "morena", "peinado": "rizado"}) == "👩🏾‍🦱"
    assert P.avatar({"genero": "hombre", "piel": "clara", "peinado": "corto", "pelo": "rubio"}) == "👱🏼‍♂️"
    assert P.avatar({"genero": "mujer", "etapa": "mayor", "piel": "oscura"}) == "👵🏿"


def test_todo_al_azar_siempre_completo():
    rng = random.Random(1)
    for _ in range(200):
        ap = P.todo_al_azar(rng)
        assert P.completa(ap)
        assert 1 <= len(ap["rasgos"]) <= 3


# --- reloj del Sim, pausa y Continuar ---------------------------------------------

def test_reloj_propio_y_pausa_a_los_5_minutos(pareja, reloj):
    assert "🕒 Lunes 08:00 · día 1" in pareja.boton(ANA, "Ana", "sala").pantalla.texto
    reloj.avanzar(3)
    assert "Lunes 08:03 · día 1" in pareja.boton(ANA, "Ana", "sala").pantalla.texto
    reloj.avanzar(20)  # 20 min sin hacer nada: el Sim se congeló a los 5
    res = pareja.boton(ANA, "Ana", "pjs")
    assert "Tu Sim estaba en pausa" in res.pantalla.texto
    assert "se quedó en pausa hace 15 min" in res.pantalla.texto
    assert datos(res.pantalla) == ["continuar"]
    reloj.avanzar(1)
    res = pareja.boton(ANA, "Ana", "continuar")
    assert "¡Seguimos!" in res.pantalla.texto
    reloj.avanzar(2)
    assert "Lunes 08:26 · día 1" in pareja.boton(ANA, "Ana", "sala").pantalla.texto  # la hora es la real


def test_la_pausa_es_solo_de_quien_se_fue(pareja, reloj):
    reloj.avanzar(10)
    pareja.boton(ADMIN, "", "continuar")  # Luis sigue jugando
    reloj.avanzar(3)
    texto = pareja.boton(ADMIN, "", "sala").pantalla.texto
    assert "Lunes 08:13 · día 1" in texto  # la hora es la real de cada jugador
    assert "🟡 ausente · hace 13 min · ❄️ Sim en pausa" in texto  # Ana sigue en pausa


def test_el_chat_no_descongela_al_sim(pareja, reloj):
    reloj.avanzar(10)
    res = pareja.texto(ANA, "Ana", "hola")
    assert res.avisos  # el mensaje llega igual
    pareja.boton(ADMIN, "", "continuar")
    sala_luis = pareja.boton(ADMIN, "", "sala").pantalla.texto
    assert "🟢 en línea · ❄️ Sim en pausa" in sala_luis


def test_tick_congela_la_sala_abierta(pareja, reloj):
    pareja.registrar_pantalla(ANA, 77, es_sala=True)
    reloj.avanzar(6)
    ediciones = {e.para: e for e in pareja.tick().ediciones}
    assert "Tu Sim está en pausa" in ediciones[ANA].pantalla.texto
    assert datos(ediciones[ANA].pantalla)[0] == "continuar"


def test_hora_local_del_jugador(juego, reloj):
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    j = juego.db.jugador(ADMIN)
    assert juego._reloj(j) == "Lunes 08:00 · día 1"
    reloj.avanzar(16 * 60 + 1)
    assert juego._reloj(j) == "Martes 00:01 · día 2"
    j.utc_offset = -300  # una hora menos
    assert juego._reloj(j) == "Lunes 23:01 · día 1"


# --- última conexión: volver al mismo sitio ---------------------------------------

def test_volver_a_los_3_minutos_retoma_la_misma_pantalla(pareja, reloj):
    pareja.boton(ANA, "Ana", "invitar")
    reloj.avanzar(3)
    res = pareja.inicio(ANA, "Ana")
    assert "Retomas donde lo dejaste: <b>💌 Invitar</b> · hace 3 min" in res.pantalla.texto
    assert "Invitar a un jugador" in res.pantalla.texto


def test_volver_a_los_5_minutos_pide_continuar_y_retoma(pareja, reloj):
    pareja.boton(ANA, "Ana", "pjs")
    reloj.avanzar(5)
    res = pareja.inicio(ANA, "Ana")
    assert "Tu Sim estaba en pausa" in res.pantalla.texto
    assert "en <b>🪪 Personajes</b>" in res.pantalla.texto
    res = pareja.boton(ANA, "Ana", "continuar")
    assert "Retomas donde lo dejaste: <b>🪪 Personajes</b> · hace 5 min" in res.pantalla.texto
    assert "Personajes de la sala" in res.pantalla.texto


def test_salir_y_volver_a_entrar(pareja, reloj):
    pareja.registrar_pantalla(ADMIN, 55, es_sala=True)
    pareja.boton(ANA, "Ana", "ajustes")
    res = pareja.boton(ANA, "Ana", "salir")
    assert "⚙️ Ajustes" in res.pantalla.texto
    assert "Ana</b> · " in res.ediciones[0].pantalla.texto
    assert "⚫ fuera de línea" in res.ediciones[0].pantalla.texto
    reloj.avanzar(40)
    res = pareja.boton(ANA, "Ana", "volver")
    assert "<b>Ajustes</b>" in res.pantalla.texto and "Retomas donde lo dejaste" in res.pantalla.texto
    assert any(a.para == ADMIN and "entró a la sala" in a.texto for a in res.avisos)


def test_volver_a_mitad_de_la_creacion(juego, reloj):
    juego.inicio(ADMIN, "Admin", None)
    juego.texto(ADMIN, "Admin", "Luis")
    juego.boton(ADMIN, "", "ap:genero:mujer")
    juego.boton(ADMIN, "", "ap:etapa:joven")
    reloj.avanzar(30)
    res = juego.inicio(ADMIN, "Admin")
    assert "Retomas donde lo dejaste: <b>🧑‍🎨 Creador de personaje</b>" in res.pantalla.texto
    assert "Paso 3 de 13" in res.pantalla.texto


def test_volver_a_mitad_de_un_cambio_de_nombre(pareja, reloj):
    pareja.boton(ANA, "Ana", "renombrar")
    reloj.avanzar(2)
    assert "Escribe el nuevo nombre" in pareja.inicio(ANA, "Ana").pantalla.texto


def test_solo_se_guarda_la_ultima_conexion(pareja, reloj):
    for accion in ["sala", "pjs", "ajustes", "invitar", "animos"]:
        pareja.boton(ANA, "Ana", accion)
        reloj.avanzar(1)
    pareja.texto(ANA, "Ana", "te quiero")
    filas = pareja.db.con.execute("SELECT * FROM ultima_conexion WHERE jugador_id = ?", (ANA,)).fetchall()
    assert len(filas) == 1
    uc = pareja.db.ultima_conexion(ANA)
    assert uc.pantalla == "animo" and uc.actividad == "💬 chateando"
    texto = pareja.comando(ANA, "Ana", "conexion").pantalla.texto
    assert "🎭 Estado de ánimo" in texto and "💬 chateando" in texto


def test_sala_muestra_que_hace_la_pareja(pareja):
    pareja.boton(ANA, "Ana", "invitar")
    assert "🟢 en línea · invitando a alguien" in pareja.boton(ADMIN, "", "sala").pantalla.texto


# --- chat interno -----------------------------------------------------------------

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


# --- presencia en vivo ------------------------------------------------------------

def test_presencia_en_vivo(pareja, reloj):
    pareja.registrar_pantalla(ADMIN, 55, es_sala=True)
    reloj.avanzar(6)
    res = pareja.tick()
    assert "🟡 ausente · hace 6 min · ❄️ Sim en pausa" in next(
        e for e in res.ediciones if e.para == ADMIN).pantalla.texto
    reloj.avanzar(60)
    res = pareja.tick()
    assert "⚫ fuera de línea · visto hace 1 h" in res.ediciones[0].pantalla.texto
    assert not pareja.tick().ediciones  # sin cambios, no se edita nada


def test_avisos_de_conexion_desactivables(pareja, reloj):
    pareja.boton(ADMIN, "Admin", "avisos")
    pareja.boton(ANA, "Ana", "salir")
    reloj.avanzar(40)
    assert not pareja.boton(ANA, "Ana", "volver").avisos


def test_renombrar(pareja):
    pareja.boton(ANA, "Ana", "renombrar")
    res = pareja.texto(ANA, "Ana", "Anita")
    assert "Anita" in res.pantalla.texto
    assert pareja.db.jugador(ANA).estado == "activo"
    assert pareja.texto(ANA, "Ana", "hola").avisos


# --- novedades y base de datos --------------------------------------------------------

def test_novedades_se_anuncian_una_vez_por_version(pareja):
    res = pareja.anunciar_novedades()
    assert {a.para for a in res.avisos} == {ADMIN, ANA}
    assert f"versión {N.VERSION}" in res.avisos[0].texto
    assert not pareja.anunciar_novedades().avisos
    pareja.db.guardar_meta("version_anunciada", "0.1")
    assert "<b>Versión 0.1</b>" not in pareja.anunciar_novedades().avisos[0].texto


def test_migra_una_base_de_datos_de_la_version_anterior(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE invitaciones (codigo TEXT PRIMARY KEY, creador INTEGER NOT NULL, tipo TEXT NOT NULL,
            sala_id INTEGER, creada REAL NOT NULL, expira REAL NOT NULL, usada_por INTEGER,
            usada_ts REAL, anulada INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE jugadores (id INTEGER PRIMARY KEY, estado TEXT NOT NULL,
            nombre_tg TEXT NOT NULL DEFAULT '', personaje TEXT NOT NULL DEFAULT '',
            apariencia TEXT NOT NULL DEFAULT '{}', borrador TEXT, sala_id INTEGER, invitado_por INTEGER,
            inv_codigo TEXT, ultima_actividad REAL NOT NULL DEFAULT 0, salio INTEGER NOT NULL DEFAULT 0,
            presencia TEXT NOT NULL DEFAULT 'fuera', msg_sala INTEGER,
            aviso_conexion_ts REAL NOT NULL DEFAULT 0, avisos_conexion INTEGER NOT NULL DEFAULT 1,
            creado REAL NOT NULL);
        INSERT INTO jugadores (id, estado, personaje, sala_id, creado) VALUES (1, 'activo', 'Vieja', 1, 0);
    """)
    con.commit()
    con.close()
    db = DB(str(ruta))
    j = db.jugador(1)
    assert j.personaje == "Vieja" and j.reloj_desde is None
    assert db.invitaciones_para(1, 0) == []
