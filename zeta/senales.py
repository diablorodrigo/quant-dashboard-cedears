"""Lectura técnica. Las etiquetas describen un sesgo: no son órdenes."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

SESGO_ALCISTA_MARCADO = "Sesgo alcista marcado"
SESGO_ALCISTA = "Sesgo alcista"
NEUTRAL = "Neutral"
SESGO_BAJISTA = "Sesgo bajista"
SESGO_BAJISTA_MARCADO = "Sesgo bajista marcado"
ALCISTA_CON_VOLUMEN = "Alcista con volumen"
ALCISTA_SIN_VOLUMEN = "Alcista sin volumen"
DISTRIBUCION = "Distribución con volumen"
EN_OBSERVACION_RUPTURA = "En observación (ruptura)"
EN_OBSERVACION_RIESGO = "En observación (riesgo)"

GIRO_ALCISTA = "Cambio a sesgo alcista"
GIRO_BAJISTA = "Cambio a sesgo bajista"

# El sesgo "marcado" exige un puntaje más extremo que el cruce mínimo,
# y el bajista marcado (antes "VENTA FUERTE") queda en una rama alcanzable.
UMBRAL_MARCADO = 3
UMBRAL_SESGO = 1
UMBRAL_BAJISTA = -2
UMBRAL_BAJISTA_MARCADO = -3

DIAS_BALANCE = 5


def etiqueta_por_puntaje(score: int) -> str:
    if score >= UMBRAL_MARCADO:
        return SESGO_ALCISTA_MARCADO
    if score >= UMBRAL_SESGO:
        return SESGO_ALCISTA
    if score <= UMBRAL_BAJISTA_MARCADO:
        return SESGO_BAJISTA_MARCADO
    if score <= UMBRAL_BAJISTA:
        return SESGO_BAJISTA
    return NEUTRAL


def es_alcista(etiqueta: str) -> bool:
    return etiqueta in (SESGO_ALCISTA, SESGO_ALCISTA_MARCADO)


def es_bajista(etiqueta: str) -> bool:
    return etiqueta in (SESGO_BAJISTA, SESGO_BAJISTA_MARCADO)


def aplicar_volumen(etiqueta: str, vol_relativo: float, variacion: float) -> str:
    if es_alcista(etiqueta):
        if vol_relativo > 120:
            if variacion > 0:
                return ALCISTA_CON_VOLUMEN
            return DISTRIBUCION
        if vol_relativo < 80:
            return ALCISTA_SIN_VOLUMEN
    if es_bajista(etiqueta) and vol_relativo > 120 and variacion > 0:
        return EN_OBSERVACION_RUPTURA
    return etiqueta


def aplicar_riesgo(etiqueta: str, hay_penalizacion: bool) -> str:
    # El filtro de riesgo cubre el sesgo alcista y el que ya sumó volumen.
    # "Alcista sin volumen" no entra, igual que la "falsa ruptura" anterior.
    if hay_penalizacion and etiqueta in (
        SESGO_ALCISTA,
        SESGO_ALCISTA_MARCADO,
        ALCISTA_CON_VOLUMEN,
    ):
        return EN_OBSERVACION_RIESGO
    return etiqueta


def giro(etiqueta_previa: str, etiqueta_actual: str, variacion: float) -> str | None:
    if es_bajista(etiqueta_previa) and es_alcista(etiqueta_actual) and variacion > 0:
        return GIRO_ALCISTA
    if es_alcista(etiqueta_previa) and es_bajista(etiqueta_actual) and variacion < 0:
        return GIRO_BAJISTA
    return None


def _a_fecha(valor) -> date | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.date()
    try:
        return pd.Timestamp(valor).date()
    except (TypeError, ValueError):
        return None


def fechas_de_balance(calendario) -> list[date]:
    """Lee la próxima fecha de balance tanto si Yahoo devuelve dict como DataFrame.

    yfinance reciente hace que ``get_calendar()`` devuelva un dict. Llamar
    ``.empty`` sobre ese dict tiraba una excepción que el panel se tragaba,
    y el filtro de balances no corría nunca.
    """
    fechas: list[date] = []
    if calendario is None:
        return fechas

    crudos = []
    if isinstance(calendario, dict):
        if not calendario:
            return fechas
        bruto = calendario.get("Earnings Date", calendario.get("earningsDate"))
        if bruto is None:
            for valor in calendario.values():
                if isinstance(valor, dict):
                    bruto = valor.get("Earnings Date", valor.get("earningsDate"))
                    if bruto is not None:
                        break
        if bruto is None:
            return fechas
        crudos = list(bruto) if isinstance(bruto, (list, tuple, set)) else [bruto]
    elif isinstance(calendario, pd.DataFrame):
        if calendario.empty:
            return fechas
        if "Earnings Date" in calendario.index:
            fila = calendario.loc["Earnings Date"]
            crudos = list(fila.values) if hasattr(fila, "values") else [fila]
        elif "Earnings Date" in calendario.columns:
            crudos = list(calendario["Earnings Date"].dropna().values)
    else:
        return fechas

    for item in crudos:
        fecha = _a_fecha(item)
        if fecha is not None:
            fechas.append(fecha)
    return fechas


def dias_hasta_balance(calendario, hoy: date) -> int | None:
    futuras = [f for f in fechas_de_balance(calendario) if f >= hoy]
    if not futuras:
        return None
    return (min(futuras) - hoy).days


def balance_en_ventana(dias: int | None, ventana: int = DIAS_BALANCE) -> bool:
    return dias is not None and 0 <= dias <= ventana
