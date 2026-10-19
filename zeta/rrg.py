"""Radar de rotación relativa contra SPY.

Misma cuenta que el panel anterior: fuerza = z-score de 50 ruedas del ratio
precio/SPY, momentum = diferencia a 10 ruedas de esa fuerza. Los cuadrantes
se parten en cero.
"""

from __future__ import annotations

import pandas as pd


def calcular_rrg(cierres: pd.DataFrame) -> pd.DataFrame:
    if cierres is None or cierres.empty or "SPY" not in cierres.columns:
        return pd.DataFrame()

    spy = cierres["SPY"].dropna()
    filas = []
    for ticker in cierres.columns:
        if ticker == "SPY":
            continue
        activo = cierres[ticker].dropna()
        comunes = activo.index.intersection(spy.index)
        if len(comunes) < 55:
            continue
        activo = activo.loc[comunes]
        spy_ok = spy.loc[comunes]
        rs_ratio = activo / spy_ok
        media = rs_ratio.rolling(50).mean()
        desvio = rs_ratio.rolling(50).std()
        fuerza = (rs_ratio - media) / desvio.replace(0, pd.NA)
        momentum = fuerza.diff(10)
        x_val = fuerza.iloc[-1]
        y_val = momentum.iloc[-1]
        if pd.isna(x_val) or pd.isna(y_val):
            continue
        x_val = float(x_val)
        y_val = float(y_val)
        if x_val > 0 and y_val > 0:
            cuadrante = "Líderes"
        elif x_val < 0 and y_val > 0:
            cuadrante = "Mejorando"
        elif x_val > 0 and y_val < 0:
            cuadrante = "Debilitándose"
        else:
            cuadrante = "Rezagados"
        filas.append(
            {
                "Ticker": ticker,
                "Fuerza_X": round(x_val, 2),
                "Momentum_Y": round(y_val, 2),
                "Cuadrante": cuadrante,
            }
        )
    if not filas:
        return pd.DataFrame()
    return pd.DataFrame(filas)
