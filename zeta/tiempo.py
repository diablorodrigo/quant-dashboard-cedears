"""Hora y cierre de mercado en America/Argentina/Buenos_Aires."""

from __future__ import annotations

import pandas as pd

ZONA = "America/Argentina/Buenos_Aires"
# El motor considera cerrada la rueda a partir de las 18:00, hora de Argentina.
CORTE_HORA = 18


def ahora_art(momento: pd.Timestamp | None = None) -> pd.Timestamp:
    if momento is None:
        return pd.Timestamp.now(tz=ZONA)
    if momento.tzinfo is None:
        return momento.tz_localize(ZONA)
    return momento.tz_convert(ZONA)


def fecha_cierre(momento: pd.Timestamp | None = None) -> pd.Timestamp:
    """Día de la última rueda usable como clave de caché.

    Antes de las 18:00 ART se toma el día hábil anterior. Sábados y domingos
    retroceden hasta el viernes.
    """
    momento = ahora_art(momento)
    dia = momento.normalize()
    if momento.hour < CORTE_HORA:
        dia = dia - pd.Timedelta(days=1)
    while int(dia.weekday()) >= 5:
        dia = dia - pd.Timedelta(days=1)
    return dia


def clave_cierre(momento: pd.Timestamp | None = None) -> str:
    return fecha_cierre(momento).strftime("%Y-%m-%d")


def texto_actualizacion(momento: pd.Timestamp | None = None) -> str:
    momento = ahora_art(momento)
    cierre = fecha_cierre(momento)
    return (
        f"{momento.strftime('%d/%m/%Y %H:%M')} ART"
        f" · cierre de referencia {cierre.strftime('%d/%m/%Y')}"
    )
