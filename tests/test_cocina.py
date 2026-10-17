"""Parte 7: súper y minijuego de cocina."""

import json

import pytest

from simpareja import cocina as C
from test_juego import ADMIN, ANA, aceptar, crear_personaje, invitar
from test_vida import ir_al_dia, nec, nuevo_juego, poner, Reloj

LLENO = dict(hambre=100, energia=100, higiene=100, diversion=100, social=100)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def solo(reloj):
    juego = nuevo_juego(reloj)
    juego.inicio(ADMIN, "Admin")
    crear_personaje(juego, ADMIN, "Luis")
    return juego


@pytest.fixture
def pareja(solo):
    aceptar(solo, ANA, invitar(solo, ADMIN, ANA))
    crear_personaje(solo, ANA, "Ana")
    return solo


def hogar(juego):
    return juego._hogar(juego.db.jugador(ADMIN).sala_id)


def llenar_despensa(juego, **cosas):
    h = hogar(juego)
    h.despensa = json.dumps(cosas)
    juego.db.guardar_hogar(h)


def datos(pantalla):
    return [d for fila in pantalla.botones for _, d in fila]


def cocinar_todo(juego, reloj, uid, receta, juntos=False):
    """Va tocando ✅ justo cuando cada paso está listo."""
    res = None
    for _, minutos in C.RECETAS[receta].pasos:
        reloj.avanzar(C.minutos_paso(minutos, juntos))
        res = juego.boton(uid, "", "coc:sig")
    return res


# --- súper -------------------------------------------------------------------------

def test_comprar_en_el_super(solo):
    res = solo.boton(ADMIN, "", "mlug")
    assert "a:super" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "a:super")
    assert "Los sábados y domingos hay ofertas" in res.pantalla.texto
    solo.boton(ADMIN, "", "sup:+:huevos")
    solo.boton(ADMIN, "", "sup:+:huevos")
    res = solo.boton(ADMIN, "", "sup:+:pan")
    assert "🥚 Huevos (docena) ×2" in res.pantalla.texto and "Total: $8.50" in res.pantalla.texto
    res = solo.boton(ADMIN, "", "sup:pagar")
    assert "Compra pagada: $9" in res.alerta
    assert json.loads(hogar(solo).despensa) == {"huevos": 24, "pan": 10}
    assert hogar(solo).cuenta == 1500 - 9
    assert "¿Confirmar?" in res.pantalla.texto  # ir y volver lleva su tiempo
    solo.boton(ADMIN, "", "as:super:ir")
    assert json.loads(solo.db.jugador(ADMIN).accion)["k"] == "super"
    assert solo.db.jugador(ADMIN).lugar == "fuera:super"


def test_ofertas_de_fin_de_semana(solo, reloj):
    ir_al_dia(solo, reloj, ADMIN, 6)
    res = solo.boton(ADMIN, "", "a:super")
    assert "Ofertas de fin de semana" in res.pantalla.texto
    assert "Pollo $4.00" in str(res.pantalla.botones)  # $5 − 20 %


# --- cocinar ---------------------------------------------------------------------------

def test_recetas_marcan_lo_que_se_puede_cocinar(solo):
    llenar_despensa(solo, huevos=2, pan=1)
    res = solo.boton(ADMIN, "", "a:cocinar")
    assert "✅ 🍳 Huevos revueltos con pan" in res.pantalla.texto
    assert "❌ 🍛 Arroz con pollo" in res.pantalla.texto
    res = solo.boton(ADMIN, "", "rec:arroz_pollo")
    assert "Falta:" in res.pantalla.texto and "a:super" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "rec:huevos")
    assert "coc:huevos:1" in datos(res.pantalla) and "coc:huevos:2" not in datos(res.pantalla)


def test_cocinar_paso_a_paso(solo, reloj):
    llenar_despensa(solo, huevos=2, pan=1)
    res = solo.boton(ADMIN, "", "coc:huevos:1")
    assert "paso 1 de 3" in res.pantalla.texto and "Batir los huevos" in res.pantalla.texto
    assert json.loads(hogar(solo).despensa) == {}  # se usan los ingredientes
    assert "cocinando huevos revueltos con pan" in solo.boton(ADMIN, "", "sala").pantalla.texto
    res = solo.boton(ADMIN, "", "coc:sig")  # demasiado pronto
    assert res.alerta == "Todavía no: faltan 2 min."
    res = cocinar_todo(solo, reloj, ADMIN, "huevos")
    assert "¡Huevos revueltos con pan listo!" in res.pantalla.texto
    assert "a:comer:huevos" in datos(res.pantalla) and "taper:huevos" in datos(res.pantalla)
    assert json.loads(hogar(solo).nevera) == {"huevos": 1}
    assert hogar(solo).cocina == "" and solo.db.jugador(ADMIN).accion is None


def test_si_te_pasas_se_quema(solo, reloj):
    llenar_despensa(solo, verduras=1)
    solo.boton(ADMIN, "", "coc:sopa:1")
    reloj.avanzar(5)
    avisos = solo.tick().avisos
    assert any("Picar las verduras: ¡listo!" in a.texto for a in avisos)
    assert not [a for a in solo.tick().avisos if "¡listo!" in a.texto]  # avisa una sola vez
    reloj.avanzar(4)  # margen: 3 min
    avisos = solo.tick().avisos
    assert any("¡Se quemó sopa de verduras!" in a.texto for a in avisos)
    assert hogar(solo).cocina == "" and json.loads(hogar(solo).nevera) == {}
    assert solo.db.jugador(ADMIN).accion is None


def test_tocar_tarde_tambien_quema(solo, reloj):
    llenar_despensa(solo, pan=2, jamon=1, queso=1)
    solo.boton(ADMIN, "", "coc:sandwich:1")
    reloj.avanzar(2 + 3)  # listo a los 2 min, margen de 2 min
    res = solo.boton(ADMIN, "", "coc:sig")
    assert "¡Se quemó" in res.pantalla.texto


def test_una_sola_cocina_y_parar(pareja):
    llenar_despensa(pareja, huevos=4, pan=2)
    pareja.boton(ADMIN, "", "coc:huevos:1")
    res = pareja.boton(ANA, "", "coc:huevos:1")
    assert "La cocina está ocupada: Luis está cocinando" in res.alerta
    res = pareja.boton(ADMIN, "", "parar")
    assert "Dejaste de cocinar" in res.pantalla.texto
    assert hogar(pareja).cocina == ""


def test_cocinar_juntos_es_mas_rapido(pareja, reloj):
    llenar_despensa(pareja, pan=4, jamon=2, queso=2)
    res = pareja.boton(ADMIN, "", "rec:sandwich")
    assert "aj:cocinar:sandwich:2" in datos(res.pantalla)
    res = pareja.boton(ADMIN, "", "aj:cocinar:sandwich:2")
    propuesta = next(a for a in res.avisos if a.para == ANA)
    assert "sándwich de jamón y queso" in propuesta.texto
    si = next(d for d in datos(propuesta) if d.endswith(":1"))
    res = pareja.boton(ANA, "", si)
    assert "A cocinar juntos" in res.pantalla.texto and "Dorarlo en la sartén · 3 min" in res.pantalla.texto
    reloj.avanzar(1)
    pareja.boton(ANA, "", "coc:sig")  # cualquiera de los dos puede tocar
    reloj.avanzar(3)
    res = pareja.boton(ADMIN, "", "coc:sig")
    assert "2 porción(es) en la nevera" in res.pantalla.texto
    assert any(a.para == ANA and "listo!" in a.texto for a in res.avisos)
    assert pareja.db.jugador(ANA).accion is None


def test_sin_gas_no_se_cocina(solo):
    llenar_despensa(solo, huevos=2, pan=1)
    h = hogar(solo)
    h.pendientes = json.dumps([{"clave": "gas", "monto": 33}])
    solo.db.guardar_hogar(h)
    assert "cortaron el gas" in solo.boton(ADMIN, "", "coc:huevos:1").alerta


# --- comer de la nevera y táper ------------------------------------------------------------

def test_comer_de_la_nevera_es_gratis(solo):
    h = hogar(solo)
    h.nevera = json.dumps({"pasta": 1})
    solo.db.guardar_hogar(h)
    poner(solo, ADMIN, hambre=20)
    res = solo.boton(ADMIN, "", "a:comer")
    assert "a:comer:pasta" in datos(res.pantalla) and "a:domicilio" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "a:comer:pasta")
    assert "gratis" not in res.pantalla.texto and "💵" not in res.pantalla.texto
    res = solo.boton(ADMIN, "", "as:comer:pasta")
    assert "Empezó" in res.pantalla.texto
    assert json.loads(hogar(solo).nevera) == {} and hogar(solo).cuenta == 1500


def test_tapper_para_el_trabajo(solo, reloj):
    h = hogar(solo)
    h.nevera = json.dumps({"arroz_pollo": 2})
    solo.db.guardar_hogar(h)
    res = solo.boton(ADMIN, "", "a:taper")
    assert "taper:arroz_pollo" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "taper:arroz_pollo")
    assert "Táper listo con arroz con pollo" in res.pantalla.texto
    assert solo.db.jugador(ADMIN).taper == "arroz_pollo"
    reloj.avanzar(6)
    solo.boton(ADMIN, "", "sim")
    solo.boton(ADMIN, "", "tomar:recepcion")
    poner(solo, ADMIN, **LLENO)
    poner(solo, ADMIN, hambre=50)
    res = solo.boton(ADMIN, "", "trabajar:8")
    assert "trabajar:8:con" in datos(res.pantalla)
    res = solo.boton(ADMIN, "", "trabajar:8:con")
    assert "Lleva su táper de arroz con pollo" in res.pantalla.texto
    assert solo.db.jugador(ADMIN).taper == ""
    reloj.avanzar(8 * 60 + 1)
    solo.tick()
    assert nec(solo, ADMIN)["hambre"] == pytest.approx(50 + 40 - 48, abs=0.5)


def test_trabajar_sin_comida_da_mas_hambre(solo, reloj):
    solo.boton(ADMIN, "", "tomar:recepcion")
    poner(solo, ADMIN, **LLENO)
    res = solo.boton(ADMIN, "", "trabajar:8:sin")
    assert "Va sin comida" in res.pantalla.texto
    reloj.avanzar(8 * 60 + 1)
    solo.tick()
    assert nec(solo, ADMIN)["hambre"] == pytest.approx(100 - 6 * 8 * 1.5, abs=0.5)
