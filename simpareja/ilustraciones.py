"""Ilustraciones de las acciones (versión 0.40): dibujos que llegan con los mensajitos de la narración.

Se dibujan con Pillow, en estilo plano y suave, según el momento real del día del jugador (mañana, tarde,
atardecer o noche: cielo, sol o luna y estrellas, farolas encendidas) y con una o dos figuras (con los
colores de cada personaje). Son JPEG pequeños (unos 25 KB) para gastar pocos datos.

`dibujar(clave)` recibe "escena:momento:figuras", por ejemplo "parque_banca:noche:hm" (h = hombre,
m = mujer, n = no binario; una letra si va solo).
"""

from __future__ import annotations

import io
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from .narracion import MOMENTOS

ANCHO, ALTO = 640, 400
X = 2  # se dibuja al doble y se reduce: bordes suaves
W, H = ANCHO * X, ALTO * X
HORIZONTE = int(H * 0.58)

PALETAS = {
    "manana": dict(cielo=((126, 192, 250), (214, 238, 255)), colina=((150, 205, 130), (120, 185, 105)),
                   suelo=(126, 196, 104), camino=(232, 214, 170), copa=((86, 160, 80), (106, 182, 92)),
                   tronco=(124, 86, 58), agua=(98, 170, 220), banca=(150, 100, 64), luz=1.0),
    "tarde": dict(cielo=((92, 160, 236), (190, 224, 252)), colina=((140, 196, 118), (112, 176, 96)),
                  suelo=(118, 186, 96), camino=(226, 206, 160), copa=((80, 152, 74), (100, 172, 86)),
                  tronco=(118, 82, 54), agua=(86, 156, 210), banca=(144, 96, 60), luz=1.0),
    "atardecer": dict(cielo=((104, 86, 160), (255, 168, 112)), colina=((126, 120, 110), (98, 104, 84)),
                      suelo=(96, 132, 76), camino=(206, 170, 128), copa=((66, 112, 62), (84, 128, 70)),
                      tronco=(96, 64, 46), agua=(180, 130, 140), banca=(122, 80, 52), luz=0.82),
    "noche": dict(cielo=((10, 16, 44), (44, 54, 104)), colina=((34, 50, 64), (26, 44, 52)),
                  suelo=(30, 62, 48), camino=(86, 84, 92), copa=((22, 52, 42), (30, 64, 50)),
                  tronco=(52, 40, 36), agua=(34, 52, 96), banca=(76, 54, 42), luz=0.55),
}
ROPA = {"h": (66, 112, 206), "m": (226, 92, 138), "n": (52, 170, 150)}
PIEL = {"h": (214, 164, 126), "m": (176, 118, 84), "n": (198, 148, 108)}
PELO = {"h": (60, 40, 30), "m": (40, 26, 22), "n": (120, 70, 40)}
ESCENAS = ("parque_llegada", "parque_patos", "parque_banca", "parque_regreso")


def _oscurecer(color, f: float):
    return tuple(max(0, min(255, round(c * f))) for c in color[:3])


def _mezclar(a, b, t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# --- piezas ------------------------------------------------------------------

def _cielo(img: Image.Image, pal: dict, mom: str) -> None:
    d = ImageDraw.Draw(img)
    arriba, abajo = pal["cielo"]
    for y in range(HORIZONTE + 4):
        d.line([(0, y), (W, y)], fill=_mezclar(arriba, abajo, y / HORIZONTE))
    if mom == "noche":
        rng = random.Random(11)
        for _ in range(70):
            x, y, r = rng.randrange(W), rng.randrange(int(HORIZONTE * 0.85)), rng.choice((2, 2, 3, 4))
            brillo = rng.randint(170, 255)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(brillo, brillo, min(255, brillo + 20)))
        _brillo(img, (W * 0.80, H * 0.18), 120, (240, 236, 200), 70)
        cx, cy, r = W * 0.80, H * 0.18, 58
        luna = Image.new("L", img.size, 0)  # luna creciente: un círculo menos otro corrido
        m = ImageDraw.Draw(luna)
        m.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        m.ellipse([cx - r + 30, cy - r - 18, cx + r + 30, cy + r - 18], fill=0)
        img.paste((246, 240, 204, 255), (0, 0) + img.size, luna)
    else:
        sol = {"manana": (W * 0.18, H * 0.20, (255, 236, 150)), "tarde": (W * 0.78, H * 0.14, (255, 244, 170)),
               "atardecer": (W * 0.70, HORIZONTE - 40, (255, 150, 80))}[mom]
        _brillo(img, sol[:2], 170, sol[2], 90)
        d = ImageDraw.Draw(img)
        r = 62 if mom != "atardecer" else 80
        d.ellipse([sol[0] - r, sol[1] - r, sol[0] + r, sol[1] + r], fill=sol[2])
        if mom != "atardecer":
            for cx, cy, s in ((W * 0.40, H * 0.16, 1.0), (W * 0.62, H * 0.28, 0.7)):
                for dx, dy, rr in ((0, 0, 46), (50, -14, 56), (104, 0, 44)):
                    x, y, rr = cx + dx * s, cy + dy * s, rr * s
                    d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 255))


def _brillo(img: Image.Image, centro, radio: float, color, alfa: int) -> None:
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).ellipse([centro[0] - radio, centro[1] - radio, centro[0] + radio, centro[1] + radio],
                                 fill=color + (alfa,))
    capa = capa.filter(ImageFilter.GaussianBlur(radio * 0.45))
    img.alpha_composite(capa)


def _paisaje(img: Image.Image, pal: dict) -> None:
    d = ImageDraw.Draw(img)
    lejos, cerca = pal["colina"]
    d.ellipse([-W * 0.3, HORIZONTE - 120, W * 0.6, HORIZONTE + 260], fill=lejos)
    d.ellipse([W * 0.35, HORIZONTE - 90, W * 1.3, HORIZONTE + 240], fill=cerca)
    d.rectangle([0, HORIZONTE, W, H], fill=pal["suelo"])


def _camino(d: ImageDraw.ImageDraw, pal: dict) -> None:
    d.polygon([(W * 0.40, H), (W * 0.62, H), (W * 0.53, HORIZONTE), (W * 0.49, HORIZONTE)], fill=pal["camino"])


def _arbol(d: ImageDraw.ImageDraw, x: float, base: float, s: float, pal: dict) -> None:
    oscuro, claro = pal["copa"]
    d.rounded_rectangle([x - 14 * s, base - 120 * s, x + 14 * s, base], radius=6 * s, fill=pal["tronco"])
    for dx, dy, r, c in ((-46, -150, 62, oscuro), (44, -150, 62, oscuro), (0, -205, 74, claro), (0, -140, 70, claro)):
        d.ellipse([x + (dx - r) * s, base + (dy - r) * s, x + (dx + r) * s, base + (dy + r) * s], fill=c)


def _farol(img: Image.Image, x: float, base: float, s: float, encendido: bool) -> None:
    if encendido:
        _brillo(img, (x, base - 236 * s), 150 * s, (255, 214, 120), 110)
    d = ImageDraw.Draw(img)
    d.rectangle([x - 6 * s, base - 230 * s, x + 6 * s, base], fill=(44, 44, 52))
    color = (255, 226, 140) if encendido else (210, 220, 228)
    d.polygon([(x - 26 * s, base - 226 * s), (x + 26 * s, base - 226 * s), (x + 16 * s, base - 268 * s),
               (x - 16 * s, base - 268 * s)], fill=color)
    d.rectangle([x - 30 * s, base - 276 * s, x + 30 * s, base - 266 * s], fill=(44, 44, 52))


def _banca(d: ImageDraw.ImageDraw, x: float, base: float, s: float, pal: dict) -> None:
    madera, hierro = pal["banca"], (52, 52, 60)
    for px in (x - 150 * s, x + 130 * s):
        d.rectangle([px, base - 70 * s, px + 20 * s, base], fill=hierro)
    d.rounded_rectangle([x - 180 * s, base - 84 * s, x + 180 * s, base - 64 * s], radius=6 * s, fill=madera)
    for dy in (-150, -118):
        d.rounded_rectangle([x - 180 * s, base + (dy - 14) * s, x + 180 * s, base + dy * s], radius=6 * s, fill=madera)
    for px in (x - 160 * s, x + 140 * s):
        d.rectangle([px, base - 164 * s, px + 16 * s, base - 70 * s], fill=hierro)


def _persona(d: ImageDraw.ImageDraw, x: float, base: float, s: float, tipo: str, sentada: bool, luz: float) -> None:
    ropa, piel, pelo = (_oscurecer(c, luz) for c in (ROPA[tipo], PIEL[tipo], PELO[tipo]))
    pantalon = _oscurecer((60, 64, 84), luz)
    if sentada:
        cadera = base - 84 * s
        d.rounded_rectangle([x - 18 * s, cadera - 8 * s, x + 46 * s, cadera + 18 * s], radius=10 * s, fill=pantalon)
        d.rounded_rectangle([x + 26 * s, cadera, x + 46 * s, base - 4 * s], radius=8 * s, fill=pantalon)
        torso_abajo = cadera + 6 * s
    else:
        d.rounded_rectangle([x - 22 * s, base - 92 * s, x - 4 * s, base], radius=8 * s, fill=pantalon)
        d.rounded_rectangle([x + 4 * s, base - 92 * s, x + 22 * s, base], radius=8 * s, fill=pantalon)
        torso_abajo = base - 84 * s
    torso_arriba = torso_abajo - 92 * s
    d.rounded_rectangle([x - 32 * s, torso_arriba, x + 32 * s, torso_abajo], radius=24 * s, fill=ropa)
    cy, r = torso_arriba - 30 * s, 30 * s
    if tipo == "m":  # pelo largo
        d.rounded_rectangle([x - 36 * s, cy - 32 * s, x + 36 * s, cy + 46 * s], radius=26 * s, fill=pelo)
    d.ellipse([x - r, cy - r, x + r, cy + r], fill=piel)
    d.chord([x - r - 2 * s, cy - r - 4 * s, x + r + 2 * s, cy + r * 0.5], 180, 360, fill=pelo)
    ojos = _oscurecer((40, 30, 30), luz)
    for dx in (-11, 11):
        d.ellipse([x + (dx - 3.5) * s, cy + 2 * s, x + (dx + 3.5) * s, cy + 9 * s], fill=ojos)
    d.arc([x - 9 * s, cy + 6 * s, x + 9 * s, cy + 20 * s], 20, 160, fill=ojos, width=max(2, int(2.5 * s)))


def _corazon(d: ImageDraw.ImageDraw, x: float, y: float, s: float, color) -> None:
    r = 16 * s
    d.ellipse([x - 2 * r, y - r, x, y + r], fill=color)
    d.ellipse([x, y - r, x + 2 * r, y + r], fill=color)
    d.polygon([(x - 2 * r + 2, y + 4 * s), (x + 2 * r - 2, y + 4 * s), (x, y + 2.6 * r)], fill=color)


def _estanque(img: Image.Image, pal: dict, mom: str) -> None:
    d = ImageDraw.Draw(img)
    caja = [W * 0.18, HORIZONTE + 60, W * 0.82, H - 50]
    d.ellipse(caja, fill=pal["agua"])
    d.ellipse([caja[0] + 60, caja[1] + 24, caja[2] - 140, caja[1] + 50], fill=_mezclar(pal["agua"], (255, 255, 255), 0.25))
    if mom == "noche":  # la luna en el agua
        d.ellipse([W * 0.62, HORIZONTE + 100, W * 0.70, HORIZONTE + 116], fill=(220, 220, 190))


def _pato(d: ImageDraw.ImageDraw, x: float, y: float, s: float, dormido: bool, luz: float) -> None:
    cuerpo, pico = _oscurecer((250, 250, 240), luz), _oscurecer((255, 160, 40), luz)
    d.ellipse([x - 40 * s, y - 22 * s, x + 40 * s, y + 22 * s], fill=cuerpo)
    if dormido:
        d.ellipse([x + 4 * s, y - 34 * s, x + 40 * s, y - 2 * s], fill=cuerpo)
    else:
        d.ellipse([x + 18 * s, y - 56 * s, x + 50 * s, y - 24 * s], fill=cuerpo)
        d.polygon([(x + 48 * s, y - 42 * s), (x + 68 * s, y - 38 * s), (x + 48 * s, y - 32 * s)], fill=pico)
        d.ellipse([x + 34 * s, y - 46 * s, x + 40 * s, y - 40 * s], fill=(30, 30, 30))


# --- escenas -----------------------------------------------------------------

def _figuras(d, img, tipos: str, centro: float, base: float, s: float, sentadas: bool, luz: float) -> None:
    separacion = 74 * s if sentadas else 64 * s
    xs = [centro] if len(tipos) == 1 else [centro - separacion / 2 - 20 * s, centro + separacion / 2 + 20 * s]
    for x, tipo in zip(xs, tipos):
        _persona(d, x - (14 * s if sentadas else 0), base, s, tipo, sentadas, luz)
    if len(tipos) == 2 and not sentadas:  # de la mano
        d.line([(xs[0] + 30 * s, base - 132 * s), (xs[1] - 30 * s, base - 132 * s)],
               fill=_oscurecer(PIEL[tipos[0]], luz), width=int(10 * s))


def _escena(nombre: str, mom: str, tipos: str) -> Image.Image:
    pal = PALETAS[mom]
    luz = pal["luz"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _cielo(img, pal, mom)
    _paisaje(img, pal)
    d = ImageDraw.Draw(img)
    noche = mom == "noche"
    if nombre == "parque_llegada":
        _camino(d, pal)
        _arbol(d, W * 0.12, HORIZONTE + 120, 1.3, pal)
        _arbol(d, W * 0.88, HORIZONTE + 110, 1.2, pal)
        _farol(img, W * 0.30, HORIZONTE + 150, 1.0, noche)
        _farol(img, W * 0.72, HORIZONTE + 120, 0.8, noche)
        _figuras(ImageDraw.Draw(img), img, tipos, W * 0.52, H - 40, 1.25, False, luz)
    elif nombre == "parque_patos":
        _arbol(d, W * 0.08, HORIZONTE + 90, 1.0, pal)
        _arbol(d, W * 0.93, HORIZONTE + 80, 0.9, pal)
        _estanque(img, pal, mom)
        d = ImageDraw.Draw(img)
        for x, y in ((W * 0.36, H * 0.78), (W * 0.50, H * 0.83), (W * 0.62, H * 0.76)):
            _pato(d, x, y, 1.0, noche, luz)
        _figuras(d, img, tipos, W * 0.84, H - 24, 0.95, False, luz)
    elif nombre == "parque_banca":
        _arbol(d, W * 0.20, HORIZONTE + 70, 1.5, pal)
        _arbol(d, W * 0.86, HORIZONTE + 60, 1.2, pal)
        _farol(img, W * 0.80, H - 40, 1.25, noche)
        d = ImageDraw.Draw(img)
        _banca(d, W * 0.46, H - 50, 1.25, pal)
        _figuras(d, img, tipos, W * 0.46, H - 50, 1.25, True, luz)
        if len(tipos) == 2:
            _corazon(d, W * 0.46, H * 0.30, 1.1, (236, 80, 110) if not noche else (250, 120, 150))
    else:  # parque_regreso
        _camino(d, pal)
        _arbol(d, W * 0.20, HORIZONTE + 60, 1.0, pal)
        _arbol(d, W * 0.80, HORIZONTE + 70, 1.1, pal)
        _farol(img, W * 0.36, HORIZONTE + 90, 0.7, noche)
        _farol(img, W * 0.66, HORIZONTE + 90, 0.7, noche)
        _figuras(ImageDraw.Draw(img), img, tipos, W * 0.51, HORIZONTE + 110, 0.55, False, luz)
    return img


@lru_cache(maxsize=64)
def dibujar(clave: str) -> bytes:
    """El JPEG de 'escena:momento:figuras'."""
    nombre, mom, tipos = clave.split(":")
    if nombre not in ESCENAS or mom not in MOMENTOS or not 1 <= len(tipos) <= 2 or set(tipos) - set(ROPA):
        raise ValueError(f"Ilustración desconocida: {clave}")
    img = _escena(nombre, mom, tipos).convert("RGB").resize((ANCHO, ALTO), Image.LANCZOS)
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=78, optimize=True, progressive=True)
    return salida.getvalue()


