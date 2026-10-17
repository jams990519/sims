"""Actualización 2, parte 10: aniversario mensual y álbum de recuerdos."""

from datetime import date

import pytest

from simpareja import aniversario_juego as A
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nuevo_juego, Reloj

FEB_1 = date(2024, 2, 1).toordinal()  # empezaron el lunes 1 de enero: cumplen un mes el jueves 1 de febrero


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


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def planear(juego, plan="restaurante", presupuesto=60, dia=FEB_1):
    juego.boton(ADMIN, "", "anivp")
    juego.boton(ADMIN, "", f"anivp:{plan}")
    juego.boton(ADMIN, "", f"anivp:{plan}:{presupuesto}")
    res = juego.boton(ADMIN, "", f"anivp:{plan}:{presupuesto}:{dia}")
    juego.boton(ANA, "", "anivok")
    return res


def test_fechas():
    assert A.sumar_meses(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert A.proximo(date(2024, 1, 1), date(2024, 1, 1)) == (1, date(2024, 2, 1))
    assert A.proximo(date(2024, 1, 1), date(2024, 2, 2)) == (2, date(2024, 3, 1))
    assert A.texto_meses(1) == "1 mes" and A.texto_meses(12) == "1 año" and A.texto_meses(5) == "5 meses"


def test_aviso_tres_dias_antes(pareja, reloj):
    texto = pareja.boton(ADMIN, "", "aniv").pantalla.texto
    assert "cumplen <b>1 mes</b> juntos el jueves 1" in texto
    ir_al_dia(pareja, reloj, ADMIN, 29)
    avisos = [a for a in pareja.tick().avisos if "cumplen 1 mes" in a.texto]
    assert {a.para for a in avisos} == {ADMIN, ANA} and "En 3 día(s)" in avisos[0].texto
    assert not [a for a in pareja.tick().avisos if "cumplen" in a.texto]  # una sola vez


def test_planear_juntos(pareja):
    res = pareja.boton(ADMIN, "", "anivp:restaurante")
    assert datos(res.pantalla)[:3] == ["anivp:restaurante:40", "anivp:restaurante:60", "anivp:restaurante:80"]
    res = pareja.boton(ADMIN, "", "anivp:restaurante:60")
    assert f"anivp:restaurante:60:{FEB_1}" in datos(res.pantalla) and f"anivp:restaurante:60:{FEB_1 + 2}" in datos(res.pantalla)
    res = pareja.boton(ADMIN, "", f"anivp:restaurante:60:{FEB_1 + 1}")  # lo mueven al viernes
    aviso = next(a for a in res.avisos if a.para == ANA)
    assert "el viernes 2: 🍝 Restaurante ($60)" in aviso.texto and "anivok" in datos(aviso)
    assert pareja.boton(ADMIN, "", "anivok").alerta == "Esa propuesta ya no está."  # no se acepta a sí mismo
    res = pareja.boton(ANA, "", "anivok")
    assert "¡Plan acordado!" in res.pantalla.texto
    assert hogar(pareja).cuenta == 2100 - 60
    assert pareja._extras_hogar(hogar(pareja))["aniv"]["dia"] == FEB_1 + 1


def test_celebrar_con_brindis_y_regalos(pareja, reloj):
    planear(pareja)
    ir_al_dia(pareja, reloj, ADMIN, 32)
    avisos = [a for a in pareja.tick().avisos if "Hoy celebran 1 mes" in a.texto]
    assert len(avisos) == 2
    assert "🎂 Aniversario 🎉" in str(pareja.boton(ADMIN, "", "mpar").pantalla.botones)
    res = pareja.boton(ADMIN, "", "anivb")
    assert any(a.para == ANA and "choca la tuya" in a.texto for a in res.avisos)
    res = pareja.boton(ANA, "", "anivb")
    assert any("Chin chin" in a.texto for a in res.avisos)
    res = pareja.boton(ADMIN, "", "anivr")
    assert "anivr:flores" in datos(res.pantalla)
    antes = hogar(pareja).cuenta
    pareja.boton(ADMIN, "", "anivr:flores")  # sin dinero en la cartera, sale de la compartida
    relacion = [pareja._relacion(pareja.db.jugador(uid)) for uid in (ADMIN, ANA)]  # ya incluye el hito del primer mes
    res = pareja.boton(ANA, "", "anivr:carta")
    assert "¡Feliz aniversario de 1 mes!" in res.pantalla.texto
    assert any(a.para == ADMIN and "Feliz aniversario" in a.texto for a in res.avisos)
    assert [pareja._relacion(pareja.db.jugador(uid)) for uid in (ADMIN, ANA)] == [r + 10 for r in relacion]
    assert hogar(pareja).cuenta == antes - 15
    album = pareja.boton(ADMIN, "", "album").pantalla.texto
    assert "Aniversarios" in album and "🎂 1 mes juntos: 🍝 restaurante, brindis y 🌹 flores y 💌 una carta" in album


def test_hacen_falta_los_dos_conectados(pareja, reloj):
    planear(pareja)
    ir_al_dia(pareja, reloj, ADMIN, 32)
    reloj.avanzar(6)
    pareja.boton(ADMIN, "", "continuar")
    assert "no está en línea" in pareja.boton(ADMIN, "", "anivb").alerta
    reloj_antes = reloj.t
    reloj.t = reloj_antes - 24 * 3600  # otro día
    assert pareja.boton(ADMIN, "", "anivb").alerta == "Hoy no toca celebrar."


def test_si_no_se_celebra_se_pierde_la_recompensa(pareja, reloj):
    pareja.tick()
    ir_al_dia(pareja, reloj, ADMIN, 33)
    avisos = pareja.tick().avisos
    assert any("Esta vez no celebraron sus 1 mes" in a.texto for a in avisos)
    pareja.tick()
    aniv = pareja._extras_hogar(hogar(pareja))["aniv"]
    assert aniv["n"] == 2 and aniv["fecha"] == date(2024, 3, 1).toordinal()
    historial = pareja._extras(pareja.db.jugador(ADMIN)).get("relacion_hist", [])
    assert not [c for c in historial if "Aniversario" in c["m"]]


def test_las_citas_quedan_en_el_album(pareja, reloj):
    res = pareja.boton(ANA, "", "aj:cine")
    si = next(d for fila in res.avisos[0].botones for _, d in fila if d.endswith(":1"))
    pareja.boton(ADMIN, "", si)
    reloj.avanzar(3 * 60)
    pareja.tick()
    pareja.boton(ADMIN, "", "continuar")
    album = pareja.boton(ADMIN, "", "album").pantalla.texto
    assert "🌹 <b>Citas</b>" in album and album.count("🎬 Cita en el cine") == 1


def test_sin_pareja(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    assert "para jugar en pareja" in juego.boton(ADMIN, "", "aniv").alerta
