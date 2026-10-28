"""Descarga en bloque y lectura del universo. Sin llamadas por activo."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from zeta.carteras import tickers_variable
from zeta.rotacion import simbolos_extra
from zeta.indicadores import atr, bollinger, ema, macd, rsi, sma
from zeta.senales import (
    aplicar_riesgo,
    aplicar_volumen,
    balance_en_ventana,
    dias_hasta_balance,
    etiqueta_por_puntaje,
    giro,
)
from zeta.contraste import AMARILLO, ROJO, VERDE, contrastar_cotizacion, registrar_desvio, ruta_log, semaforo
from zeta.fuentes import (
    ccl_data912,
    cotizaciones_acciones,
    cotizaciones_cedears,
    cuadro_cambiario,
    edad_cache,
    mediana,
    panel_ccl,
)
from zeta.tiempo import ahora_art, mercado_cedears_abierto
from zeta.universo import (
    ESTADO_NO,
    ESTADO_OK,
    cargar_universo,
    incorporar_faltantes,
    simbolo_byma,
    simbolos_pesos,
    usa_ratio,
)

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


def _ultima_fecha(series: dict[str, pd.DataFrame]) -> str | None:
    """Fecha de la última vela, no la hora en que se armó la página."""
    fechas = []
    for historia in series.values():
        if historia is None or historia.empty:
            continue
        fechas.append(pd.Timestamp(historia.index.max()))
    if not fechas:
        return None
    return max(fechas).strftime("%Y-%m-%d")


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


def _fecha_barra(historia: pd.DataFrame | None) -> pd.Timestamp | None:
    if historia is None or historia.empty:
        return None
    return pd.Timestamp(historia.index.max()).normalize()


def _cotizacion_viva(cfg: dict, cedears: dict | None, acciones: dict | None) -> dict | None:
    byma = cfg.get("byma") or simbolo_byma(cfg.get("cedear") or "")
    if cedears and byma in cedears:
        return cedears[byma]
    if acciones and byma in acciones:
        return acciones[byma]
    return None


def _fila_bloqueada(clave: str, cfg: dict, precio_ars: float | None, variacion: float | None, lectura: dict) -> dict:
    return {
        "ticker": clave,
        "nombre": cfg.get("name") or clave,
        "rubro": cfg.get("rubro") or "Sin verificar",
        "precio_usd": None,
        "variacion": None if variacion is None else round(variacion, 2),
        "precio_ars": None if precio_ars is None else round(precio_ars, 2),
        "gap_ccl": None,
        "rsi14": None,
        "vol_relativo": None,
        "stage2": False,
        "historia_corta": False,
        "lectura": "Sin señal",
        "giro": None,
        "penalizaciones": [lectura.get("motivo") or "Contraste en rojo"],
        "contraste": lectura.get("estado") or ROJO,
        "contraste_motivo": lectura.get("motivo") or "",
    }


def _fila_sin_verificar(clave: str, cfg: dict, precio_ars: float | None, variacion: float | None) -> dict:
    return {
        "ticker": clave,
        "nombre": cfg.get("name") or clave,
        "rubro": cfg.get("rubro") or "Sin verificar",
        "precio_usd": None,
        "variacion": None if variacion is None else round(float(variacion), 2),
        "precio_ars": None if precio_ars is None else round(float(precio_ars), 2),
        "gap_ccl": None,
        "lectura": "Sin verificar",
        "contraste": "—",
        "contraste_motivo": cfg.get("motivo") or "Ratio sin verificar",
        "estado": ESTADO_NO,
    }


def ensamblar_panel(
    universo: dict[str, dict],
    usd: dict[str, pd.DataFrame],
    ars: dict[str, pd.DataFrame],
    faltan_usd: list[str],
    faltan_ars: list[str],
    vivos: dict[str, dict] | None,
    acciones: dict[str, dict] | None,
    *,
    mercado_abierto: bool,
    hoy: pd.Timestamp,
    edad_minutos: float | None,
    ccl_feed: float | None,
    momento,
    log_ruta=None,
    clave: str = "",
) -> dict:
    """Arma las filas. En contraste rojo no llama al puntaje de la señal."""
    fuente_caida = not vivos
    libro = []
    for clave_activo, cfg in universo.items():
        quote = None if fuente_caida else _cotizacion_viva(cfg, vivos, acciones)
        yahoo = ars.get(cfg.get("cedear") or "")
        precio_yahoo = _ultimo_precio(yahoo)
        precio_vivo = float(quote["c"]) if quote and quote.get("c") else None
        variacion_viva = quote.get("pct_change") if quote else None
        if fuente_caida:
            lectura = {
                "estado": AMARILLO,
                "motivo": "data912 no respondió. La señal usa el precio de Yahoo, sin contraste en vivo.",
                "bloquea_senal": False,
                "diferencia": None,
                "comparo": "fuente_caida",
            }
            precio_ars = precio_yahoo
        elif precio_vivo is not None:
            lectura = contrastar_cotizacion(
                precio_vivo=precio_vivo,
                variacion_pct=variacion_viva,
                precio_yahoo=precio_yahoo,
                yahoo_es_hoy=_fecha_barra(yahoo) == hoy.normalize() if precio_yahoo else False,
                edad_minutos=edad_minutos,
                mercado_abierto=mercado_abierto,
            )
            precio_ars = precio_vivo
        elif precio_yahoo is not None:
            lectura = semaforo(precio_yahoo, None)
            lectura["motivo"] = "Sin cotización en data912 para este símbolo."
            lectura["bloquea_senal"] = False
            precio_ars = precio_yahoo
        else:
            lectura = {
                "estado": AMARILLO,
                "motivo": "Sin precio en pesos.",
                "bloquea_senal": False,
                "diferencia": None,
                "comparo": "sin_precio",
            }
            precio_ars = None
        libro.append((clave_activo, cfg, precio_ars, variacion_viva, precio_yahoo, lectura))

    pares = []
    for clave_activo, cfg, precio_ars, _variacion, _yahoo, lectura in libro:
        if not usa_ratio(cfg) or lectura.get("bloquea_senal"):
            continue
        usd_px = _ultimo_precio(usd.get(cfg.get("underlying") or ""))
        if precio_ars and usd_px and cfg.get("ratio"):
            pares.append((precio_ars * float(cfg["ratio"])) / usd_px)
    ccl = mediana(pares)
    ccl_fuente = "pares verificados"
    if ccl is None and ccl_feed is not None:
        ccl = float(ccl_feed)
        ccl_fuente = "data912 (varios tickers)"

    filas = []
    historicos = {}
    sin_historia = []
    sin_senal = []
    sin_verificar = []
    configs = {}
    for clave_activo, cfg, precio_ars, variacion_viva, _yahoo, lectura in libro:
        hay_desvio = lectura.get("estado") == ROJO or (
            lectura.get("estado") == AMARILLO and lectura.get("diferencia") is not None
        )
        if log_ruta is not None and hay_desvio:
            registrar_desvio(
                log_ruta,
                {
                    "momento": momento.isoformat() if hasattr(momento, "isoformat") else str(momento),
                    "tipo": "precio",
                    "clave": clave_activo,
                    "valor_principal": "" if precio_ars is None else precio_ars,
                    "fuente_principal": "data912" if not fuente_caida else "Yahoo",
                    "valor_contraste": "" if _yahoo is None else _yahoo,
                    "fuente_contraste": "Yahoo .BA",
                    "diferencia_pct": "" if lectura.get("diferencia") is None else lectura["diferencia"],
                    "estado": lectura.get("estado"),
                    "motivo": lectura.get("motivo") or "",
                },
            )
        if not usa_ratio(cfg):
            sin_verificar.append(_fila_sin_verificar(clave_activo, cfg, precio_ars, variacion_viva))
            continue
        if lectura.get("bloquea_senal"):
            sin_senal.append(_fila_bloqueada(clave_activo, cfg, precio_ars, variacion_viva, lectura))
            continue
        historia = usd.get(cfg.get("underlying") or "")
        resultado = analizar_activo(clave_activo, cfg, historia, precio_ars, ccl)
        if resultado is None:
            if cfg.get("underlying") not in faltan_usd:
                sin_historia.append(clave_activo)
            continue
        historicos[clave_activo] = resultado.pop("historico")
        resultado["contraste"] = lectura.get("estado") or VERDE
        resultado["contraste_motivo"] = lectura.get("motivo") or ""
        resultado["sector_estado"] = cfg.get("sector_estado") or ESTADO_NO
        filas.append(resultado)
        configs[clave_activo] = cfg

    if not filas and not sin_senal and not sin_verificar:
        raise RuntimeError("No se pudo armar ninguna lectura con los precios recibidos.")

    cierres = {simbolo: historia["Close"] for simbolo, historia in usd.items()}
    verificados = [clave_activo for clave_activo, cfg, *_resto in libro if usa_ratio(cfg)]
    return {
        "clave": clave,
        "ccl": None if ccl is None else float(ccl),
        "ccl_pares": len(pares),
        "ccl_fuente": ccl_fuente,
        "filas": pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["ticker", "nombre", "rubro", "precio_usd", "variacion", "precio_ars", "gap_ccl", "rsi14", "vol_relativo", "stage2", "historia_corta", "lectura", "giro", "penalizaciones", "contraste", "contraste_motivo", "sector_estado"]
        ),
        "historicos": historicos,
        "precios_usd": pd.DataFrame(cierres).sort_index(),
        "sin_precio_usd": [k for k in verificados if universo[k].get("underlying") in faltan_usd],
        "sin_precio_ars": [k for k in verificados if universo[k].get("cedear") in faltan_ars and k not in {f["ticker"] for f in sin_senal}],
        "sin_historia": sin_historia,
        "sin_senal": pd.DataFrame(sin_senal),
        "sin_verificar": pd.DataFrame(sin_verificar),
        "configs": configs,
        "fuente_viva": not fuente_caida,
        "obtenido_en": momento.isoformat() if hasattr(momento, "isoformat") else str(momento),
        "ultima_rueda": _ultima_fecha(usd),
        "ultima_rueda_ars": _ultima_fecha(ars),
    }


def universo_de_senales() -> dict[str, dict]:
    """Los que tienen ratio verificado y subyacente: son los que bajan historia."""
    return {
        ticker: cfg
        for ticker, cfg in cargar_universo().items()
        if usa_ratio(cfg) and cfg.get("underlying")
    }


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def _historia(clave: str) -> dict:
    """Historia de Yahoo. `clave` es el cierre del día: no se renueva a cada clic."""
    universo = universo_de_senales()
    simbolos_usd = [cfg["underlying"] for cfg in universo.values()]
    simbolos_usd.extend(tickers_variable())
    simbolos_usd.extend(simbolos_extra())
    simbolos_usd.append("SPY")
    simbolos_ars = [cfg["cedear"] for cfg in universo.values() if cfg.get("cedear")]
    usd, faltan_usd = descargar_simbolos(simbolos_usd, "2y")
    ars, faltan_ars = descargar_simbolos(simbolos_ars, "10d")
    if len(usd) < 20:
        raise RuntimeError("Yahoo Finance no devolvió cotizaciones suficientes.")
    return {"usd": usd, "ars": ars, "faltan_usd": faltan_usd, "faltan_ars": faltan_ars, "clave": clave}


@st.cache_data(ttl=60, show_spinner=False)
def cargar_panel(clave: str) -> dict:
    """Historia de Yahoo (caché del día) y precios en vivo de data912 (al menos un minuto)."""
    reloj = time.perf_counter()
    historia = _historia(clave)
    vivos = cotizaciones_cedears()
    acciones = cotizaciones_acciones()
    universo = cargar_universo()
    if vivos:
        universo = incorporar_faltantes(universo, simbolos_pesos(vivos))
    momento = ahora_art()
    hoy = pd.Timestamp(momento.date())
    log = ruta_log(Path(__file__).resolve().parent.parent / "logs", momento.to_pydatetime())
    ccl_feed = ccl_data912(panel_ccl())
    panel = ensamblar_panel(
        universo,
        historia["usd"],
        historia["ars"],
        historia["faltan_usd"],
        historia["faltan_ars"],
        vivos,
        acciones,
        mercado_abierto=mercado_cedears_abierto(momento),
        hoy=hoy,
        edad_minutos=edad_cache("cedears"),
        ccl_feed=ccl_feed,
        momento=momento,
        log_ruta=log,
        clave=clave,
    )
    cuadro = cuadro_cambiario(ccl_calculado=panel["ccl"], momento=momento.isoformat(), log_ruta=log)
    panel["dolares"] = cuadro
    logging.warning(
        "Panel %s listo en %.1fs (%s lecturas, %s sin verificar, %s sin señal, CCL %s de %s pares)",
        clave,
        time.perf_counter() - reloj,
        len(panel["filas"]),
        len(panel["sin_verificar"]),
        len(panel["sin_senal"]),
        None if panel["ccl"] is None else round(panel["ccl"], 1),
        panel["ccl_pares"],
    )
    return panel


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
        "obtenido_en": ahora_art().isoformat(),
    }
