"""Descarga en bloque y lectura del universo. Sin llamadas por activo."""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from zeta.carteras import tickers_variable
from zeta.indicadores import atr, bollinger, ema, macd, rsi, sma
from zeta.senales import (
    aplicar_riesgo,
    aplicar_volumen,
    balance_en_ventana,
    dias_hasta_balance,
    etiqueta_por_puntaje,
    giro,
)
from zeta.universo import WATCHLIST

MIN_RUEDAS = 210
LOTE = 40


def _sin_zona(indice: pd.Index) -> pd.Index:
    idx = pd.to_datetime(indice)
    tz = getattr(idx, "tz", None)
    if tz is not None:
        idx = idx.tz_localize(None)
    return idx


def _limpiar_ohlcv(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    out = df.copy()
    out.index = _sin_zona(out.index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["Close"])
    if out.empty:
        return None
    return out


def _extraer(data: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    encontrados: dict[str, pd.DataFrame] = {}
    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        return encontrados

    if isinstance(data.columns, pd.MultiIndex):
        nivel_ticker = set(map(str, data.columns.get_level_values(0)))
        for ticker in tickers:
            if ticker not in nivel_ticker:
                continue
            bloque = data[ticker]
            if isinstance(bloque, pd.Series):
                continue
            limpio = _limpiar_ohlcv(bloque)
            if limpio is not None:
                encontrados[ticker] = limpio
        return encontrados

    if len(tickers) == 1:
        limpio = _limpiar_ohlcv(data)
        if limpio is not None:
            encontrados[tickers[0]] = limpio
    return encontrados


def _descargar_lote(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    data = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    return _extraer(data, tickers)


def descargar_simbolos(tickers: list[str], period: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    unicos = list(dict.fromkeys(tickers))
    series: dict[str, pd.DataFrame] = {}
    for i in range(0, len(unicos), LOTE):
        grupo = unicos[i : i + LOTE]
        try:
            series.update(_descargar_lote(grupo, period))
        except Exception:
            continue
    faltantes = [t for t in unicos if t not in series]
    # Un lote grande a veces se come un símbolo nuevo. Se reintenta solo.
    for ticker in faltantes[:20]:
        try:
            series.update(_descargar_lote([ticker], period))
        except Exception:
            continue
    faltantes = [t for t in unicos if t not in series]
    return series, faltantes


def _puntaje(idx: int, close, sma10, sma20, sma50, ema200, rsi14, macd_line, macd_signal, boll_up, boll_low) -> int:
    score = 0
    precio = close.iloc[idx]
    if precio < ema200.iloc[idx]:
        score -= 2
    if sma10.iloc[idx] < sma20.iloc[idx]:
        if not (precio > sma10.iloc[idx] and precio > sma20.iloc[idx]):
            score -= 1
    if macd_line.iloc[idx] > macd_signal.iloc[idx]:
        score += 1
    elif macd_line.iloc[idx] < macd_signal.iloc[idx] and macd_line.iloc[idx] > macd_line.iloc[idx - 1]:
        pass
    else:
        score -= 1
    if sma10.iloc[idx - 1] <= sma20.iloc[idx - 1] and sma10.iloc[idx] > sma20.iloc[idx]:
        score += 2
    if sma10.iloc[idx - 1] <= sma50.iloc[idx - 1] and sma10.iloc[idx] > sma50.iloc[idx]:
        score += 2
    valor_rsi = rsi14.iloc[idx]
    if valor_rsi <= 35:
        score += 2
    elif valor_rsi >= 70:
        score -= 2
    if precio <= boll_low.iloc[idx]:
        score += 2
    elif precio >= boll_up.iloc[idx]:
        score -= 2
    return int(score)


def _ultimo_precio(historia: pd.DataFrame | None) -> float | None:
    if historia is None or historia.empty:
        return None
    valor = float(historia["Close"].iloc[-1])
    if not np.isfinite(valor) or valor <= 0:
        return None
    return valor


def _fila_base(clave: str, cfg: dict, precio: float, variacion: float, precio_ars: float | None, ccl: float | None) -> dict:
    gap = None
    if precio_ars is not None and ccl:
        ccl_activo = (precio_ars * float(cfg["ratio"])) / precio
        gap = (ccl_activo / ccl - 1) * 100
    return {
        "ticker": clave,
        "nombre": cfg["name"],
        "rubro": cfg.get("rubro", "Otros"),
        "precio_usd": round(precio, 2),
        "variacion": round(variacion, 2),
        "precio_ars": round(precio_ars, 2) if precio_ars is not None else None,
        "gap_ccl": round(gap, 2) if gap is not None and np.isfinite(gap) else None,
    }


def _analisis_corto(clave: str, cfg: dict, hist: pd.DataFrame, precio_ars: float | None, ccl: float | None) -> dict | None:
    """Activos nuevos (por ejemplo SPCX) entran al monitor sin fingir una EMA 200."""
    close = hist["Close"].astype(float)
    precio = float(close.iloc[-1])
    anterior = float(close.iloc[-2]) if len(close) > 1 else 0.0
    if not np.isfinite(precio) or precio <= 0 or not anterior:
        return None
    volume = hist["Volume"].astype(float) if "Volume" in hist.columns else pd.Series(0.0, index=hist.index)
    vol_media = sma(volume, 20)
    media = vol_media.iloc[-1]
    vol_rel = float(volume.iloc[-1] / media * 100) if pd.notna(media) and media > 0 else 100.0
    rsi14 = rsi(close, 14)
    fila = _fila_base(clave, cfg, precio, (precio / anterior - 1) * 100, precio_ars, ccl)
    fila.update(
        {
            "rsi14": round(float(rsi14.iloc[-1]), 2),
            "vol_relativo": round(vol_rel, 1),
            "stage2": False,
            "historia_corta": True,
            "lectura": "Historia corta",
            "giro": None,
            "penalizaciones": ["Menos de 210 ruedas: sin lectura de medias"],
            "historico": hist,
        }
    )
    return fila


def analizar_activo(clave: str, cfg: dict, hist: pd.DataFrame, precio_ars: float | None, ccl: float | None) -> dict | None:
    if hist is None or len(hist) < 30:
        return None
    if len(hist) < MIN_RUEDAS:
        return _analisis_corto(clave, cfg, hist, precio_ars, ccl)
    close = hist["Close"].astype(float)
    volume = hist["Volume"].astype(float) if "Volume" in hist.columns else pd.Series(0.0, index=hist.index)
    sma10, sma20, sma50 = sma(close, 10), sma(close, 20), sma(close, 50)
    ema200 = ema(close, 200)
    rsi14 = rsi(close, 14)
    macd_line, macd_signal, _ = macd(close)
    boll_up, _, boll_low = bollinger(close)
    val_atr = atr(hist, 14)
    vol_media = sma(volume, 20)

    precio = float(close.iloc[-1])
    if not np.isfinite(precio) or precio <= 0:
        return None

    media_vol = vol_media.iloc[-1]
    vol_rel = float(volume.iloc[-1] / media_vol * 100) if pd.notna(media_vol) and media_vol > 0 else 100.0
    ema_hoy = ema200.iloc[-1]
    ema_prev = ema200.iloc[-20] if len(ema200) > 20 else ema200.iloc[0]
    stage2 = bool(pd.notna(ema_hoy) and pd.notna(ema_prev) and precio > ema_hoy and ema_hoy > ema_prev)

    penalizaciones: list[str] = []
    atr_hoy = val_atr.iloc[-1]
    apertura = float(hist["Open"].iloc[-1]) if "Open" in hist.columns else precio
    if pd.notna(atr_hoy) and float(atr_hoy) > 0 and (apertura - precio) > 2 * float(atr_hoy):
        penalizaciones.append("Caída mayor a 2× ATR")

    previo = _puntaje(-2, close, sma10, sma20, sma50, ema200, rsi14, macd_line, macd_signal, boll_up, boll_low)
    actual = _puntaje(-1, close, sma10, sma20, sma50, ema200, rsi14, macd_line, macd_signal, boll_up, boll_low)
    base_prev = etiqueta_por_puntaje(previo)
    base_act = etiqueta_por_puntaje(actual)
    anterior = float(close.iloc[-2])
    variacion = (precio / anterior - 1) * 100 if anterior else 0.0
    alerta = giro(base_prev, base_act, variacion)
    lectura = aplicar_riesgo(aplicar_volumen(base_act, vol_rel, variacion), bool(penalizaciones))

    fila = _fila_base(clave, cfg, precio, variacion, precio_ars, ccl)
    fila.update(
        {
            "rsi14": round(float(rsi14.iloc[-1]), 2),
            "vol_relativo": round(vol_rel, 1),
            "stage2": stage2,
            "historia_corta": False,
            "lectura": lectura,
            "giro": alerta,
            "penalizaciones": penalizaciones,
            "historico": hist.tail(320),
        }
    )
    return fila


def _ccl_apple(usd: dict[str, pd.DataFrame], ars: dict[str, pd.DataFrame]) -> float | None:
    precio_ars = _ultimo_precio(ars.get("AAPL.BA"))
    precio_usd = _ultimo_precio(usd.get("AAPL"))
    if not precio_ars or not precio_usd:
        return None
    return (precio_ars * 20) / precio_usd


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def cargar_panel(clave: str) -> dict:
    """Una descarga del universo por clave de cierre. `clave` invalida el caché."""
    reloj = time.perf_counter()
    simbolos_usd = [cfg["underlying"] for cfg in WATCHLIST.values()]
    simbolos_usd.extend(tickers_variable())
    simbolos_usd.append("SPY")
    simbolos_ars = [cfg["cedear"] for cfg in WATCHLIST.values()]

    usd, faltan_usd = descargar_simbolos(simbolos_usd, "2y")
    ars, faltan_ars = descargar_simbolos(simbolos_ars, "10d")
    if len(usd) < 20:
        raise RuntimeError("Yahoo Finance no devolvió cotizaciones suficientes.")

    ccl = _ccl_apple(usd, ars)
    filas = []
    historicos = {}
    sin_historia = []
    for clave_activo, cfg in WATCHLIST.items():
        historia = usd.get(cfg["underlying"])
        precio_ars = _ultimo_precio(ars.get(cfg["cedear"]))
        resultado = analizar_activo(clave_activo, cfg, historia, precio_ars, ccl)
        if resultado is None:
            if cfg["underlying"] not in faltan_usd:
                sin_historia.append(clave_activo)
            continue
        historicos[clave_activo] = resultado.pop("historico")
        filas.append(resultado)

    if not filas:
        raise RuntimeError("No se pudo armar ninguna lectura con los precios recibidos.")
    logging.warning(
        "Panel %s listo en %.1fs (%s lecturas, CCL %s, historia corta %s)",
        clave,
        time.perf_counter() - reloj,
        len(filas),
        None if ccl is None else round(ccl, 1),
        sin_historia,
    )

    cierres = {}
    for simbolo, historia in usd.items():
        cierres[simbolo] = historia["Close"]
    precios = pd.DataFrame(cierres).sort_index()

    return {
        "clave": clave,
        "ccl": None if ccl is None else float(ccl),
        "filas": pd.DataFrame(filas),
        "historicos": historicos,
        "precios_usd": precios,
        "sin_precio_usd": [k for k, cfg in WATCHLIST.items() if cfg["underlying"] in faltan_usd],
        "sin_precio_ars": [k for k, cfg in WATCHLIST.items() if cfg["cedear"] in faltan_ars],
        "sin_historia": sin_historia,
    }


@st.cache_data(ttl=60 * 60 * 4, show_spinner=False)
def ficha_activo(ticker_subyacente: str, clave: str) -> dict:
    """Consenso, balance y fundamentales. Solo se pide al abrir un activo."""
    del clave  # forma parte de la clave de caché junto con el cierre del día
    ticker = yf.Ticker(ticker_subyacente)
    info = {}
    try:
        crudo = ticker.info or {}
        if isinstance(crudo, dict):
            info = crudo
    except Exception:
        info = {}

    dias = None
    try:
        dias = dias_hasta_balance(ticker.get_calendar(), pd.Timestamp.now(tz="America/Argentina/Buenos_Aires").date())
    except Exception:
        dias = None
    if dias is None:
        try:
            fechas = ticker.get_earnings_dates(limit=12)
            if isinstance(fechas, pd.DataFrame) and not fechas.empty:
                dias = dias_hasta_balance({"Earnings Date": list(fechas.index)}, pd.Timestamp.now(tz="America/Argentina/Buenos_Aires").date())
        except Exception:
            dias = None

    return {
        "sector": info.get("sector") or info.get("quoteType") or "—",
        "recomendacion": info.get("recommendationKey"),
        "puntaje": info.get("recommendationMean"),
        "objetivo": info.get("targetMeanPrice"),
        "analistas": info.get("numberOfAnalystOpinions"),
        "per": info.get("trailingPE"),
        "per_forward": info.get("forwardPE"),
        "peg": info.get("pegRatio"),
        "roe": info.get("returnOnEquity"),
        "margen": info.get("profitMargins"),
        "deuda_patrimonio": info.get("debtToEquity"),
        "crecimiento": info.get("revenueGrowth"),
        "dividendo": info.get("dividendYield"),
        "dias_balance": dias,
        "balance_cerca": balance_en_ventana(dias),
    }
