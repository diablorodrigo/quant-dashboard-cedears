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


# Rueda habitual de CEDEARs en BYMA. No contempla feriados.
APERTURA_CEDEAR = (11, 0)
CIERRE_CEDEAR = (17, 0)


def mercado_cedears_abierto(momento: pd.Timestamp | None = None) -> bool:
    """Lunes a viernes, de 11:00 a 17:00, hora de Argentina."""
    momento = ahora_art(momento)
    if int(momento.weekday()) >= 5:
        return False
    minutos = momento.hour * 60 + momento.minute
    abre = APERTURA_CEDEAR[0] * 60 + APERTURA_CEDEAR[1]
    cierra = CIERRE_CEDEAR[0] * 60 + CIERRE_CEDEAR[1]
    return abre <= minutos < cierra


def linea_datos(
    obtenido: pd.Timestamp,
    ultima_rueda: pd.Timestamp | None = None,
    momento: pd.Timestamp | None = None,
    ultima_rueda_ars: pd.Timestamp | None = None,
) -> str:
    """Sello de la descarga guardada en caché, no de la hora en que se abrió la página.

    `obtenido` es el instante en que Yahoo respondió. `momento` solo dice si
    ahora la rueda local está abierta o cerrada.
    """
    obtenido = ahora_art(obtenido)
    estado = "abierto" if mercado_cedears_abierto(momento) else "cerrado"
    texto = (
        f"Datos actualizados: {obtenido:%d/%m/%Y %H:%M} (hora Argentina)"
        f" · Mercado de CEDEARs {estado}"
        f" · Precios de Yahoo con demora de unos 15 minutos"
    )
    if ultima_rueda is not None:
        texto += f" · Última rueda en la serie: {pd.Timestamp(ultima_rueda):%d/%m/%Y}"
    if ultima_rueda_ars is not None and ultima_rueda is not None:
        ars = pd.Timestamp(ultima_rueda_ars).normalize()
        usd = pd.Timestamp(ultima_rueda).normalize()
        if ars != usd:
            texto += f" · Precios en pesos al {ars:%d/%m/%Y}"
    return texto
