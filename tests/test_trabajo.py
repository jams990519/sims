"""Parte 6 y actualización 2, parte 2: trabajos con horario real, automáticos y flexibles."""

import json
import random

import pytest

from simpareja import trabajo as T
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def juego(reloj):
    j = nuevo_juego(reloj)
    j.inicio(ADMIN, "Admin")
    crear_personaje(j, ADMIN, "Luis")
    return j


@pytest.fixture
def pareja(juego):
    aceptar(juego, ANA, invitar(juego, ADMIN, ANA))
    crear_personaje(juego, ANA, "Ana")
    return juego


def ser(juego, genero):
    jug = juego.db.jugador(ADMIN)
    ap = jug.ap
    ap["genero"] = genero
    jug.apariencia = json.dumps(ap)
    juego.db.guardar_jugador(jug)


def ser_mujer(juego):
    ser(juego, "mujer")


def empleo(juego):
    return json.loads(juego.db.jugador(ADMIN).trabajo)


def turno(juego, reloj, horas=8):
    res = juego.boton(ADMIN, "", f"trabajar:{horas}:sin")
    reloj.avanzar(horas * 60 + 1)
    return res, juego.tick()


def test_lista_de_trabajos(juego):
    ser(juego, "hombre")
    res = juego.boton(ADMIN, "", "trabajo")
    texto = str(res.pantalla.botones)
    assert len([d for fila in res.pantalla.botones for _, d in fila if d.startswith("vtrab:")]) == 7
    for t in ("Manicurista · $10/h", "Asistente de estudio · $11/h", "$10/h", "Repartidor", "Ayudante de cocina",
              "Recepcionista · $11/h", "$12/h"):
        assert t in texto


def test_ver_y_aceptar_un_trabajo(juego):
    ser_mujer(juego)
    texto = juego.boton(ADMIN, "", "vtrab:foto").pantalla.texto
    assert "Nivel 2: Fotógrafa · $16/h" in texto and "Nivel 3: Directora del estudio · $24/h" in texto
    assert "de lunes a viernes" in texto and "máximo 8 h al día" in texto
    res = juego.boton(ADMIN, "", "tomar:foto")
    assert "¡Te contrataron!" in res.pantalla.texto and "¿qué hora es ahora donde estás?" in res.pantalla.texto
    assert "📸 Asistente de estudio · $11/h" in juego.boton(ADMIN, "", "sim").pantalla.texto


def poner_horario(juego, uid=ADMIN, offset=-240, *toques):
    """Elige la hora local y guarda el horario (por defecto: lunes a viernes, 09:00, 8 h)."""
    juego.boton(uid, "", "hor")
    res = juego.boton(uid, "", f"hor:tz:{offset}")
    for toque in toques:
        res = juego.boton(uid, "", f"hor:{toque}")
    return res, juego.boton(uid, "", "hor:ok")


def test_horario_real_con_hora_local(juego):
    res = juego.boton(ADMIN, "", "tomar:recepcion")
    opciones = [d for fila in res.pantalla.botones for _, d in fila if d.startswith("hor:tz:")]
    assert len(opciones) == 24 and "hor:tz:-240" in opciones  # las 24 horas del mundo
    assert "🕒 08:00" in str(res.pantalla.botones) and "🕒 13:00" in str(res.pantalla.botones)
    res, guardado = poner_horario(juego, ADMIN, 60, "d:0", "d:5", "i:14:00", "h:6")
    assert juego.db.jugador(ADMIN).utc_offset == 60
    assert "🕒 Tu hora ahora: 13:00" in res.pantalla.texto
    assert "Mar, Mié, Jue, Vie, Sáb, de 14:00 a 20:00 (6 h)" in res.pantalla.texto and "$66 por día" in res.pantalla.texto
    assert "¡Horario guardado!" in guardado.pantalla.texto
    assert empleo(juego)["horario"] == {"dias": [1, 2, 3, 4, 5], "inicio": "14:00", "horas": 6}
    assert "Tu horario: Mar, Mié, Jue, Vie, Sáb, de 14:00 a 20:00 (6 h)" in juego.boton(ADMIN, "", "trabajo").pantalla.texto


def test_como_mucho_8_horas(juego):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(juego, ADMIN, -240, "h:9")
    assert empleo(juego)["horario"]["horas"] == 8
    poner(juego, ADMIN, **LLENO)
    assert juego.boton(ADMIN, "", "trabajar:9:sin").alerta == "Como mucho 8 horas al día."
    assert juego.db.jugador(ADMIN).accion is None


def test_sin_dias_no_se_guarda(juego):
    juego.boton(ADMIN, "", "tomar:recepcion")
    _, res = poner_horario(juego, ADMIN, -240, *(f"d:{d}" for d in range(5)))
    assert res.alerta == "Elige al menos un día." and "horario" not in empleo(juego)


def test_un_turno_de_8_horas(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    res = juego.boton(ADMIN, "", "trabajo")
    assert "Hoy (Lunes) entras a las 09:00" in res.pantalla.texto
    assert "trabajar:ir" in str(res.pantalla.botones) and "trabajar:luego" in str(res.pantalla.botones)
    res = juego.boton(ADMIN, "", "trabajar:ir")
    assert "+$88 al terminar" in res.pantalla.texto and "¿Confirmar?" in res.pantalla.texto
    res = juego.boton(ADMIN, "", "trabajar:8:sin")
    assert "Sale a las 16:00" in res.pantalla.texto
    assert "💼 trabajando hasta las 16:00" in juego.boton(ADMIN, "", "sala").pantalla.texto
    reloj.avanzar(8 * 60 + 1)
    avisos = juego.tick().avisos
    assert any(a.para == ADMIN and "Cobró $88" in a.texto for a in avisos)
    j = juego.db.jugador(ADMIN)
    assert j.cartera == 88
    assert juego._hogar(j.sala_id).cuenta == 1500 - 4  # transporte
    assert nec(juego, ADMIN)["energia"] == pytest.approx(100 - 64, abs=0.5)
    assert empleo(juego)["dias"] == 1


def test_un_turno_por_dia_y_dias_libres(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    turno(juego, reloj)
    assert "Hoy (Lunes) ya trabajaste" in juego.boton(ADMIN, "", "trabajo").pantalla.texto
    assert juego.boton(ADMIN, "", "trabajar:8:sin").alerta == "Hoy ya trabajaste."
    ir_al_dia(juego, reloj, ADMIN, 6)
    assert "Hoy (Sábado) es tu día libre" in juego.boton(ADMIN, "", "trabajo").pantalla.texto
    assert juego.boton(ADMIN, "", "trabajar:8:sin").alerta == "Hoy es tu día libre."


def test_rotativo_libra_dos_dias_seguidos_entre_semana():
    for semilla in range(20):
        dias = T.dias_sugeridos(T.ROTATIVO, random.Random(semilla))
        libres = [d for d in range(7) if d not in dias]
        assert len(libres) == 2 and libres[1] == libres[0] + 1 and libres[1] <= 4
    assert T.trabaja({"dias": [5, 6]}, 6) and not T.trabaja({"dias": [5, 6]}, 2)
    assert T.hora_salida({"inicio": "20:00", "horas": 8}) == "04:00"


# --- turno automático y flexible ----------------------------------------------------

def test_se_va_solo_a_trabajar_aunque_no_estes(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(juego)
    poner(juego, ADMIN, **LLENO)
    reloj.avanzar(59)
    juego.tick()
    assert juego.db.jugador(ADMIN).accion is None  # todavía no son las 09:00
    reloj.avanzar(1)
    avisos = juego.tick().avisos
    aviso = next(a for a in avisos if "se fue a trabajar" in a.texto)
    assert "Sale a las 17:00" in aviso.texto and not aviso.botones  # no estaba conectado
    assert json.loads(juego.db.jugador(ADMIN).accion)["k"] == "trabajar"
    reloj.avanzar(8 * 60 + 1)
    avisos = juego.tick().avisos
    assert any("Cobró $88" in a.texto for a in avisos)
    assert juego.db.jugador(ADMIN).cartera == 88
    reloj.avanzar(60)
    assert not [a for a in juego.tick().avisos if "trabajar" in a.texto]  # un turno al día


def test_si_estas_conectado_solo_puedes_quedarte(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(juego)
    poner(juego, ADMIN, **LLENO)
    reloj.avanzar(58)
    juego.boton(ADMIN, "", "sim")  # está jugando, sin su pareja
    reloj.avanzar(2)
    aviso = next(a for a in juego.tick().avisos if "se fue a trabajar" in a.texto)
    assert ("⏰ Quedarme: ir cuando me desconecte", "trabajar:luego") in aviso.botones[0]
    res = juego.boton(ADMIN, "", "trabajar:luego")
    assert "irá a trabajar cuando te desconectes" in res.pantalla.texto
    assert juego.db.jugador(ADMIN).accion is None and juego.db.jugador(ADMIN).lugar == "salon"
    reloj.avanzar(3)
    juego.boton(ADMIN, "", "sim")
    reloj.avanzar(1)
    assert not juego.tick().avisos  # sigue jugando: no se va
    reloj.avanzar(6)  # se desconectó
    aviso = next(a for a in juego.tick().avisos if "se fue a trabajar" in a.texto)
    assert "Sale a las 17:10" in aviso.texto
    assert juego._hogar(juego.db.jugador(ADMIN).sala_id).cuenta == 1500 - 4  # el pasaje se paga una vez


def test_tiempo_juntos_protegido(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(pareja)
    poner(pareja, ADMIN, **LLENO)
    reloj.avanzar(58)
    pareja.boton(ADMIN, "", "continuar")
    pareja.boton(ANA, "", "continuar")  # están los dos conectados
    reloj.avanzar(2)
    aviso = next(a for a in pareja.tick().avisos if a.para == ADMIN)
    assert "Es tu hora de trabajar (09:00), pero estás con" in aviso.texto and "No te obligo" in aviso.texto
    assert aviso.botones == [[("💼 Ir ahora", "trabajar:ir"), ("⏰ Cuando me desconecte", "trabajar:luego")]]
    assert pareja.db.jugador(ADMIN).accion is None  # nunca se le obliga
    reloj.avanzar(1)
    pareja.boton(ADMIN, "", "sala")
    assert not [a for a in pareja.tick().avisos if a.para == ADMIN]  # pregunta una sola vez
    assert "Moviste el turno" not in pareja.boton(ADMIN, "", "trabajo").pantalla.texto
    pareja.boton(ADMIN, "", "trabajar:luego")
    assert "Moviste el turno" in pareja.boton(ADMIN, "", "trabajo").pantalla.texto
    reloj.avanzar(3 * 60)  # se quedaron jugando y luego Luis se fue
    aviso = next(a for a in pareja.tick().avisos if a.para == ADMIN)
    assert "se fue a trabajar" in aviso.texto and "Sale a las 20:01" in aviso.texto
    reloj.avanzar(8 * 60 + 1)
    pareja.tick()
    assert pareja.db.jugador(ADMIN).cartera == 88  # trabajó sin él y cobró


def test_si_no_repone_el_turno_ese_dia_no_cobra(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(pareja)
    reloj.avanzar(60)
    pareja.boton(ADMIN, "", "trabajar:luego")
    ir_al_dia(pareja, reloj, ADMIN, 2)  # siguió conectado hasta el otro día
    assert pareja.db.jugador(ADMIN).cartera == 0 and not empleo(pareja).get("historial")
    assert "Hoy (Martes) entras a las 09:00" in pareja.boton(ADMIN, "", "trabajo").pantalla.texto


def test_ir_ahora_desde_el_aviso(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(pareja)
    poner(pareja, ADMIN, **LLENO)
    reloj.avanzar(59)
    pareja.boton(ADMIN, "", "continuar")
    pareja.boton(ANA, "", "continuar")
    reloj.avanzar(1)
    assert any("No te obligo" in a.texto for a in pareja.tick().avisos)
    pareja.boton(ADMIN, "", "trabajar:ir")
    res = pareja.boton(ADMIN, "", "trabajar:8:sin")
    assert "¡A trabajar!" in res.pantalla.texto


def test_el_chat_y_las_acciones_rapidas_durante_el_turno(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner(pareja, ADMIN, **LLENO)
    poner(pareja, ANA, social=50)
    pareja.boton(ADMIN, "", "trabajar:8:sin")
    assert pareja.texto(ADMIN, "", "te extraño").avisos  # el chat siempre funciona
    assert "rapida:abrazo" in str(pareja.boton(ADMIN, "", "sim").pantalla.botones)
    res = pareja.boton(ADMIN, "", "rapida:abrazo")
    assert "Abrazo enviado" in res.pantalla.texto
    assert any(a.para == ANA and "te mandó un abrazo desde el trabajo" in a.texto for a in res.avisos)
    assert nec(pareja, ANA)["social"] == pytest.approx(55, abs=0.2)
    assert "cada media hora" in pareja.boton(ADMIN, "", "rapida:redes").alerta
    reloj.avanzar(31)
    assert "Descanso" in pareja.boton(ADMIN, "", "rapida:redes").pantalla.texto
    assert json.loads(pareja.db.jugador(ADMIN).accion)["k"] == "trabajar"  # sigue trabajando


def test_trabajando_no_acepta_planes_juntos(pareja, reloj):
    pareja.boton(ADMIN, "", "tomar:recepcion")
    poner(pareja, ADMIN, **LLENO)
    pareja.boton(ADMIN, "", "trabajar:8:sin")
    res = pareja.boton(ANA, "", "aj:abrazar")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    res = pareja.boton(ADMIN, "", si)
    assert "abrazo rápido" in res.alerta
    assert json.loads(pareja.db.jugador(ADMIN).accion)["k"] == "trabajar"


def test_si_no_puede_ir_avisa_una_vez(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner_horario(juego)
    poner(juego, ADMIN, social=0)
    reloj.avanzar(60)
    avisos = [a for a in juego.tick().avisos if "no pudo ir a trabajar" in a.texto]
    assert len(avisos) == 1 and "mal humor" in avisos[0].texto
    reloj.avanzar(1)
    assert not [a for a in juego.tick().avisos if "no pudo ir a trabajar" in a.texto]


def test_con_mal_humor_no_se_trabaja(juego):
    juego.boton(ADMIN, "", "tomar:taller")
    poner(juego, ADMIN, social=0)
    assert "mal humor" in juego.boton(ADMIN, "", "trabajar:8:sin").alerta


def test_ascenso_tras_5_dias_sin_rojos(juego, reloj):
    ser_mujer(juego)
    juego.boton(ADMIN, "", "tomar:recepcion")
    avisos = []
    for dia in range(1, 6):
        ir_al_dia(juego, reloj, ADMIN, dia)
        poner(juego, ADMIN, **LLENO)
        _, res = turno(juego, reloj)
        avisos += res.avisos
    assert any("¡Ascenso!</b> Ahora es administrativa ($16/h)" in a.texto for a in avisos)
    e = empleo(juego)
    assert e["nivel"] == 2 and e["dias"] == 0


def test_con_necesidades_en_rojo_el_dia_no_cuenta(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    poner(juego, ADMIN, hambre=20)
    res, _ = turno(juego, reloj)
    assert "no contará para el ascenso" in res.pantalla.texto
    assert empleo(juego)["dias"] == 0
    assert juego.db.jugador(ADMIN).cartera == 88  # pero cobra igual


def test_parar_a_mitad_cobra_las_horas_hechas(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    juego.boton(ADMIN, "", "trabajar:8:sin")
    reloj.avanzar(3 * 60)
    res = juego.boton(ADMIN, "", "parar")
    assert "Cobró $33" in res.pantalla.texto and "turno incompleto" in res.pantalla.texto
    assert empleo(juego)["dias"] == 0


def test_sin_energia_se_duerme_en_el_trabajo(juego, reloj):
    juego.boton(ADMIN, "", "tomar:recepcion")
    poner(juego, ADMIN, **LLENO)
    poner(juego, ADMIN, energia=20)
    juego.boton(ADMIN, "", "trabajar:8:sin")
    avisos = []
    for _ in range(3 * 60):  # el bot revisa cada minuto
        reloj.avanzar(1)
        avisos += juego.tick().avisos
        if any("Dejó de trabajar" in a.texto for a in avisos):
            break
    assert any("necesita atención" in a.texto for a in avisos)  # antes avisó de la energía baja
    assert any("Dejó de trabajar a mitad del turno" in a.texto for a in avisos)
    assert json.loads(juego.db.jugador(ADMIN).accion)["k"] == "dormir"
    assert juego.db.jugador(ADMIN).cartera == round(11 * 19 / 8)  # cae al bajar de 1: (20 − 1) ÷ 8 h


def test_renunciar_y_empezar_de_cero(juego):
    juego.boton(ADMIN, "", "tomar:taller")
    j = juego.db.jugador(ADMIN)
    j.trabajo = json.dumps({**empleo(juego), "nivel": 3})
    juego.db.guardar_jugador(j)
    assert "renunciar:si" in str(juego.boton(ADMIN, "", "renunciar").pantalla.botones)
    res = juego.boton(ADMIN, "", "renunciar:si")
    assert "Renunciaste" in res.pantalla.texto and empleo(juego) == {}
    juego.boton(ADMIN, "", "tomar:taller")
    assert empleo(juego)["nivel"] == 1


def test_hora_local_en_ajustes(juego):
    assert "🕒 Tu hora local: 08:00" in juego.boton(ADMIN, "", "ajustes").pantalla.texto
    assert "zona:60" in str(juego.boton(ADMIN, "", "zona").pantalla.botones)
    res = juego.boton(ADMIN, "", "zona:60")
    assert res.alerta == "🕒 Listo: tu hora es 13:00" and "🕒 Tu hora local: 13:00" in res.pantalla.texto
    juego.boton(ADMIN, "", "tomar:recepcion")
    assert "🕒 Tu hora ahora: 13:00" in juego.boton(ADMIN, "", "hor").pantalla.texto  # ya no vuelve a preguntar
