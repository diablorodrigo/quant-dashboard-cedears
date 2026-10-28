"""Semáforo de contraste entre dos fuentes y log diario de desvíos.

Verde: la diferencia es menor a 0,5% (1% si el dato es un dólar).
Amarillo: de ese umbral hasta 2%, inclusive.
Rojo: la diferencia supera el 2%, o el dato tiene más de 30 minutos
y el mercado está abierto. En rojo no se calcula la señal del activo.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

VERDE = "verde"
AMARILLO = "amarillo"
ROJO = "rojo"

UMBRAL_VERDE = 0.005
UMBRAL_VERDE_DOLAR = 0.01
UMBRAL_ROJO = 0.02
EDAD_MAX_MINUTOS = 30

COLUMNAS_LOG = (
    "momento",
    "tipo",
    "clave",
    "valor_principal",
    "fuente_principal",
    "valor_contraste",
    "fuente_contraste",
    "diferencia_pct",
    "estado",
    "motivo",
)


def diferencia_relativa(principal: float | None, contraste: float | None) -> float | None:
    if principal is None or contraste is None:
        return None
    try:
        base = abs(float(principal))
        if base == 0:
            return None
        return abs(float(principal) - float(contraste)) / base
    except (TypeError, ValueError):
        return None


def semaforo(
    principal: float | None,
    contraste: float | None,
    *,
    es_dolar: bool = False,
    edad_minutos: float | None = None,
    mercado_abierto: bool = False,
) -> dict:
    """Compara dos lecturas del mismo dato y devuelve el color, la diferencia y el motivo."""
    verde = UMBRAL_VERDE_DOLAR if es_dolar else UMBRAL_VERDE
    dif = diferencia_relativa(principal, contraste)
    viejo = (
        edad_minutos is not None
        and edad_minutos > EDAD_MAX_MINUTOS
        and mercado_abierto
    )
    if principal is None:
        estado, motivo = ROJO, "Sin dato de la fuente principal."
    elif viejo:
        estado, motivo = ROJO, "El dato tiene más de 30 minutos."
    elif contraste is None or dif is None:
        estado, motivo = AMARILLO, "Sin segunda fuente para contrastar."
    elif dif < verde:
        estado, motivo = VERDE, ""
    elif dif <= UMBRAL_ROJO:
        estado, motivo = AMARILLO, "Las fuentes difieren, dentro de la banda de aviso."
    else:
        estado, motivo = ROJO, "Las fuentes difieren más del 2%."
    return {
        "estado": estado,
        "diferencia": None if dif is None else round(dif * 100, 4),
        "motivo": motivo,
        "bloquea_senal": estado == ROJO,
    }


def cierre_previo(precio: float | None, variacion_pct: float | None) -> float | None:
    """Reconstruye el cierre anterior a partir del precio y la variación del día, en %."""
    if precio is None or variacion_pct is None:
        return None
    try:
        factor = 1 + float(variacion_pct) / 100
    except (TypeError, ValueError):
        return None
    if factor == 0:
        return None
    return float(precio) / factor


def contrastar_cotizacion(
    *,
    precio_vivo: float | None,
    variacion_pct: float | None,
    precio_yahoo: float | None,
    yahoo_es_hoy: bool,
    edad_minutos: float | None,
    mercado_abierto: bool,
) -> dict:
    """Contrasta el precio en vivo con Yahoo.

    Si el mercado está abierto y Yahoo todavía no tiene la rueda de hoy,
    se compara el cierre anterior reconstruido. Así una suba de la mañana
    no se lee como un desvío entre fuentes.
    """
    if (
        edad_minutos is not None
        and edad_minutos > EDAD_MAX_MINUTOS
        and mercado_abierto
    ):
        lectura = semaforo(
            precio_vivo,
            precio_yahoo,
            edad_minutos=edad_minutos,
            mercado_abierto=True,
        )
        lectura["comparo"] = "frescura"
        return lectura

    directo = semaforo(precio_vivo, precio_yahoo, edad_minutos=None, mercado_abierto=False)
    directo["comparo"] = "precio"
    # Si el último precio de Yahoo ya está al lado del vivo, no hace falta
    # reconstruir el cierre: el desvío de verdad es el de ahora.
    if not mercado_abierto or yahoo_es_hoy or directo["estado"] != ROJO:
        return directo

    previo = cierre_previo(precio_vivo, variacion_pct)
    lectura = semaforo(previo, precio_yahoo, edad_minutos=None, mercado_abierto=False)
    if lectura["motivo"]:
        lectura["motivo"] += " "
    lectura["motivo"] += "Se contrastó el cierre anterior: Yahoo todavía no tiene la rueda de hoy."
    lectura["comparo"] = "cierre_anterior"
    lectura["valor_comparado"] = previo
    return lectura


def ruta_log(carpeta: Path, momento: datetime) -> Path:
    return Path(carpeta) / f"desvios-{momento:%Y-%m-%d}.csv"


def registrar_desvio(ruta: Path, fila: dict) -> None:
    """Agrega una fila al CSV del día. No registra los contrastes en verde."""
    if fila.get("estado") == VERDE:
        return
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with ruta.open("a", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=COLUMNAS_LOG)
        if nuevo:
            writer.writeheader()
        writer.writerow({columna: fila.get(columna, "") for columna in COLUMNAS_LOG})
