# Pantalla original de la Anycubic Kobra Neo (TFT ST7789V 320x240 por SPI)
# como pantalla de Klipper: estado, menus y control con la rueda.
#
# Pines (de pins_ANYCUBIC_KOBRA_NEO.h / bsp_spi_tft.h de Anycubic):
#   SCK PC5, MOSI PC4, CS PB1, DC PB0, retroiluminacion PC0,
#   rueda PB10/PB3, pulsador PB4.
# Necesita el firmware de placa con SPI (parche hc32f460, ver LEEME.md).
#
# Rueda: girar = mover / cambiar; pulsar = entrar / aceptar;
# mantener ~1 s = volver / deshacer; mantener 2 s = confirmar lo peligroso.
# La pulsacion larga actua en cuanto se cumple el tiempo, sin esperar a soltar.
# Sin tocar la rueda 60 s en un menu, vuelve sola a la pantalla de estado.
#
# Copyright (C) 2026  Abraham
# This file may be distributed under the terms of the GNU GPLv3 license.
import json, logging, os, socket, struct, threading, time, zlib
import urllib.parse, urllib.request

BACKGROUND_PRIORITY_CLOCK = 0x7fffffff00000000
ANCHO, ALTO = 320, 240
TROZO = 48          # bytes por mensaje spi_send (un mensaje Klipper son 64)
RELLENO_MAX = 512   # pixeles por spi_fill: con 2048 la placa tardaba en confirmar (retransmisiones)
ESCALA_MAX = 4      # mayor escala que acepta spi_glyph
MINI_X, MINI_Y, MINI_LADO = 244, 86, 68   # vista previa del G-code en el estado
LARGO, MUY_LARGO = 0.8, 2.0   # pulsacion larga: volver / confirmar lo peligroso


def rgb(r, g, b):
    # RGB565 (comprobado con la carta de colores: en BGR salian rojo y azul cambiados)
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

NEGRO = rgb(0, 0, 0)
BLANCO = rgb(255, 255, 255)
GRIS = rgb(140, 140, 140)
GRIS_CLARO = rgb(200, 200, 200)
GRIS_OSCURO = rgb(45, 45, 45)
NARANJA = rgb(255, 140, 0)
VERDE = rgb(40, 190, 80)
ROJO = rgb(220, 40, 40)
AZUL = rgb(40, 120, 230)
AMARILLO = rgb(240, 200, 30)
CIAN = rgb(40, 200, 220)
LATON = rgb(210, 160, 40)
BLOQUE = rgb(120, 120, 130)

COLOR_ESTADO = {
    'printing': (VERDE, 'IMPRIMIENDO'), 'paused': (AMARILLO, 'EN PAUSA'),
    'complete': (AZUL, 'TERMINADA'), 'cancelled': (GRIS, 'CANCELADA'),
    'error': (ROJO, 'ERROR'), 'standby': (GRIS_OSCURO, 'LISTA'),
}

# Idioma de la pantalla: los textos se escriben en espanol y se traducen al
# pintar (Campo.poner) o, si llevan numeros dentro, con _() antes de formatear.
IDIOMAS = {'es': 'Espa\xf1ol', 'en': 'English'}
IDIOMA = ['en']
EN = {
    'IMPRIMIENDO': 'PRINTING', 'EN PAUSA': 'PAUSED', 'TERMINADA': 'FINISHED',
    'CANCELADA': 'CANCELLED', 'LISTA': 'READY', 'Lista': 'Ready',
    'Sin archivo': 'No file', 'BOQUILLA': 'NOZZLE', 'CAMA': 'BED',
    'Tiempo %s  Resta %s': 'Time %s  Left %s',
    'Espera: cama a %d\xb0 (quitar <35\xb0)': 'Wait: bed at %d\xb0 (remove <35\xb0)',
    'Ya puedes quitar la pieza': 'You can remove the part',
    'Z %.2f  Vel %d%%  Vent %d%%': 'Z %.2f  Spd %d%%  Fan %d%%',
    '%d\xb0 apag': '%d\xb0 off',
    '↻ Mover  ● Entrar  ●1s Volver': '↻ Move  ● Enter  ●1s Back',
    'antes %s  ● Aplicar  ●1s Deshacer': 'was %s  ● Apply  ●1s Undo',
    'Mant\xe9n 2 s para confirmar': 'Hold 2 s to confirm',
    'No, volver': 'No, go back',
    '↻ Elegir  ● Aceptar': '↻ Choose  ● Accept',
    '  S\xed: mantener 2 s': '  Yes: hold 2 s',
    'MEN\xda': 'MENU', 'Volver al estado': 'Back to status',
    'Ajustes en vivo': 'Live tuning', 'Temperaturas': 'Temperatures',
    'Reanudar': 'Resume', 'Pausa': 'Pause', 'Cancelar impresi\xf3n': 'Cancel print',
    '\xbfCANCELAR?': 'CANCEL?', 'Va por el %d%%': 'Progress: %d%%',
    'No se puede reanudar.': 'It cannot be resumed.', 'S\xed, cancelar': 'Yes, cancel',
    'Archivos': 'Files', 'Filamento': 'Filament', 'Mover ejes': 'Move axes',
    'Apagar luz': 'Screen off', 'Informaci\xf3n': 'Information',
    'AJUSTES': 'TUNING', 'Velocidad': 'Speed', 'Flujo': 'Flow', 'Ventilador': 'Fan',
    'Ajuste fino Z': 'Z fine tune', 'Ajuste Z': 'Z offset',
    'Boquilla': 'Nozzle', 'Cama': 'Bed',
    '↻ Elegir  ● Editar  ●1s Volver': '↻ Choose  ● Edit  ●1s Back',
    'TEMPERATURAS': 'TEMPERATURES', 'PLA estable': 'PLA stable',
    'Calentando: PLA estable': 'Heating: PLA stable', 'PLA r\xe1pido': 'PLA fast',
    'Calentando: PLA r\xe1pido': 'Heating: PLA fast', 'Precalentar cama': 'Preheat bed',
    'Calentando la cama': 'Heating the bed', 'Enfriar todo': 'Cool down all',
    'Calentadores apagados': 'Heaters off',
    '↻ Elegir  ● Aplicar  ●1s Volver': '↻ Choose  ● Apply  ●1s Back',
    'MOVER': 'MOVE', 'Primero haz el origen': 'Home the axes first', 'Paso': 'Step',
    'Origen (G28)': 'Home (G28)', 'Haciendo origen': 'Homing',
    'Desactivar motores': 'Disable motors', 'Motores libres': 'Motors disabled',
    'No disponible imprimiendo': 'Not available while printing',
    'mueve %s': 'moving %s', '↻ Mover %s  ● Listo': '↻ Move %s  ● Done',
    'sin imprimir': 'not printing',
    'ARCHIVOS': 'FILES', '\xbfIMPRIMIR?': 'PRINT?', '\xbfCama limpia?': 'Is the bed clean?',
    'S\xed, imprimir': 'Yes, print', 'No hay archivos': 'No files',
    '↻ Elegir  ● Imprimir  ●1s Volver': '↻ Choose  ● Print  ●1s Back',
    'FILAMENTO': 'FILAMENT', 'Calentando para %s': 'Heating to %s',
    'descargar': 'unload', 'cargar': 'load',
    'paso 1 de 3': 'step 1 of 3', 'paso 2 de 3': 'step 2 of 3', 'paso 3 de 3': 'step 3 of 3',
    '●1s Cancelar (apaga la boquilla)': '●1s Cancel (nozzle off)',
    'Sacando...': 'Unloading...', 'Metiendo y purgando...': 'Loading and purging...',
    'Espera, no tires del filamento': "Wait, don't pull the filament",
    'Hecho: ya puedes sacarlo': 'Done: you can pull it out',
    'Hecho: filamento cargado': 'Done: filament loaded',
    'Boquilla a %d\xb0 primero': 'Nozzle to %d\xb0 first',
    'Descargar (sacar)': 'Unload (pull out)', 'Cargar (meter y purgar)': 'Load (feed and purge)',
    '↻ Elegir  ● Empezar  ●1s Salir': '↻ Choose  ● Start  ●1s Exit',
    'Placa': 'Board',
    '● Men\xfa  ↻ Ajustes': '● Menu  ↻ Tuning', '   ● Men\xfa': '   ● Menu',
    'BLAN AMAR CIAN VERD MAGE ROJO AZUL NEGR': 'WHIT YELL CYAN GREN MAGE RED  BLUE BLCK',
    'CARTA  ': 'CHART  ', 'ROJO ': 'RED ', 'VERDE ': 'GREEN ', 'AZUL ': 'BLUE ',
    'NARANJA': 'ORANGE', 'Toca la rueda para salir': 'Touch the knob to exit',
}


def _(texto):
    """Traduce un texto de la pantalla al idioma elegido (si no esta, se queda igual)."""
    if IDIOMA[0] == 'en' and isinstance(texto, str):
        return EN.get(texto, texto)
    return texto


# Secuencia de arranque del ST7789V tal cual la usa el firmware de Anycubic
SECUENCIA = [
    (0x01, b'', 0.15),                      # reset por software
    (0x11, b'', 0.12),                      # salir de reposo
    (0x36, b'\xb0', 0), (0x3a, b'\x05', 0),
    (0xb2, b'\x05\x05\x00\x33\x33', 0), (0xb7, b'\x35', 0),
    (0xbb, b'\x28', 0), (0xc0, b'\x2c', 0), (0xc2, b'\x01', 0),
    (0xc3, b'\x0b', 0), (0xc4, b'\x20', 0), (0xc6, b'\x0f', 0),
    (0xd0, b'\xa4\xa1', 0),
    (0x29, b'', 0),                         # encender
]

# Curvas de brillo (gamma positiva 0xE0 y negativa 0xE1); se prueban con TFT_CARTA GAMMA=...
GAMMAS = {
    'anycubic': (b'\xd0\x01\x08\x0f\x11\x2a\x36\x55\x44\x3a\x0b\x06\x11\x20',
                 b'\xd0\x02\x07\x0a\x0b\x18\x34\x43\x4a\x2b\x1b\x1c\x22\x1f'),
    'estandar': (b'\xd0\x04\x0d\x11\x13\x2b\x3f\x54\x4c\x18\x0d\x0b\x1f\x23',
                 b'\xd0\x04\x0c\x11\x13\x2c\x3f\x44\x51\x2f\x1f\x1f\x20\x23'),
    'viva':     (b'\xd0\x00\x02\x07\x0a\x28\x32\x44\x42\x06\x0e\x12\x14\x17',
                 b'\xd0\x00\x02\x07\x0a\x28\x31\x54\x47\x0e\x1c\x17\x1b\x1e'),
}


######################################################################
# Dibujo (independiente de Klipper: tambien lo usa el simulador)
######################################################################

class Lienzo:
    """Convierte primitivas de dibujo en ventanas + pixeles para el ST7789.
    'salida' necesita: comando(c, datos) y datos(bytes)."""
    def __init__(self, salida, fuente):
        self.salida = salida
        self.fuente = fuente
        self.pendiente = []          # lista de (bytes_estimados, funcion)
    def _ventana(self, x0, y0, x1, y1):
        self.salida.comando(0x2a, bytes([x0 >> 8, x0 & 0xff, x1 >> 8, x1 & 0xff]))
        self.salida.comando(0x2b, bytes([y0 >> 8, y0 & 0xff, y1 >> 8, y1 & 0xff]))
        self.salida.comando(0x2c, b'')
    def _acelerada(self):
        return getattr(self.salida, 'acelerada', False)
    def rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        if self._acelerada():
            # la placa genera los pixeles: por el USB solo va la orden
            def hacer():
                self._ventana(x, y, x + w - 1, y + h - 1)
                self.salida.rellenar(color, w * h)
            self.pendiente.append((60 + 16 * (-(-w * h // RELLENO_MAX)), hacer))
            return
        def hacer():
            self._ventana(x, y, x + w - 1, y + h - 1)
            fila = bytes([color >> 8, color & 0xff]) * w
            filas = max(1, 4096 // len(fila))
            for y0 in range(0, h, filas):
                self.salida.datos(fila * min(filas, h - y0))
        self.pendiente.append((w * h * 2 + 20, hacer))
    def imagen(self, x, y, w, h, pix):
        """pix: w*h pixeles RGB565 (2 bytes, big endian), fila a fila."""
        acel = self._acelerada()
        def hacer():
            self._ventana(x, y, x + w - 1, y + h - 1)
            if not acel:
                self.salida.datos(pix)
                return
            # los tramos largos de un mismo color (el fondo) los rellena la placa
            n, i, crudo = len(pix) // 2, 0, 0
            while i < n:
                j = i + 1
                while j < n and pix[2 * j:2 * j + 2] == pix[2 * i:2 * i + 2]:
                    j += 1
                if j - i >= 12:
                    if crudo < i:
                        self.salida.datos(pix[2 * crudo:2 * i])
                    self.salida.rellenar((pix[2 * i] << 8) | pix[2 * i + 1], j - i)
                    crudo = j
                i = j
            if crudo < n:
                self.salida.datos(pix[2 * crudo:])
        self.pendiente.append((len(pix) + 60, hacer))
    def caracter(self, x, y, c, escala, tinta, fondo):
        if self._acelerada() and escala <= ESCALA_MAX:
            def hacer():
                self._ventana(x, y, x + 8 * escala - 1, y + 16 * escala - 1)
                self.salida.glifo(tinta, fondo, escala, self.fuente[c])
            self.pendiente.append((80, hacer))
            return
        def hacer():
            glifo = self.fuente[c]
            t = bytes([tinta >> 8, tinta & 0xff]) * escala
            f = bytes([fondo >> 8, fondo & 0xff]) * escala
            filas = []
            for b in glifo:
                fila = b''.join(t if b & (0x80 >> i) else f for i in range(8))
                filas.append(fila * escala)
            self._ventana(x, y, x + 8 * escala - 1, y + 16 * escala - 1)
            self.salida.datos(b''.join(filas))
        self.pendiente.append((8 * 16 * escala * escala * 2 + 20, hacer))
    def volcar(self, presupuesto):
        """Ejecuta operaciones pendientes hasta gastar 'presupuesto' bytes."""
        gastado = 0
        while self.pendiente and gastado < presupuesto:
            coste, hacer = self.pendiente.pop(0)
            hacer()
            gastado += coste
        return gastado


# Simbolos que la fuente VGA tiene en los codigos bajos (el codec cp437 de
# Python no los traduce) y mayusculas acentuadas que la fuente no tiene.
SIMBOLOS = {'\u25ba': 0x10, '\u25c4': 0x11, '\u25cf': 0x07, '\u21bb': 0x12,
            '\u203a': 0xaf, '\xc1': 0x41, '\xcd': 0x49, '\xd3': 0x4f, '\xda': 0x55}

def png_a_rgb565(datos, lado):
    """PNG de 8 bits RGB/RGBA sin entrelazar (las miniaturas de Orca) ->
    (ancho, alto, pixeles RGB565) reducido para caber en lado x lado,
    promediando y mezclando la transparencia sobre negro."""
    if datos[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("no es PNG")
    pos, idat, cab = 8, [], None
    while pos + 8 <= len(datos):
        n, tipo = struct.unpack('>I4s', datos[pos:pos + 8])
        cuerpo = datos[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tipo == b'IHDR':
            cab = struct.unpack('>IIBBBBB', cuerpo)
        elif tipo == b'IDAT':
            idat.append(cuerpo)
        elif tipo == b'IEND':
            break
    w, h, prof, tipo_color, _c, _f, entrelazado = cab
    if prof != 8 or tipo_color not in (2, 6) or entrelazado:
        raise ValueError("PNG no soportado (%d bits, tipo %d)" % (prof, tipo_color))
    bpp = 4 if tipo_color == 6 else 3
    crudo = zlib.decompress(b''.join(idat))
    paso = w * bpp
    filas, prev, i = [], bytearray(paso), 0
    for _y in range(h):
        filtro, fila = crudo[i], bytearray(crudo[i + 1:i + 1 + paso])
        i += 1 + paso
        for x in range(paso):
            a = fila[x - bpp] if x >= bpp else 0
            b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
            if filtro == 1:
                fila[x] = (fila[x] + a) & 255
            elif filtro == 2:
                fila[x] = (fila[x] + b) & 255
            elif filtro == 3:
                fila[x] = (fila[x] + ((a + b) >> 1)) & 255
            elif filtro == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                fila[x] = (fila[x] + (a if pa <= pb and pa <= pc else
                                      b if pb <= pc else c)) & 255
        filas.append(fila)
        prev = fila
    k = min(1., float(lado) / max(w, h))
    W, H = max(1, int(round(w * k))), max(1, int(round(h * k)))
    out = bytearray()
    for Y in range(H):
        y0, y1 = int(Y * h / H), max(int(Y * h / H) + 1, int((Y + 1) * h / H))
        for X in range(W):
            x0, x1 = int(X * w / W), max(int(X * w / W) + 1, int((X + 1) * w / W))
            r = g = b = cuenta = 0
            for yy in range(y0, y1):
                fila = filas[yy]
                for xx in range(x0, x1):
                    o = xx * bpp
                    al = fila[o + 3] if bpp == 4 else 255
                    r += fila[o] * al
                    g += fila[o + 1] * al
                    b += fila[o + 2] * al
                    cuenta += 255
            col = rgb(r // cuenta, g // cuenta, b // cuenta)
            out += bytes((col >> 8, col & 255))
    return W, H, bytes(out)


def a_cp437(texto):
    cod = []
    for ch in texto:
        if ch in SIMBOLOS:
            cod.append(SIMBOLOS[ch])
        else:
            cod.extend(ch.encode('cp437', errors='replace'))
    return cod


class Campo:
    """Texto en una posicion fija; solo redibuja los caracteres que cambian.
    Un espacio solo depende del fondo (la tinta no se ve)."""
    def __init__(self, lienzo, x, y, ancho, escala=1, tinta=BLANCO, fondo=NEGRO):
        self.l, self.x, self.y, self.ancho, self.escala = lienzo, x, y, ancho, escala
        self.tinta, self.fondo = tinta, fondo
        self.actual = [None] * ancho
    def poner(self, texto, tinta=None, fondo=None, alinear='izq'):
        tinta = self.tinta if tinta is None else tinta
        fondo = self.fondo if fondo is None else fondo
        cod = a_cp437(_(texto))[:self.ancho]
        hueco = self.ancho - len(cod)
        if alinear == 'der':
            cod = [32] * hueco + cod
        elif alinear == 'centro':
            cod = [32] * (hueco // 2) + cod + [32] * (hueco - hueco // 2)
        else:
            cod = cod + [32] * hueco
        for i, c in enumerate(cod):
            nuevo = (c, None if c == 32 else tinta, fondo)
            if self.actual[i] != nuevo:
                self.actual[i] = nuevo
                self.l.caracter(self.x + i * 8 * self.escala, self.y, c,
                                self.escala, tinta, fondo)
    def olvidar(self):
        self.actual = [None] * self.ancho
    def asumir(self, fondo):
        """La zona acaba de pintarse lisa con 'fondo' (no hace falta dibujar espacios)."""
        self.actual = [(32, None, fondo)] * self.ancho


def hms(seg):
    """Duracion sin ambiguedad: 3h35, 12m, 45s."""
    seg = int(max(0, seg))
    h, m = divmod(seg // 60, 60)
    if h:
        return "%dh%02d" % (h, m)
    return "%dm" % m if m else "%ds" % seg


def temp_txt(actual, objetivo):
    if objetivo > 0:
        return "%d/%d\xb0" % (round(actual), round(objetivo))
    return _("%d\xb0 apag") % round(actual)


class Cabecera:
    """Barra de arriba, compartida por el estado y los menus."""
    def __init__(self, lienzo):
        L = self.l = lienzo
        self.color = None
        self.izq = Campo(L, 8, 2, 13, 2)
        self.der_g = Campo(L, 216, 2, 6, 2)       # p. ej. "37%"
        self.der_p = Campo(L, 216, 10, 12, 1)     # p. ej. "paso 1 de 3"
    def olvidar(self):
        self.color = None
    def poner(self, color, texto, derecha='', grande=False):
        if color != self.color:
            self.color = color
            self.l.rect(0, 0, ANCHO, 36, color)
            for c in (self.izq, self.der_g, self.der_p):
                c.asumir(color)
        tinta = NEGRO if color == AMARILLO else BLANCO
        self.izq.poner(texto, tinta, color)
        if grande:
            self.der_p.poner('', tinta, color)
            self.der_g.poner(derecha, tinta, color, alinear='der')
        else:
            self.der_g.poner('', tinta, color)
            self.der_p.poner(derecha, tinta, color, alinear='der')


class PantallaEstado:
    """Pantalla de estado (la que se ve casi siempre)."""
    def __init__(self, lienzo, cab, pie):
        self.l, self.cab, self.pie = lienzo, cab, pie
        self.barra_px = None
        L = lienzo
        self.fichero = Campo(L, 8, 42, 38, 1, GRIS)
        self.et_boq = Campo(L, 8, 96, 9, 1, NARANJA)
        self.boq = Campo(L, 104, 88, 8, 2)        # hasta x=232: a la derecha va la miniatura
        self.et_cama = Campo(L, 8, 136, 9, 1, CIAN)
        self.cama = Campo(L, 104, 128, 8, 2)
        self.mini_clave = None
        self.tiempo = Campo(L, 8, 168, 38, 1)
        self.linea_z = Campo(L, 8, 188, 38, 1)
        self.campos = [self.fichero, self.et_boq, self.boq, self.et_cama,
                       self.cama, self.tiempo, self.linea_z]
    def asumir_vacia(self):
        for c in self.campos:
            c.asumir(NEGRO)
        self.barra_px = None
        self.mini_clave = None
    def _miniatura(self, mini):
        """Vista previa del G-code (si la trae) a la derecha de las temperaturas."""
        clave = mini[0] if mini else None
        if clave == self.mini_clave:
            return
        if self.mini_clave is not None:
            self.l.rect(MINI_X, MINI_Y, MINI_LADO, MINI_LADO, NEGRO)
        if mini:
            _clave, w, h, pix = mini
            self.l.imagen(MINI_X + (MINI_LADO - w) // 2, MINI_Y + (MINI_LADO - h) // 2,
                          w, h, pix)
        self.mini_clave = clave
    def salir(self):
        """Borra solo lo que hay pintado (letras y barra)."""
        for c in self.campos:
            c.poner('')
        self._miniatura(None)
        if self.barra_px is not None:
            self.l.rect(8, 62, 304, 14, NEGRO)
            self.barra_px = None
    def _barra(self, progreso):
        x, y, w, h = 8, 62, 304, 14
        px = int(round(w * max(0., min(1., progreso))))
        if self.barra_px is None:
            self.l.rect(x, y, w, h, GRIS_OSCURO)
            self.barra_px = 0
        if px > self.barra_px:
            self.l.rect(x + self.barra_px, y, px - self.barra_px, h, VERDE)
        elif px < self.barra_px:
            self.l.rect(x + px, y, self.barra_px - px, h, GRIS_OSCURO)
        self.barra_px = px
    def pintar(self, s, pie):
        estado = s['estado']
        color, nombre = COLOR_ESTADO.get(estado, (GRIS_OSCURO, estado.upper()))
        imprimiendo = estado in ('printing', 'paused')
        pct = "%d%%" % int(s['progreso'] * 100) if imprimiendo else ""
        if estado == 'complete':
            pct = "100%"
        self.cab.poner(color, nombre, pct, grande=True)
        self._miniatura(s.get('miniatura') if estado in ('printing', 'paused', 'complete')
                        else None)
        if estado == 'error' and s['error']:
            self.fichero.poner(s['error'], ROJO)
        else:
            self.fichero.poner(s['fichero'] or "Sin archivo", GRIS)
        self._barra(1. if estado == 'complete' else
                    (s['progreso'] if imprimiendo else 0.))
        self.et_boq.poner("BOQUILLA")
        self.boq.poner(temp_txt(s['boq'], s['boq_obj']),
                       NARANJA if s['boq_obj'] > 0 else BLANCO)
        self.et_cama.poner("CAMA")
        self.cama.poner(temp_txt(s['cama'], s['cama_obj']),
                        CIAN if s['cama_obj'] > 0 else BLANCO)
        if imprimiendo:
            # Tiempo desde el inicio (calentar incluido). Resta: como Fluidd
            # (por fichero) cuando ya hay avance; antes, la del laminador.
            p, dur = s['progreso'], s['duracion']
            if dur > 0 and p > 0.05:
                resta = hms(dur / p - dur)
            elif s.get('estimado'):
                resta = hms(max(0., s['estimado'] - dur))
            else:
                resta = "--"
            self.tiempo.poner(_("Tiempo %s  Resta %s")
                              % (hms(s.get('total', dur)), resta))
        elif estado == 'complete':
            if s['cama'] > 35:
                self.tiempo.poner(_("Espera: cama a %d\xb0 (quitar <35\xb0)")
                                  % round(s['cama']), CIAN)
            else:
                self.tiempo.poner("Ya puedes quitar la pieza", VERDE)
        else:
            self.tiempo.poner("")
        self.linea_z.poner(_("Z %.2f  Vel %d%%  Vent %d%%") % (
            s['z'], round(s['velocidad'] * 100), round(s['ventilador'] * 100)))
        self.pie.poner(pie)


class Plantilla:
    """Rejilla comun de todos los menus: cabecera, 7 filas y pie.
    Al pasar de un menu a otro solo se redibujan las letras que cambian."""
    FILAS = 7
    def __init__(self, lienzo, cab, pie):
        L = self.l = lienzo
        self.cab, self.pie = cab, pie
        self.marca = [Campo(L, 4, 44 + i * 24, 1) for i in range(self.FILAS)]
        self.izq = [Campo(L, 16, 44 + i * 24, 26) for i in range(self.FILAS)]
        self.der = [Campo(L, 216, 44 + i * 24, 12) for i in range(self.FILAS)]
        self.antes = Campo(L, 8, 64, 38, 1, GRIS)
        self.grande = Campo(L, 48, 92, 7, 4, NARANJA)
        self.barra_sel = None
        self.barra_val = None
        self.modo_grande = False
    def _campos(self):
        return self.marca + self.izq + self.der + [self.antes, self.grande]
    def asumir_vacia(self):
        for c in self._campos():
            c.asumir(NEGRO)
        self.barra_sel = self.barra_val = None
        self.modo_grande = False
    def salir(self):
        for c in self._campos():
            c.poner('')
        self._barra_seleccion(None)
        self._barra_valor(None)
        self.modo_grande = False
    def pintar(self, m, color_estado=GRIS_OSCURO):
        self.cab.poner(m.get('color') or color_estado, m['titulo'], m.get('derecha', ''))
        grande = m.get('grande')
        if grande is not None:
            if not self.modo_grande:
                self._borrar_filas()
                self.modo_grande = True
            self.antes.poner(grande.get('antes', ''), alinear='centro')
            self.grande.poner(grande['valor'], grande.get('color', NARANJA),
                              alinear='centro')
            self._barra_valor(grande.get('barra'))
        else:
            if self.modo_grande:
                self.antes.poner('')
                self.grande.poner('')
                self._barra_valor(None)
                self.modo_grande = False
            filas = m.get('filas', [])
            sel = m.get('sel')
            for i in range(self.FILAS):
                if i < len(filas):
                    f = filas[i]
                    activa = (i == sel)
                    tinta = NARANJA if activa else f.get('color', BLANCO)
                    self.marca[i].poner('\u25ba' if activa else '', NARANJA)
                    self.izq[i].poner(f.get('izq', ''), tinta)
                    self.der[i].poner(f.get('der', ''), f.get('der_color') or
                                      (tinta if activa else GRIS_CLARO), alinear='der')
                else:
                    self.marca[i].poner('')
                    self.izq[i].poner('')
                    self.der[i].poner('')
            self._barra_seleccion(sel if sel is not None and sel < len(filas) else None)
        self.pie.poner(m.get('pie', ''))
    def _borrar_filas(self):
        for i in range(self.FILAS):
            self.marca[i].poner('')
            self.izq[i].poner('')
            self.der[i].poner('')
        self._barra_seleccion(None)
    def _barra_seleccion(self, fila):
        if fila == self.barra_sel:
            return
        if self.barra_sel is not None:
            self.l.rect(0, 42 + self.barra_sel * 24, 3, 20, NEGRO)
        if fila is not None:
            self.l.rect(0, 42 + fila * 24, 3, 20, NARANJA)
        self.barra_sel = fila
    def _barra_valor(self, frac):
        x, y, w, h = 32, 168, 256, 10
        if frac is None:
            if self.barra_val is not None:
                self.l.rect(x, y, w, h, NEGRO)
            self.barra_val = None
            return
        px = int(round(w * max(0., min(1., frac))))
        if self.barra_val is None:
            self.l.rect(x, y, w, h, GRIS_OSCURO)
            self.barra_val = 0
        if px > self.barra_val:
            self.l.rect(x + self.barra_val, y, px - self.barra_val, h, NARANJA)
        elif px < self.barra_val:
            self.l.rect(x + px, y, self.barra_val - px, h, GRIS_OSCURO)
        self.barra_val = px


######################################################################
# Menus (independientes de Klipper: 'ctx' da estado y acciones)
#   ctx.s        diccionario de estado actual
#   ctx.gcode(script)   ctx.ir(vista)   ctx.atras()   ctx.inicio()
#   ctx.aviso(texto, color)   ctx.apagar_luz()   ctx.archivos()
######################################################################

PIE_LISTA = "↻ Mover  ● Entrar  ●1s Volver"


def submenu(fn):
    fn.submenu = True
    return fn


class Vista:
    titulo = ''
    color = None        # None = el color del estado (no repinta la cabecera)
    def __init__(self, ctx):
        self.ctx = ctx
    def modelo(self):
        return {'titulo': self.titulo, 'color': self.color}
    def girar(self, d, rapido=False):
        pass
    def pulsar(self):
        pass
    def mantener(self, seg):
        self.ctx.atras()
    def umbral_largo(self):
        """Segundos de pulsacion para que salte mantener() sin esperar a soltar."""
        return LARGO


class Lista(Vista):
    """Lista de opciones: cada opcion es (texto, valor_fn|None, accion_fn|None)."""
    def __init__(self, ctx):
        Vista.__init__(self, ctx)
        self.sel = 0
        self.desde = 0
    def opciones(self):
        return []
    def pie(self):
        return PIE_LISTA
    def girar(self, d, rapido=False):
        n = len(self.opciones())
        if n:
            self.sel = max(0, min(n - 1, self.sel + d))
    def pulsar(self):
        ops = self.opciones()
        if ops and ops[self.sel][2] is not None:
            ops[self.sel][2]()
    def modelo(self):
        ops = self.opciones()
        self.sel = min(self.sel, max(0, len(ops) - 1))
        F = Plantilla.FILAS
        if self.sel < self.desde:
            self.desde = self.sel
        elif self.sel >= self.desde + F:
            self.desde = self.sel - F + 1
        filas = []
        for texto, valor, accion in ops[self.desde:self.desde + F]:
            filas.append({'izq': texto, 'der': valor() if valor else
                          ('›' if accion and getattr(accion, 'submenu', False) else '')})
        m = Vista.modelo(self)
        m.update({'filas': filas, 'sel': self.sel - self.desde, 'pie': self.pie()})
        if len(ops) > F:
            m['derecha'] = "%d/%d" % (self.sel + 1, len(ops))
        return m


class Editor(Vista):
    """Cambiar un numero con la rueda en la propia fila de la lista:
    pulsar aplica, mantener deshace."""
    def __init__(self, ctx, padre, titulo, leer, aplicar, paso, minimo, maximo,
                 fmt="%d", unidad="", paso_rapido=None):
        Vista.__init__(self, ctx)
        self.padre, self.titulo = padre, titulo
        self.leer, self.aplicar = leer, aplicar
        self.paso, self.minimo, self.maximo = paso, minimo, maximo
        self.paso_rapido = paso_rapido or paso * 5
        self.fmt, self.unidad = fmt, unidad
        self.antes = leer()
        self.valor = self.antes
    def _txt(self, v):
        return (self.fmt % v) + self.unidad
    def girar(self, d, rapido=False):
        p = self.paso_rapido if rapido else self.paso
        v = round((self.valor + d * p) / self.paso) * self.paso
        self.valor = max(self.minimo, min(self.maximo, v))
    def pulsar(self):
        self.aplicar(self.valor)
        self.ctx.aviso("%s: %s" % (_(self.titulo), self._txt(self.valor)), VERDE)
        self.ctx.atras()
    def modelo(self):
        m = self.padre.modelo()
        fila = self.padre.sel - self.padre.desde
        m['filas'][fila] = dict(m['filas'][fila], der='\u25c4%s\u25ba' % self._txt(self.valor),
                                der_color=AMARILLO)
        m['pie'] = _("antes %s  \u25cf Aplicar  \u25cf1s Deshacer") % self._txt(self.antes)
        return m


class Confirmar(Vista):
    """Si/No. Con peligro=True el 'Si' pide mantener 2 s."""
    def __init__(self, ctx, titulo, lineas, si, accion, peligro=False):
        Vista.__init__(self, ctx)
        self.titulo, self.lineas, self.si = titulo, lineas, si
        self.accion, self.peligro = accion, peligro
        self.color = ROJO if peligro else None
        self.sel = 0
        self.nota = ''
    def girar(self, d, rapido=False):
        self.sel = 1 if d > 0 else 0
        self.nota = ''
    def pulsar(self):
        if self.sel == 0:
            self.ctx.atras()
        elif self.peligro:
            self.nota = "Mant\xe9n 2 s para confirmar"
        else:
            self._hacer()
    def umbral_largo(self):
        return MUY_LARGO if self.sel == 1 and self.peligro else LARGO
    def mantener(self, seg):
        if self.sel == 1 and self.peligro and seg >= 2:
            self._hacer()
        else:
            self.ctx.atras()
    def _hacer(self):
        self.ctx.inicio()
        self.accion()
    def modelo(self):
        m = Vista.modelo(self)
        filas = [{'izq': t, 'color': GRIS_CLARO} for t in self.lineas[:3]]
        while len(filas) < 3:
            filas.append({'izq': ''})
        filas.append({'izq': self.nota, 'color': AMARILLO})
        filas.append({'izq': ''})
        filas.append({'izq': 'No, volver'})
        filas.append({'izq': self.si, 'color': ROJO if self.peligro else BLANCO})
        m.update({'filas': filas, 'sel': 5 + self.sel,
                  'pie': _("↻ Elegir  ● Aceptar") +
                  (_("  S\xed: mantener 2 s") if self.peligro else "")})
        return m


class Menu(Lista):
    titulo = 'MEN\xda'
    def opciones(self):
        c = self.ctx
        s = c.s
        imprime = s['estado'] in ('printing', 'paused')
        ops = [("Volver al estado", None, c.inicio)]
        if imprime:
            ops.append(("Ajustes en vivo", None, submenu(lambda: c.ir(Ajustes(c)))))
            ops.append(("Temperaturas", None, submenu(lambda: c.ir(Temperaturas(c)))))
            if s['estado'] == 'paused':
                ops.append(("Reanudar", None, lambda: (c.gcode("RESUME"), c.inicio())))
            else:
                ops.append(("Pausa", None, lambda: (c.gcode("PAUSE"), c.inicio())))
            ops.append(("Cancelar impresi\xf3n", None, submenu(lambda: c.ir(Confirmar(
                c, '\xbfCANCELAR?', [s['fichero'], _("Va por el %d%%") % int(s['progreso'] * 100),
                                     "No se puede reanudar."],
                "S\xed, cancelar", lambda: c.gcode("CANCEL_PRINT"), peligro=True)))))
        else:
            ops.append(("Archivos", None, submenu(lambda: c.ir(Archivos(c)))))
            ops.append(("Temperaturas", None, submenu(lambda: c.ir(Temperaturas(c)))))
            ops.append(("Filamento", None, submenu(lambda: c.ir(Filamento(c)))))
            ops.append(("Mover ejes", None, submenu(lambda: c.ir(Mover(c)))))
        ops.append(("Apagar luz", None, c.apagar_luz))
        ops.append(("Idioma / Language", lambda: IDIOMAS[IDIOMA[0]], c.cambiar_idioma))
        ops.append(("Informaci\xf3n", None, submenu(lambda: c.ir(Info(c)))))
        return ops
    def modelo(self):
        m = Lista.modelo(self)
        s = self.ctx.s
        if s['estado'] in ('printing', 'paused'):
            m['derecha'] = "● %d%%" % int(s['progreso'] * 100)
        return m


class Ajustes(Lista):
    titulo = 'AJUSTES'
    def opciones(self):
        c, s = self.ctx, self.ctx.s
        def ed(*a, **k):
            return lambda: c.ir(Editor(c, self, *a, **k))
        return [
            ("Velocidad", lambda: "%d %%" % round(s['velocidad'] * 100),
             ed("Velocidad", lambda: round(s['velocidad'] * 100),
                lambda v: c.gcode("M220 S%d" % v), 5, 50, 200, unidad="%", paso_rapido=25)),
            ("Flujo", lambda: "%d %%" % round(s['flujo'] * 100),
             ed("Flujo", lambda: round(s['flujo'] * 100),
                lambda v: c.gcode("M221 S%d" % v), 1, 80, 120, unidad="%")),
            ("Ventilador", lambda: "%d %%" % round(s['ventilador'] * 100),
             ed("Ventilador", lambda: round(s['ventilador'] * 100),
                lambda v: c.gcode("M106 S%d" % round(v * 2.55)), 5, 0, 100, unidad="%")),
            ("Ajuste fino Z", lambda: "%.3f" % s['z_offset'],
             ed("Ajuste Z", lambda: s['z_offset'],
                lambda v: c.gcode("SET_GCODE_OFFSET Z=%.3f MOVE=1" % v),
                0.005, -0.3, 0.3, fmt="%.3f", paso_rapido=0.025)),
            ("Boquilla", lambda: "%d\xb0" % round(s['boq_obj']),
             ed("Boquilla", lambda: round(s['boq_obj']),
                lambda v: c.gcode("M104 S%d" % v), 1, 0, 260, unidad="\xb0", paso_rapido=5)),
            ("Cama", lambda: "%d\xb0" % round(s['cama_obj']),
             ed("Cama", lambda: round(s['cama_obj']),
                lambda v: c.gcode("M140 S%d" % v), 1, 0, 100, unidad="\xb0", paso_rapido=5)),
        ]
    def pie(self):
        return "↻ Elegir  ● Editar  ●1s Volver"


class Temperaturas(Lista):
    titulo = 'TEMPERATURAS'
    def opciones(self):
        c, s = self.ctx, self.ctx.s
        def fija(b, k, txt):
            def f():
                if b is not None:
                    c.gcode("M104 S%d" % b)
                if k is not None:
                    c.gcode("M140 S%d" % k)
                c.aviso(txt, VERDE)
            return f
        return [
            ("PLA estable", lambda: "205 / 60", fija(205, 60, "Calentando: PLA estable")),
            ("PLA r\xe1pido", lambda: "215 / 60", fija(215, 60, "Calentando: PLA r\xe1pido")),
            ("Precalentar cama", lambda: "- / 60", fija(None, 60, "Calentando la cama")),
            ("Boquilla", lambda: temp_txt(s['boq'], s['boq_obj']),
             lambda: c.ir(Editor(c, self, "Boquilla", lambda: round(s['boq_obj']),
                                 lambda v: c.gcode("M104 S%d" % v), 1, 0, 260,
                                 unidad="\xb0", paso_rapido=5))),
            ("Cama", lambda: temp_txt(s['cama'], s['cama_obj']),
             lambda: c.ir(Editor(c, self, "Cama", lambda: round(s['cama_obj']),
                                 lambda v: c.gcode("M140 S%d" % v), 1, 0, 100,
                                 unidad="\xb0", paso_rapido=5))),
            ("Enfriar todo", lambda: "0 / 0", lambda: (c.gcode("TURN_OFF_HEATERS"),
                                                       c.aviso("Calentadores apagados", CIAN))),
        ]
    def pie(self):
        return "↻ Elegir  ● Aplicar  ●1s Volver"


class Mover(Lista):
    titulo = 'MOVER'
    PASOS = [0.1, 1., 10., 50.]
    def __init__(self, ctx):
        Lista.__init__(self, ctx)
        self.paso = 10.
        self.eje = None          # eje que mueve la rueda (None = elegir)
    def opciones(self):
        c, s = self.ctx, self.ctx.s
        def elegir(eje):
            def f():
                if eje not in s['homed']:
                    c.aviso("Primero haz el origen", AMARILLO)
                else:
                    self.eje = eje
            return f
        def paso():
            i = self.PASOS.index(self.paso)
            self.paso = self.PASOS[(i + 1) % len(self.PASOS)]
        pos = s['pos']
        return [
            ("X", lambda: "%.1f" % pos[0], elegir('x')),
            ("Y", lambda: "%.1f" % pos[1], elegir('y')),
            ("Z", lambda: "%.2f" % pos[2], elegir('z')),
            ("Paso", lambda: ("%g mm" % self.paso), paso),
            ("Origen (G28)", None, lambda: (c.gcode("G28"), c.aviso("Haciendo origen", AMARILLO))),
            ("Desactivar motores", None, lambda: (c.gcode("M84"), c.aviso("Motores libres", CIAN))),
        ]
    def girar(self, d, rapido=False):
        if self.eje is None:
            return Lista.girar(self, d)
        vel = 600 if self.eje == 'z' else 3000
        self.ctx.gcode("G91\nG1 %s%.3f F%d\nG90" % (self.eje.upper(), d * self.paso, vel))
    def pulsar(self):
        if self.eje is not None:
            self.eje = None
        else:
            Lista.pulsar(self)
    def mantener(self, seg):
        if self.eje is not None:
            self.eje = None
        else:
            self.ctx.atras()
    def modelo(self):
        m = Lista.modelo(self)
        if self.ctx.s['estado'] in ('printing', 'paused'):
            m['filas'] = [{'izq': 'No disponible imprimiendo', 'color': AMARILLO}]
            m['sel'] = None
        elif self.eje is not None:
            m['color'] = NARANJA
            m['derecha'] = _("mueve %s") % self.eje.upper()
            m['pie'] = _("↻ Mover %s  ● Listo") % self.eje.upper()
        else:
            m['derecha'] = "sin imprimir"
        return m


class Archivos(Lista):
    titulo = 'ARCHIVOS'
    def __init__(self, ctx):
        Lista.__init__(self, ctx)
        self.lista = ctx.archivos()
    def opciones(self):
        c = self.ctx
        ops = []
        for nombre, tam, cuando in self.lista:
            def imprimir(n=nombre, t=tam):
                c.ir(Confirmar(c, '\xbfIMPRIMIR?', [n, "%d KB" % (t // 1024),
                                                    "\xbfCama limpia?"],
                               "S\xed, imprimir",
                               lambda: c.gcode('SDCARD_PRINT_FILE FILENAME="%s"' % n)))
            ops.append((nombre, (lambda q=cuando: q), imprimir))
        if not ops:
            ops.append(("No hay archivos", None, None))
        return ops
    def pie(self):
        return "↻ Elegir  ● Imprimir  ●1s Volver"


class Filamento(Vista):
    """Asistente: calentar, sacar (descargar) o meter y purgar (cargar)."""
    titulo = 'FILAMENTO'
    TEMP = 220
    def __init__(self, ctx):
        Vista.__init__(self, ctx)
        self.sel = 0
        self.fase = 'elegir'       # elegir, calentar, moviendo, hecho
        self.que = None
        self.t_fin = 0.
    def girar(self, d, rapido=False):
        if self.fase in ('elegir', 'hecho'):
            self.sel = 1 if d > 0 else 0
    def pulsar(self):
        if self.fase in ('elegir', 'hecho'):
            self.que = 'descargar' if self.sel == 0 else 'cargar'
            self.fase = 'calentar'
            self.ctx.gcode("M104 S%d" % self.TEMP)
    def mantener(self, seg):
        self.ctx.gcode("M104 S0")
        self.ctx.atras()
    def modelo(self):
        c, s = self.ctx, self.ctx.s
        m = Vista.modelo(self)
        if self.fase == 'calentar':
            if s['boq'] >= self.TEMP - 5:
                if self.que == 'descargar':
                    c.gcode("M83\nG1 E10 F300\nG1 E-80 F1800\nM82")
                else:
                    c.gcode("M83\nG1 E80 F600\nG1 E25 F150\nM82")
                self.fase = 'moviendo'
                self.t_fin = s['ahora'] + 12
            m['grande'] = {'valor': "%d\xb0" % round(s['boq']),
                           'antes': _("Calentando para %s") % _(self.que),
                           'barra': s['boq'] / float(self.TEMP), 'color': NARANJA}
            m['derecha'] = "paso 1 de 3"
            m['pie'] = "●1s Cancelar (apaga la boquilla)"
            return m
        if self.fase == 'moviendo':
            if s['ahora'] >= self.t_fin:
                self.fase = 'hecho'
                self.sel = 1
            texto = "Sacando..." if self.que == 'descargar' else "Metiendo y purgando..."
            m['grande'] = {'valor': "%d\xb0" % round(s['boq']), 'antes': texto,
                           'barra': 1. - max(0., self.t_fin - s['ahora']) / 12., 'color': VERDE}
            m['derecha'] = "paso 2 de 3"
            m['pie'] = "Espera, no tires del filamento"
            return m
        filas = []
        if self.fase == 'hecho':
            filas.append({'izq': 'Hecho: ya puedes sacarlo' if self.que == 'descargar'
                          else 'Hecho: filamento cargado', 'color': VERDE})
        else:
            filas.append({'izq': _('Boquilla a %d\xb0 primero') % self.TEMP, 'color': GRIS})
        filas.append({'izq': ''})
        filas.append({'izq': 'Descargar (sacar)'})
        filas.append({'izq': 'Cargar (meter y purgar)'})
        m.update({'filas': filas, 'sel': 2 + self.sel,
                  'pie': "↻ Elegir  ● Empezar  ●1s Salir"})
        if self.fase == 'hecho':
            m['derecha'] = "paso 3 de 3"
        return m


class Info(Lista):
    titulo = 'INFO'
    def opciones(self):
        s = self.ctx.s
        return [("Klipper", lambda: s['version'].split('-g')[0][-10:], None),
                ("Placa", lambda: s['mcu'].split('-g')[0][-10:], None),
                ("IP", lambda: s['ip'], None),
                ("Fluidd: http://" + s['ip'], None, None)]


######################################################################
# Animacion de arranque
######################################################################

def dibujar_carta(lienzo):
    """Carta de ajuste: barras puras, degradados de 32 pasos y rotulos de color."""
    barras = [rgb(255, 255, 255), rgb(255, 255, 0), rgb(0, 255, 255), rgb(0, 255, 0),
              rgb(255, 0, 255), rgb(255, 0, 0), rgb(0, 0, 255), rgb(0, 0, 0)]
    for i, c in enumerate(barras):
        lienzo.rect(i * 40, 0, 40, 72, c)
    lienzo.rect(0, 72, ANCHO, 16, NEGRO)
    Campo(lienzo, 0, 72, 40, tinta=GRIS).poner(
        "BLAN AMAR CIAN VERD MAGE ROJO AZUL NEGR")
    canales = [('R', lambda v: rgb(v, 0, 0)), ('G', lambda v: rgb(0, v, 0)),
               ('B', lambda v: rgb(0, 0, v)), ('W', lambda v: rgb(v, v, v))]
    for j, (letra, color) in enumerate(canales):
        y = 88 + j * 28
        for i in range(32):
            lienzo.rect(i * 10, y, 10, 28, color(i * 255 // 31))
        Campo(lienzo, 2, y + 6, 1, tinta=BLANCO, fondo=NEGRO).poner(letra)
    lienzo.rect(0, 200, ANCHO, 40, NEGRO)
    x = 0
    for txt, c in (("CARTA  ", BLANCO), ("ROJO ", rgb(255, 0, 0)),
                   ("VERDE ", rgb(0, 255, 0)), ("AZUL ", rgb(0, 0, 255)),
                   ("NARANJA", NARANJA)):
        txt = _(txt)
        Campo(lienzo, x, 204, len(txt), tinta=c).poner(txt)
        x += len(txt) * 8
    Campo(lienzo, 0, 222, 40, tinta=GRIS).poner(
        _("Toca la rueda para salir").center(40))


def animacion_inicio(lienzo, luz, subtitulo):
    """Generador: va dejando dibujo pendiente en 'lienzo' y devuelve la espera
    (segundos) hasta el siguiente fotograma. 'luz(v)' enciende/apaga la luz."""
    L = lienzo
    luz(0)                                   # se borra a oscuras
    L.rect(0, 0, ANCHO, ALTO, NEGRO)
    yield 0.
    luz(1)
    titulo = "KOBRA NEO"
    x0 = (ANCHO - len(titulo) * 32) // 2
    for i, ch in enumerate(titulo):
        if ch != ' ':
            L.caracter(x0 + i * 32, 48, ord(ch), 4,
                       NARANJA if i < 5 else BLANCO, NEGRO)
        yield 0.07
    sub = a_cp437(subtitulo)[:38]
    xs = (ANCHO - len(sub) * 8) // 2
    for i, c in enumerate(sub):
        L.caracter(xs + i * 8, 124, c, 1, GRIS, NEGRO)
    yield 0.35
    # una boquilla cruza la pantalla imprimiendo una linea de filamento
    y, xa, xb, paso = 206, 16, 304, 12
    prev = None
    for x in list(range(xa, xb, paso)) + [xb]:
        if prev is not None:
            L.rect(prev - 14, y - 38, 29, 38, NEGRO)         # borra la boquilla
        desde = xa if prev is None else prev
        L.rect(desde, y, x - desde + 1, 4, NARANJA)        # filamento
        _boquilla(L, x, y)
        prev = x
        yield 0.04
    L.rect(prev - 14, y - 38, 29, 38, NEGRO)
    listo = a_cp437(_("Lista"))
    xs = (ANCHO - len(listo) * 16) // 2
    for i, c in enumerate(listo):
        L.caracter(xs + i * 16, 150, c, 2, VERDE, NEGRO)
    yield 0.9

def _boquilla(L, x, y):
    """Bloque calefactor + boquilla con la punta tocando la linea (y). 29x38 px."""
    L.rect(x - 14, y - 38, 29, 13, BLOQUE)       # bloque calefactor
    L.rect(x - 3, y - 35, 7, 4, ROJO)            # cartucho
    L.rect(x - 8, y - 25, 17, 5, LATON)          # tuerca de la boquilla
    L.rect(x - 6, y - 20, 13, 4, LATON)
    L.rect(x - 4, y - 16, 9, 4, LATON)
    L.rect(x - 2, y - 12, 5, 4, LATON)
    L.rect(x - 1, y - 8, 3, 8, NARANJA)          # hilo de plastico saliendo


######################################################################
# Navegacion (comun a Klipper y al simulador)
######################################################################

class Navegador:
    """Pila de vistas sobre la pantalla de estado + gestos de la rueda.
    Quien lo use pone: gcode(script), apagar_luz(), archivos()."""
    def __init__(self, lienzo):
        self.l = lienzo
        self.cab = Cabecera(lienzo)
        self.pie = Campo(lienzo, 8, 219, 38, 1, GRIS_CLARO, GRIS_OSCURO)
        self.estado_p = PantallaEstado(lienzo, self.cab, self.pie)
        self.plantilla = Plantilla(lienzo, self.cab, self.pie)
        self.pila = []
        self.capa = None            # 'estado', 'menu' o None (pantalla sin conocer)
        self.s = None
        self.aviso_txt, self.aviso_color, self.aviso_hasta = '', GRIS_CLARO, 0.
        self.ult_gesto = 0.
        self.volver_tras = 60.       # sin tocar la rueda en un menu: al estado
    # --- acciones para las vistas (ctx)
    def ir(self, vista):
        self.pila.append(vista)
    def atras(self):
        if self.pila:
            self.pila.pop()
    def inicio(self):
        self.pila = []
    def aviso(self, texto, color=GRIS_CLARO, duracion=4.):
        self.aviso_txt, self.aviso_color = texto, color
        self.aviso_hasta = (self.s['ahora'] if self.s else 0.) + duracion
    # --- gestos
    def girar(self, d, rapido=False):
        if not self.pila:
            imprime = self.s and self.s['estado'] in ('printing', 'paused')
            self.ir(Ajustes(self) if imprime else Menu(self))
            return
        self.pila[-1].girar(d, rapido)
    def pulsar(self):
        if not self.pila:
            self.ir(Menu(self))
        else:
            self.pila[-1].pulsar()
    def mantener(self, seg):
        if self.pila:
            self.pila[-1].mantener(seg)
    def umbral_largo(self):
        return self.pila[-1].umbral_largo() if self.pila else None
    # --- pintar
    def _capa(self, nueva):
        if self.capa == nueva:
            return
        if self.capa is None:
            # pantalla desconocida (arranque): se borra entera una sola vez
            self.l.rect(0, 0, ANCHO, 214, NEGRO)
            self.l.rect(0, 214, ANCHO, 26, GRIS_OSCURO)
            self.cab.olvidar()
            self.pie.asumir(GRIS_OSCURO)
            self.estado_p.asumir_vacia()
            self.plantilla.asumir_vacia()
        elif self.capa == 'estado':
            self.estado_p.salir()
        else:
            self.plantilla.salir()
        self.capa = nueva
    def pintar(self, s):
        self.s = s
        if (self.pila and self.volver_tras
                and s['ahora'] - self.ult_gesto > self.volver_tras):
            self.pila = []
        aviso = self.aviso_txt if s['ahora'] < self.aviso_hasta else ''
        if not self.pila:
            self._capa('estado')
            pie = aviso or ("\u25cf Men\xfa  \u21bb Ajustes" if s['estado'] in
                            ('printing', 'paused') else
                            time.strftime("%H:%M") + _("   \u25cf Men\xfa"))
            self.estado_p.pintar(s, pie)
            return
        m = self.pila[-1].modelo()
        self._capa('menu')
        if aviso:
            m['pie'] = aviso
        self.plantilla.pintar(m, COLOR_ESTADO.get(s['estado'], (GRIS_OSCURO,))[0])
    def forzar_repintado(self):
        self.capa = None


######################################################################
# Integracion con Klipper
######################################################################

def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "?"


class SalidaST7789:
    def __init__(self, config):
        from . import bus
        self.spi = bus.MCU_SPI_from_config(config, 0, default_speed=4000000)
        mcu = self.spi.get_mcu()
        cq = self.spi.get_command_queue()
        self.dc = bus.MCU_bus_digital_out(mcu, config.get('dc_pin'), cq)
        self.luz = bus.MCU_bus_digital_out(mcu, config.get('backlight_pin'),
                                           cq, value=1)
        self.dc_estado = None
        # Con el firmware parcheado (spi_fill / spi_glyph) los pixeles se generan
        # en la placa; si no las tiene, se mandan como antes por spi_send.
        self.relleno = self.cmd_glifo = None
        mcu.register_config_callback(self._configurar)
    def _configurar(self):
        mcu = self.spi.get_mcu()
        cq = self.spi.get_command_queue()
        f_rel = "spi_fill oid=%c color=%hu count=%hu"
        f_gli = "spi_glyph oid=%c fg=%hu bg=%hu scale=%c bits=%*s"
        if (mcu.try_lookup_command(f_rel) is not None
                and mcu.try_lookup_command(f_gli) is not None):
            self.relleno = mcu.lookup_command(f_rel, cq=cq)
            self.cmd_glifo = mcu.lookup_command(f_gli, cq=cq)
        logging.info("kobra_tft: pixeles generados en la placa: %s",
                     "si" if self.acelerada else "no (firmware sin spi_fill)")
    @property
    def acelerada(self):
        return self.relleno is not None
    def rellenar(self, color, n):
        self._dc(1)
        oid = self.spi.get_oid()
        while n > 0:
            k = min(n, RELLENO_MAX)
            self.relleno.send([oid, color, k], reqclock=BACKGROUND_PRIORITY_CLOCK)
            n -= k
    def glifo(self, tinta, fondo, escala, filas):
        self._dc(1)
        self.cmd_glifo.send([self.spi.get_oid(), tinta, fondo, escala, list(filas)],
                            reqclock=BACKGROUND_PRIORITY_CLOCK)
    def _dc(self, v):
        if v != self.dc_estado:
            self.dc.update_digital_out(v, reqclock=BACKGROUND_PRIORITY_CLOCK)
            self.dc_estado = v
    def comando(self, c, datos):
        self._dc(0)
        self.spi.spi_send([c], reqclock=BACKGROUND_PRIORITY_CLOCK)
        if datos:
            self.datos(datos)
    def datos(self, buf):
        self._dc(1)
        for i in range(0, len(buf), TROZO):
            self.spi.spi_send(list(buf[i:i + TROZO]),
                              reqclock=BACKGROUND_PRIORITY_CLOCK)
    def luz_pon(self, encendida):
        self.luz.update_digital_out(encendida,
                                    reqclock=BACKGROUND_PRIORITY_CLOCK)


class KobraTFT:
    def __init__(self, config):
        from .display import font8x14
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.salida = SalidaST7789(config)
        self.lienzo = Lienzo(self.salida, font8x14.VGA_FONT)
        self.nav = Navegador(self.lienzo)
        self.nav.gcode = self.gcode
        self.nav.apagar_luz = self._apagar_luz
        self.nav.cambiar_idioma = self._cambiar_idioma
        # Preferencias elegidas en la pantalla: sobreviven a reinicios
        self.ruta_pref = os.path.join(
            os.path.dirname(self.printer.get_start_args()['config_file']),
            'kobra_tft', 'preferencias.json')
        IDIOMA[0] = config.getchoice('idioma', {k: k for k in IDIOMAS}, 'en')  # sin preferencias: ingles
        idioma = self._leer_pref().get('idioma')
        if idioma in IDIOMAS:
            IDIOMA[0] = idioma
        self.nav.archivos = self._archivos
        self.periodo = config.getfloat('refresco', 2., minval=0.5)
        self.presup_reposo = config.getint('bytes_reposo', 4000, minval=500)
        self.presup_imprime = config.getint('bytes_imprimiendo', 1500, minval=200)
        self.presup_uso = config.getint('bytes_usando', 8000, minval=500)
        self.apagar_tras = config.getfloat('apagar_luz_tras', 900., minval=0.)
        self.nav.volver_tras = config.getfloat('volver_al_estado_tras', 60., minval=0.)
        self.con_animacion = config.getboolean('animacion_inicio', True)
        self.anim = None
        self.luz = True
        self.ult_actividad = 0.
        self.ult_gesto = 0.
        self.gamma = config.getchoice('gamma', {k: k for k in GAMMAS}, 'anycubic')
        pos, neg = GAMMAS[self.gamma]
        self.inicio = list(SECUENCIA)
        self.inicio[-1:-1] = [(0xe0, pos, 0), (0xe1, neg, 0)]
        self.ip = "?"
        self.version = self.mcu_version = "?"
        self.cola_gcode = []
        self.moonraker = config.get('moonraker_url', 'http://127.0.0.1:7125').rstrip('/')
        self.meta_fichero, self.meta, self.meta_reintento = None, {}, 0.
        self.miniatura = None
        self.t_pulsado = None
        self.t_largo = None
        self.seg_largo = 1
        self.ult_giro = 0.
        self.racha = 0
        # rueda y pulsador
        botones = self.printer.load_object(config, 'buttons')
        p1, p2 = [p.strip() for p in config.get('encoder_pins').split(',')]
        botones.register_rotary_encoder(
            p1, p2, lambda t: self._giro(t, 1), lambda t: self._giro(t, -1),
            config.getint('encoder_steps_per_detent', 4, minval=2, maxval=4))
        botones.register_buttons([config.get('click_pin')], self._boton)
        self.printer.register_event_handler("klippy:ready", self._listo)
        self.temporizador = None
        self.carta = False
        self.printer.lookup_object('gcode').register_command(
            'TFT_CARTA', self.cmd_TFT_CARTA,
            desc="Muestra una carta de colores en la pantalla (SALIR=1 la quita)")
    def cmd_TFT_CARTA(self, gcmd):
        self.lienzo.pendiente = []
        if gcmd.get_int('SALIR', 0):
            self._quitar_carta()
            return
        gamma = gcmd.get('GAMMA', None)
        if gamma is not None:
            if gamma.lower() not in GAMMAS:
                raise gcmd.error("GAMMA puede ser: %s" % ", ".join(sorted(GAMMAS)))
            self.gamma = gamma.lower()
            pos, neg = GAMMAS[self.gamma]
            self.salida.comando(0xe0, pos)
            self.salida.comando(0xe1, neg)
        self.carta = True
        if not self.luz:
            self.luz = True
            self.salida.luz_pon(1)
        dibujar_carta(self.lienzo)
        gcmd.respond_info("Carta de colores en pantalla (gamma %s; otras: %s);"
                          " toca la rueda para salir"
                          % (self.gamma, ", ".join(sorted(GAMMAS))))
        if self.temporizador is not None:
            self.reactor.update_timer(self.temporizador, self.reactor.NOW)
    def _quitar_carta(self):
        self.carta = False
        self.lienzo.pendiente = []
        self.nav.forzar_repintado()
        if self.temporizador is not None:
            self.reactor.update_timer(self.temporizador, self.reactor.NOW)
    # --- eventos
    def _listo(self):
        p = self.printer
        self.gc = p.lookup_object('gcode')
        self.ps = p.lookup_object('print_stats')
        self.sd = p.lookup_object('virtual_sdcard', None)
        self.ext = p.lookup_object('extruder', None)
        self.cama = p.lookup_object('heater_bed', None)
        self.gm = p.lookup_object('gcode_move')
        self.th = p.lookup_object('toolhead')
        self.ventilador = p.lookup_object('fan', None)
        self.version = p.start_args.get('software_version', '?')
        self.mcu_version = p.lookup_object('mcu').get_status().get('mcu_version', '?')
        self.ip = ip_local()
        self.ult_actividad = self.reactor.monotonic()
        self.temporizador = self.reactor.register_timer(self._tic,
                                                        self.reactor.NOW)
    def _gesto(self, ahora):
        """Comun a todos los gestos. Devuelve True si el gesto solo despierta
        (luz apagada o arrancando): con la luz apagada nunca se actua a ciegas."""
        self.ult_actividad = self.ult_gesto = self.nav.ult_gesto = ahora
        if self.carta:
            self._quitar_carta()
            return True
        despierta = not self.luz
        if despierta:
            self.luz = True
            self.salida.luz_pon(1)
        if self.temporizador is not None:
            self.reactor.update_timer(self.temporizador, self.reactor.NOW)
        return despierta or bool(self.inicio) or self.anim is not None
    def _giro(self, ahora, d):
        rapido = ahora - self.ult_giro < 0.12
        self.racha = self.racha + 1 if rapido else 0
        self.ult_giro = ahora
        if self._gesto(ahora):
            return
        self.nav.girar(d, self.racha > 3)
    def _boton(self, ahora, estado):
        # La pulsacion larga salta mientras se mantiene (temporizador), no al soltar.
        if estado:
            self._cancelar_largo()
            self.t_pulsado = None
            if self._gesto(ahora):
                return
            self.t_pulsado = ahora
            umbral = self.nav.umbral_largo()
            if umbral:
                self.seg_largo = 2 if umbral >= MUY_LARGO else 1
                self.t_largo = self.reactor.register_timer(self._largo,
                                                           ahora + umbral)
            return
        if self.t_pulsado is None:
            return  # solo desperto, o la larga ya salto
        self.t_pulsado = None
        self._cancelar_largo()
        self.nav.pulsar()
    def _largo(self, ahora):
        self._cancelar_largo()
        if self.t_pulsado is not None:
            self.t_pulsado = None
            self.ult_gesto = self.nav.ult_gesto = ahora
            self.nav.mantener(self.seg_largo)
            if self.temporizador is not None:
                self.reactor.update_timer(self.temporizador, self.reactor.NOW)
        return self.reactor.NEVER
    def _cancelar_largo(self):
        if self.t_largo is not None:
            self.reactor.unregister_timer(self.t_largo)
            self.t_largo = None
    def _leer_pref(self):
        try:
            with open(self.ruta_pref) as f:
                pref = json.load(f)
            return pref if isinstance(pref, dict) else {}
        except (OSError, ValueError):
            return {}
    def _guardar_pref(self, **cambios):
        pref = self._leer_pref()
        pref.update(cambios)
        tmp = self.ruta_pref + '.tmp'
        try:
            os.makedirs(os.path.dirname(self.ruta_pref), exist_ok=True)
            with open(tmp, 'w') as f:
                json.dump(pref, f, indent=1)
            os.replace(tmp, self.ruta_pref)
        except OSError as e:
            logging.info("kobra_tft: no se pudo guardar %s (%s)", self.ruta_pref, e)
    def _cambiar_idioma(self):
        lista = list(IDIOMAS)
        IDIOMA[0] = lista[(lista.index(IDIOMA[0]) + 1) % len(lista)]
        self._guardar_pref(idioma=IDIOMA[0])
        self.nav.forzar_repintado()
    def _apagar_luz(self):
        self.nav.inicio()
        self.luz = False
        self.salida.luz_pon(0)
    def _archivos(self):
        if self.sd is None:
            return []
        base = self.sd.sdcard_dirname
        lista = []
        for nombre, tam in self.sd.get_file_list(check_subdirs=True):
            try:
                mt = os.path.getmtime(os.path.join(base, nombre))
            except OSError:
                mt = 0.
            lista.append((mt, nombre, tam))
        lista.sort(reverse=True)
        return [(n, t, time.strftime("%d/%m", time.localtime(mt)))
                for mt, n, t in lista[:30]]
    # --- G-code en cola (como el menu de Klipper), sin bloquear la pantalla
    def gcode(self, script):
        self.cola_gcode.append(script)
        if len(self.cola_gcode) == 1:
            self.reactor.register_callback(self._ejecutar_gcode)
    def _ejecutar_gcode(self, ahora):
        while self.cola_gcode:
            script = self.cola_gcode[0]
            try:
                self.gc.run_script(script)
            except Exception as e:
                logging.info("kobra_tft: %s -> %s", script, e)
                self.nav.aviso(str(e).split('\n')[0][:38], ROJO, 8.)
            self.cola_gcode.pop(0)
    # --- bucle
    def _estado(self, ahora):
        ps = self.ps.get_status(ahora)
        sd = self.sd.get_status(ahora) if self.sd else {}
        e = self.ext.get_status(ahora) if self.ext else {}
        c = self.cama.get_status(ahora) if self.cama else {}
        g = self.gm.get_status(ahora)
        f = self.ventilador.get_status(ahora) if self.ventilador else {}
        th = self.th.get_status(ahora)
        pos = g.get('gcode_position', [0, 0, 0, 0])
        fichero = ps.get('filename', '')
        if fichero and fichero != self.meta_fichero and ahora > self.meta_reintento:
            self.meta_fichero, self.meta, self.miniatura = fichero, {}, None
            threading.Thread(target=self._pedir_meta, args=(fichero,),
                             daemon=True).start()
        return {
            'ahora': ahora,
            'estado': ps.get('state', 'standby'),
            'fichero': ps.get('filename', ''),
            'error': ps.get('message', ''),
            'duracion': ps.get('print_duration', 0.),
            'progreso': self._progreso(sd),
            'total': ps.get('total_duration', 0.),
            'estimado': self.meta.get('estimated_time'),
            'miniatura': self.miniatura,
            'boq': e.get('temperature', 0.), 'boq_obj': e.get('target', 0.),
            'cama': c.get('temperature', 0.), 'cama_obj': c.get('target', 0.),
            'velocidad': g.get('speed_factor', 1.),
            'flujo': g.get('extrude_factor', 1.),
            'z_offset': g.get('homing_origin', [0, 0, 0])[2],
            'ventilador': f.get('speed', 0.),
            'pos': (pos[0], pos[1], pos[2]), 'z': pos[2],
            'homed': th.get('homed_axes', ''),
            'ip': self.ip, 'version': self.version, 'mcu': self.mcu_version,
        }
    # --- progreso igual que Fluidd: solo cuenta el G-code real del fichero
    # (sin cabecera ni pie), con los bytes que da Moonraker en sus metadatos
    def _pedir_meta(self, fichero):
        url = "%s/server/files/metadata?filename=%s" % (
            self.moonraker, urllib.parse.quote(fichero))
        try:
            with urllib.request.urlopen(url, timeout=5.) as r:
                m = json.load(r)['result']
        except Exception as e:
            logging.info("kobra_tft: sin metadatos de %s (%s)", fichero, e)
            if self.meta_fichero == fichero:
                self.meta_fichero = None
                self.meta_reintento = self.reactor.monotonic() + 30.
            return
        if self.meta_fichero != fichero:
            return
        self.meta = m
        # vista previa: solo si el G-code la trae (la mas pequena que llene el hueco)
        minis = [t for t in (m.get('thumbnails') or []) if t.get('relative_path')]
        if not minis:
            return
        grandes = [t for t in minis if max(t['width'], t['height']) >= MINI_LADO]
        t = (min(grandes, key=lambda t: t['width'] * t['height']) if grandes
             else max(minis, key=lambda t: t['width'] * t['height']))
        ruta = os.path.join(os.path.dirname(fichero), t['relative_path'])
        url = "%s/server/files/gcodes/%s" % (self.moonraker, urllib.parse.quote(ruta))
        try:
            with urllib.request.urlopen(url, timeout=5.) as r:
                w, h, pix = png_a_rgb565(r.read(), MINI_LADO)
        except Exception as e:
            logging.info("kobra_tft: sin vista previa de %s (%s)", fichero, e)
            return
        if self.meta_fichero == fichero:
            self.miniatura = (fichero, w, h, pix)
    def _progreso(self, sd):
        ini, fin = self.meta.get('gcode_start_byte'), self.meta.get('gcode_end_byte')
        pos = sd.get('file_position')
        if ini is not None and fin is not None and pos is not None and fin > ini:
            return max(0., min(1., (pos - ini) / float(fin - ini)))
        return sd.get('progress', 0.)
    def _tic(self, ahora):
        try:
            # 1) arranque del controlador (con sus esperas) y animacion
            while self.inicio:
                c, datos, espera = self.inicio.pop(0)
                self.salida.comando(c, datos)
                if espera:
                    return ahora + espera
                if not self.inicio and self.con_animacion:
                    self.anim = animacion_inicio(
                        self.lienzo, self.salida.luz_pon,
                        "Klipper %s  %s" % (self.version.split('-g')[0], self.ip))
            if self.anim is not None:
                try:
                    espera = next(self.anim)
                except StopIteration:
                    self.anim = None
                    self.nav.forzar_repintado()
                else:
                    self.lienzo.volcar(10**9)
                    return ahora + max(espera, 0.02)
            # carta de colores: no se toca hasta que se quite
            if self.carta:
                self.ult_actividad = ahora
                self.lienzo.volcar(self.presup_uso)
                return ahora + (0.05 if self.lienzo.pendiente else self.periodo)
            # 2) estado, luz y vuelta automatica al estado
            s = self._estado(ahora)
            imprimiendo = s['estado'] in ('printing', 'paused')
            if imprimiendo:
                self.ult_actividad = ahora
                if not self.luz:
                    self.luz = True
                    self.salida.luz_pon(1)
            elif (self.luz and self.apagar_tras
                  and ahora - self.ult_actividad > self.apagar_tras):
                self._apagar_luz()
            # 3) pintar solo lo que cambia
            if not self.lienzo.pendiente:
                self.nav.pintar(s)
            usando = ahora - self.ult_gesto < 10.
            presupuesto = (self.presup_uso if usando else
                           self.presup_imprime if imprimiendo else self.presup_reposo)
            self.lienzo.volcar(presupuesto)
            if self.lienzo.pendiente:
                return ahora + (0.05 if usando else 0.5 if imprimiendo else 0.25)
            if usando:
                return ahora + 0.25
            if self.nav.pila and self.nav.volver_tras:
                # despertar justo cuando toque volver al estado
                return min(ahora + self.periodo,
                           self.ult_gesto + self.nav.volver_tras + 0.05)
        except Exception:
            logging.exception("kobra_tft: error al pintar")
            return ahora + 10.
        return ahora + self.periodo
    def get_status(self, eventtime):
        return {'luz': self.luz, 'menu': len(self.nav.pila),
                'pendiente': len(self.lienzo.pendiente)}


def load_config(config):
    return KobraTFT(config)
