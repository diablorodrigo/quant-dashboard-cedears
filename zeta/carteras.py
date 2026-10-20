"""Carteras modelo y métricas históricas del bloque de renta variable.

Los porcentajes originales no cerraban en 100 (el conservador sumaba 90 y
Plotly lo reescalaba: la renta fija de 65 pasaba a verse como ~72). Acá el
bloque variable se lleva al peso que el texto ya anunciaba.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERFILES = {
    "conservador": {
        "titulo": "Preservación y flujo",
        "renta_fija": 65.0,
        "detalle_fija": (
            "El núcleo está pensado en obligaciones negociables y bonos. "
            "Ese bloque no tiene serie de precios en este panel, así que no entra "
            "en el rendimiento histórico."
        ),
        # Pesos relativos del bloque variable, tomados de la torta original.
        "variable": {
            "ACWI": 6.8,
            "ABBV": 4.8,
            "AIG": 4.3,
            "AGRO": 3.3,
            "ABT": 3.1,
            "AAPL": 2.7,
        },
    },
    "agresivo": {
        "titulo": "Crecimiento",
        "renta_fija": 30.0,
        "detalle_fija": (
            "La reserva de renta fija es táctica. Tampoco tiene serie en este panel "
            "y queda fuera del cálculo de rendimiento."
        ),
        "variable": {
            "AMGN": 17.5,
            "AMD": 11.9,
            "AAPL": 11.6,
            "AGRO": 8.0,
            "ABBV": 5.0,
            "ANF": 4.5,
            "AMAT": 4.3,
        },
    },
}


def tickers_variable() -> list[str]:
    vistos = []
    for perfil in PERFILES.values():
        for ticker in perfil["variable"]:
            if ticker not in vistos:
                vistos.append(ticker)
    return vistos


def _a_un_decimal(valores: list[float]) -> list[float]:
    """Reparte el residuo para que los porcentajes a 1 decimal sumen 100."""
    enteros = [int(np.floor(v * 10 + 1e-9)) for v in valores]
    resto = int(round(1000 - sum(enteros)))
    fracciones = sorted(
        ((valores[i] * 10 - enteros[i], i) for i in range(len(valores))),
        reverse=True,
    )
    for k in range(max(resto, 0)):
        enteros[fracciones[k % len(fracciones)][1]] += 1
    return [n / 10 for n in enteros]


def composicion(clave: str) -> pd.DataFrame:
    perfil = PERFILES[clave]
    relativos = perfil["variable"]
    total_rel = sum(relativos.values())
    peso_variable = 100.0 - float(perfil["renta_fija"])
    crudos = [float(perfil["renta_fija"])]
    nombres = ["Renta fija"]
    bloques = ["Renta fija"]
    for ticker, peso in relativos.items():
        nombres.append(ticker)
        bloques.append("Renta variable")
        crudos.append(peso / total_rel * peso_variable)
    ajustados = _a_un_decimal(crudos)
    return pd.DataFrame(
        {
            "Activo": nombres,
            "Bloque": bloques,
            "Porcentaje": ajustados,
        }
    )


def pesos_variable(clave: str) -> dict[str, float]:
    tabla = composicion(clave)
    filas = tabla[tabla["Bloque"] == "Renta variable"]
    return {row.Activo: float(row.Porcentaje) for row in filas.itertuples(index=False)}


def metricas_historicas(
    precios: pd.DataFrame,
    pesos: dict[str, float],
    sesiones: int = 252,
) -> dict:
    """Métricas del bloque variable con pesos constantes (rebalanceo diario implícito)."""
    import quantstats.stats as qs

    disponibles = [t for t in pesos if t in precios.columns]
    faltantes = [t for t in pesos if t not in precios.columns]
    if len(disponibles) < 2:
        raise ValueError("No hay precios suficientes para el bloque variable.")

    serie = precios[disponibles].apply(pd.to_numeric, errors="coerce").dropna(how="any")
    if len(serie) < 40:
        raise ValueError("Historia demasiado corta para calcular métricas.")
    serie = serie.tail(sesiones + 1)
    retornos = serie.pct_change().dropna(how="any")
    pesos_usados = np.array([pesos[t] for t in disponibles], dtype=float)
    pesos_usados = pesos_usados / pesos_usados.sum()
    cartera = pd.Series(retornos.values @ pesos_usados, index=retornos.index, name="cartera")
    cartera = cartera.replace([np.inf, -np.inf], np.nan).dropna()

    inicio = pd.Timestamp(cartera.index[0]).tz_localize(None)
    fin = pd.Timestamp(cartera.index[-1]).tz_localize(None)
    return {
        "rendimiento": float(qs.comp(cartera)),
        "volatilidad": float(qs.volatility(cartera)),
        "caida_maxima": float(qs.max_drawdown(cartera)),
        "var_95": float(qs.var(cartera)),
        "sharpe": float(qs.sharpe(cartera)),
        "sortino": float(qs.sortino(cartera)),
        "inicio": inicio,
        "fin": fin,
        "sesiones": int(len(cartera)),
        "faltantes": faltantes,
        "pesos_efectivos": {t: float(p) for t, p in zip(disponibles, pesos_usados)},
    }
