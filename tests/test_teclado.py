"""Botones abajo: lógica pura del teclado."""

from simpareja import teclado as TK


def test_separa_los_enlaces_y_los_pone_en_el_texto():
    filas, enlaces = TK.separar([[("📤 Enviar", "https://t.me/share/url?a=1&b=2")], [("❌ Anular", "anular:X"), ("⬅️ Atrás", "invitar")]])
    assert filas == [[["❌ Anular", "anular:X"], ["⬅️ Atrás", "invitar"]]]
    assert TK.texto_con_enlaces("Hola", enlaces) == 'Hola\n\n👉 <a href="https://t.me/share/url?a=1&amp;b=2">📤 Enviar</a>'


def test_el_aviso_va_arriba_sin_repetir_y_con_menu():
    extra = [[["✅ ¡Vamos!", "pj:1:1"], ["❌ Ahora no", "pj:1:0"]]]
    filas = [[["⚡ Acciones", "macc"]], [["❌ Ahora no", "otra"]]]
    vista = TK.mostrar(extra, filas)
    assert vista == [extra[0], [["⚡ Acciones", "macc"]], [TK.MENU]]
    assert TK.mostrar([], filas) == filas  # sin aviso, solo la pantalla


def test_buscar_reconoce_solo_los_botones_que_se_ven():
    estado = {"filas": [[["⚡ Acciones", "macc"]]], "extra": [[["✅ ¡Vamos!", "pj:1:1"]]]}
    assert TK.buscar(estado, "✅ ¡Vamos!") == "pj:1:1"
    assert TK.buscar(estado, "🎮 Menú") == "menu"
    assert TK.buscar(estado, "⚡ Acciones") == "macc"
    assert TK.buscar(estado, "te quiero") is None  # esto es chat
    assert TK.buscar({}, "⚡ Acciones") is None
