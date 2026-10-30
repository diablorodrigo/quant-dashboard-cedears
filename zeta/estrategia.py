"""Cruce de medias con volumen para la pestaña Señales.

La compra es el cruce de la SMA rápida sobre la media, con volumen.
La confirmación es el cruce de la rápida sobre la lenta dentro de la ventana:
en la pantalla es la Compra fuerte. La compra sola es la Compra débil.
Si la débil se confirma mientras sigue abierta, es la misma posición teórica:
la tabla muestra una sola fila, Compra fuerte, con las dos fechas.

La entrada teórica es la apertura de la rueda siguiente. Se sale por el stop,
por tiempo, o por cruce bajista si el config lo activa. «Venta» es esa salida
de la posición teórica, no una orden sobre la cartera.

Los parámetros viven en ``data/estrategia_senales.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from zeta.contraste import ROJO

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CONFIG = RAIZ / "data" / "estrategia_senales.json"
RUTA_BACKTEST = RAIZ / "data" / "estrategia_backtest.json"

# Cristian lo revisa. Va justo arriba de la tabla de señales.
AVISO_CONTEXTO = (
    "Es una guía de contexto, no una promesa. Las señales se basan en análisis cuantitativo."
)

# Cristian lo revisa. Es el texto fijo al pie de esta pestaña.
AVISO_ESTRATEGIA = (
    "Son criterios cuantitativos y no una recomendación de inversión ni una oferta "
    "de compra o venta. No son 100% efectivos y los resultados pasados no garantizan "
    "resultados futuros. Cada persona debe hacer su propio análisis antes de operar."
)

LIMITACIONES = (
    "En ETFs la muestra es muy chica y la ventaja frente a un día al azar es mínima. "
    "Diez ETFs se leen en dólares MEP (especie D), con unos 20 meses de historia y sin el efecto del CCL. "
    "Hay sesgo de supervivencia: el universo es el que hoy tiene serie. "
    "Los retornos en pesos incluyen la suba del CCL. No hay impuestos: "
    "el 0,6% y el 1,2% son un supuesto de ida y vuelta, no la tarifa de un broker. "
    "La señal se calcula al cierre y la entrada es la apertura siguiente; un gap puede "
    "empeorar el stop. El drawdown es la suma de operaciones sueltas, no una cartera."
)

MOTIVOS_SALIDA = {
    "stop": "Tocó el stop.",
    "tiempo": "Cumplió las ruedas de la salida por tiempo.",
    "cruce": "Cruzó para abajo.",
    "abierta": "La posición teórica sigue abierta.",
}


def cargar_backtest(ruta: Path | None = None) -> dict:
    """Cifras publicadas. La pantalla las muestra tal cual: no las recalcula."""
    datos = json.loads((ruta or RUTA_BACKTEST).read_text(encoding="utf-8"))
    estudios = datos.get("estudios") or []
    if not isinstance(estudios, list) or not estudios:
        raise ValueError("El archivo de backtest no trae estudios.")
    for estudio in estudios:
        if not estudio.get("filas"):
            raise ValueError(f"El estudio {estudio.get('id') or estudio.get('titulo')} no trae filas.")
    return datos


# Un solo nombre en todo el panel. El singular viejo se muestra igual, por si queda un dato anterior.
NOMBRE_CUADRANTE = {
    "Líder": "Líderes",
    "Líderes": "Líderes",
    "Mejorando": "Mejorando",
    "Debilitándose": "Debilitándose",
    "Rezagado": "Rezagados",
    "Rezagados": "Rezagados",
}
_A_FAVOR = {
    "compra": {"Líderes", "Mejorando"},
    "venta": {"Debilitándose", "Rezagados"},
}


def cargar_config(ruta: Path | None = None) -> dict:
    datos = json.loads((ruta or RUTA_CONFIG).read_text(encoding="utf-8"))
    universos = datos.get("universos")
    if not universos:
        tickers = datos.get("tickers", [])
        if isinstance(tickers, str):
            tickers = tickers.split()
        universos = [{"id": "lista", "titulo": "Lista", "nota": "", "tickers": tickers}]
        datos["universo_default"] = "lista"
    limpios = []
    for universo in universos:
        tickers = universo.get("tickers", [])
        if isinstance(tickers, str):
            tickers = tickers.split()
        sin_historia = universo.get("sin_historia") or []
        if isinstance(sin_historia, str):
            sin_historia = sin_historia.split()
        especies = []
        for item in universo.get("especies") or []:
            ticker = str(item.get("ticker") or "")
            if not ticker:
                continue
            yahoo = str(item.get("simbolo_yahoo") or f"{ticker.replace('.', '-')}.BA")
            data912 = str(item.get("simbolo_data912") or yahoo[:-3])
            serie = str(item.get("serie") or "ARS (especie pesos)")
            moneda = str(item.get("moneda") or ("USD MEP" if "USD" in serie else "ARS"))
            especies.append(
                {
                    "ticker": ticker,
                    "nombre": item.get("nombre") or ticker,
                    "serie": serie,
                    "moneda": moneda,
                    "simbolo_yahoo": yahoo,
                    "simbolo_data912": data912,
                }
            )
        if not tickers and especies:
            tickers = [e["ticker"] for e in especies]
        limpios.append(
            {
                "id": str(universo.get("id") or "lista"),
                "titulo": universo.get("titulo") or universo.get("id") or "Lista",
                "nota": universo.get("nota") or "",
                "tickers": [str(t) for t in tickers],
                "sin_historia": [str(t) for t in sin_historia],
                "especies": especies,
            }
        )
    datos["universos"] = limpios
    datos.setdefault("universo_default", limpios[0]["id"])
    datos.setdefault("close_hour", 17)
    datos.setdefault("exit_cross", None)
    datos.setdefault("cost_base", 0.006)
    datos.setdefault("cost_conservative", 0.012)
    datos.setdefault("recent_days", 10)
    datos.setdefault("confirm_window", 30)
    datos.setdefault("max_hold", 20)
    datos.setdefault("vol_mult", 1.5)
    return datos


def universo_por_id(cfg: dict, universo_id: str | None = None) -> dict:
    elegido = universo_id or cfg.get("universo_default")
    for universo in cfg.get("universos") or []:
        if universo["id"] == elegido:
            return universo
    universos = cfg.get("universos") or []
    return universos[0] if universos else {"id": "", "titulo": "", "nota": "", "tickers": []}


def tickers_de(cfg: dict, universo_id: str | None = None) -> list[str]:
    return list(universo_por_id(cfg, universo_id).get("tickers") or [])


def especies_de(cfg: dict, universo_id: str | None = None) -> list[dict]:
    """Cada ETF con la moneda de su serie y el símbolo de Yahoo y de data912."""
    universo = universo_por_id(cfg, universo_id)
    if universo.get("especies"):
        return list(universo["especies"])
    return [
        {
            "ticker": ticker,
            "nombre": ticker,
            "serie": "ARS (especie pesos)",
            "moneda": "ARS",
            "simbolo_yahoo": f"{str(ticker).replace('.', '-')}.BA",
            "simbolo_data912": str(ticker).replace(".", ""),
        }
        for ticker in universo.get("tickers") or []
    ]


def relacion_rrg(senal: str, cuadrante: str | None) -> str:
    """Compra con Líderes o Mejorando coincide. Venta con esos cuadrantes se contradice."""
    if not cuadrante:
        return "sin cuadrante"
    cuadrante = NOMBRE_CUADRANTE.get(cuadrante, cuadrante)
    texto = (senal or "").lower()
    if "venta" in texto:
        lado = "venta"
    elif "compra" in texto:
        lado = "compra"
    else:
        return "sin cuadrante"
    if cuadrante in _A_FAVOR[lado]:
        return "coincide"
    return "contradice"


def recortar_vela_abierta(df: pd.DataFrame, ahora: pd.Timestamp, hora_cierre: int = 17) -> pd.DataFrame:
    """Antes del cierre no se usa la vela del día: la señal es al cierre."""
    if df is None or df.empty:
        return df
    ultima = pd.Timestamp(df.index[-1])
    if ultima.tzinfo is not None:
        ultima = ultima.tz_localize(None)
    dia = ahora.tz_localize(None).date() if getattr(ahora, "tzinfo", None) else pd.Timestamp(ahora).date()
    if ultima.date() == dia and int(ahora.hour) < int(hora_cierre):
        return df.iloc[:-1]
    return df


def preparar_serie(df: pd.DataFrame) -> pd.DataFrame:
    """Deja OHLCV y saca las ruedas sin volumen, que distorsionan la media."""
    if df is None or df.empty:
        return pd.DataFrame()
    columnas = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    out = df[columnas].copy()
    if "Volume" in out.columns:
        out = out[out["Volume"].fillna(0) > 0]
    return out.dropna(subset=["Close"])


def cruce_al_alza(rapida: pd.Series, lenta: pd.Series) -> pd.Series:
    """Ayer la rápida no superaba a la lenta; hoy sí."""
    return (rapida > lenta) & (rapida.shift(1) <= lenta.shift(1))


def ratio_volumen(volume: pd.Series, promedio: int, mirada: int) -> pd.Series:
    """Máximo entre el volumen del día y el promedio corto, contra el promedio previo."""
    base = volume.rolling(promedio).mean().shift(1)
    reciente = volume.rolling(mirada).mean()
    return pd.concat([volume / base, reciente / base], axis=1).max(axis=1)


def _indicadores(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    d = df.copy()
    precio = d["Close"].astype(float)
    for n in {int(cfg["fast"]), int(cfg["mid"]), int(cfg["slow"]), 20, 50}:
        d[f"sma{n}"] = precio.rolling(n).mean()
    d["vol_ratio"] = ratio_volumen(d["Volume"].astype(float), int(cfg["vol_avg"]), int(cfg["vol_lookback"]))
    previo = precio.shift(1)
    tr = pd.concat(
        [(d["High"] - d["Low"]).abs(), (d["High"] - previo).abs(), (d["Low"] - previo).abs()],
        axis=1,
    ).max(axis=1)
    d["atr"] = tr.rolling(int(cfg["atr_period"])).mean()
    return d


def nivel_stop(entrada: float, stop: dict, atr: float | None = None) -> float | None:
    tipo = (stop or {}).get("type")
    if tipo == "pct":
        return round(entrada * (1 - float(stop["pct"]) / 100), 2)
    if tipo == "atr" and atr is not None and np.isfinite(atr):
        return round(entrada - float(stop["mult"]) * float(atr), 2)
    return None


def detectar_senales(df: pd.DataFrame, cfg: dict, ticker: str = "") -> list[dict]:
    """Compras con volumen y confirmaciones dentro de la ventana.

    Una confirmación consume la compra: el próximo cruce lento no la vuelve a contar.
    """
    if df is None or len(df) < int(cfg["slow"]) + 5:
        return []
    d = _indicadores(df, cfg)
    rapida = d[f"sma{int(cfg['fast'])}"]
    media = d[f"sma{int(cfg['mid'])}"]
    lenta = d[f"sma{int(cfg['slow'])}"]
    compras = (cruce_al_alza(rapida, media) & (d["vol_ratio"] >= float(cfg["vol_mult"]))).fillna(False)
    confirmaciones = cruce_al_alza(rapida, lenta).fillna(False)
    eventos: list[dict] = []
    ultima_compra: int | None = None
    ventana = int(cfg["confirm_window"])
    for i in range(len(d)):
        if bool(compras.iloc[i]):
            ultima_compra = i
            eventos.append(_evento(ticker, d, i, "compra", cfg))
        if (
            ultima_compra is not None
            and bool(confirmaciones.iloc[i])
            and i - ultima_compra <= ventana
        ):
            evento = _evento(ticker, d, i, "confirmacion", cfg)
            evento["dias_desde_compra"] = i - ultima_compra
            eventos.append(evento)
            ultima_compra = None
    return eventos


def _evento(ticker: str, d: pd.DataFrame, i: int, tipo: str, cfg: dict) -> dict:
    precio = float(d["Close"].iloc[i])
    rapida = d[f"sma{int(cfg['fast'])}"].iloc[i]
    lenta = d[f"sma{int(cfg['slow'])}"].iloc[i]
    atr = d["atr"].iloc[i]
    return {
        "ticker": ticker,
        "fecha": str(pd.Timestamp(d.index[i]).date()),
        "tipo": tipo,
        "precio": round(precio, 2),
        "ratio_volumen": round(float(d["vol_ratio"].iloc[i]), 2) if pd.notna(d["vol_ratio"].iloc[i]) else None,
        "sma10_sobre_sma50": bool(pd.notna(rapida) and pd.notna(lenta) and rapida > lenta),
        "stop_sugerido": nivel_stop(precio, cfg["stop"], None if pd.isna(atr) else float(atr)),
        "idx": i,
    }


def _precio_salida_stop(apertura: float, minimo: float, nivel: float) -> float | None:
    if minimo > nivel:
        return None
    if apertura <= nivel:
        return apertura
    return nivel


def backtest(
    df: pd.DataFrame,
    senales: list[dict],
    stop: dict,
    max_hold: int = 20,
    exit_cross: tuple[str, str] | None = None,
    cost: float = 0.0,
    include_open: bool = False,
    cfg: dict | None = None,
) -> list[dict]:
    """Entra en la apertura siguiente. El stop se mira con el mínimo; si abre debajo, sale ahí."""
    if df is None or df.empty:
        return []
    d = _indicadores(
        df,
        cfg or {"fast": 10, "mid": 20, "slow": 50, "vol_avg": 20, "vol_lookback": 3, "atr_period": 14},
    )
    trades = []
    for senal in senales:
        i = int(senal["idx"]) + 1
        if i >= len(d):
            continue
        entrada = float(d["Open"].iloc[i])
        atr_prev = d["atr"].iloc[i - 1] if "atr" in d.columns else None
        nivel = nivel_stop(entrada, stop, None if atr_prev is None or pd.isna(atr_prev) else float(atr_prev))
        salida = None
        motivo = None
        j = i
        limite = min(i + int(max_hold), len(d))
        for j in range(i, limite):
            apertura = float(d["Open"].iloc[j])
            minimo = float(d["Low"].iloc[j])
            cierre = float(d["Close"].iloc[j])
            if nivel is not None:
                precio_stop = _precio_salida_stop(apertura, minimo, nivel)
                if precio_stop is not None:
                    salida = precio_stop
                    motivo = "stop"
                    break
            if exit_cross and j > i:
                rapida = d[exit_cross[0]].iloc[j]
                lenta = d[exit_cross[1]].iloc[j]
                if pd.notna(rapida) and pd.notna(lenta) and rapida < lenta:
                    salida = cierre
                    motivo = "cruce"
                    break
        else:
            j = limite - 1
            salida = float(d["Close"].iloc[j])
            motivo = "tiempo"
            if i + int(max_hold) > len(d):
                if not include_open:
                    continue
                motivo = "abierta"
        trades.append(
            {
                "ticker": senal.get("ticker", ""),
                "tipo": senal.get("tipo", "compra"),
                "fecha_senal": senal.get("fecha"),
                "entrada": str(pd.Timestamp(d.index[i]).date()),
                "precio_entrada": round(entrada, 2),
                "fecha_salida": str(pd.Timestamp(d.index[j]).date()),
                "precio_salida": round(float(salida), 2),
                "exit_idx": j,
                "ret": float(salida) / entrada - 1 - float(cost),
                "dias": j - i + 1,
                "salida": motivo,
                "stop": None if nivel is None else round(nivel, 2),
                "idx_senal": senal.get("idx"),
            }
        )
    return trades


def resumir(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0}
    retornos = pd.Series([t["ret"] for t in trades], dtype=float)
    equity = retornos.cumsum()
    drawdown = float((equity - equity.cummax()).min())
    ganadoras = retornos[retornos > 0]
    perdedoras = retornos[retornos <= 0]
    ratio = None
    if len(ganadoras) and len(perdedoras) and float(perdedoras.mean()) != 0:
        ratio = round(float(ganadoras.mean()) / abs(float(perdedoras.mean())), 2)
    return {
        "n": int(len(retornos)),
        "media": round(float(retornos.mean()) * 100, 2),
        "mediana": round(float(retornos.median()) * 100, 2),
        "acierto": round(float((retornos > 0).mean()) * 100, 1),
        "peor": round(float(retornos.min()) * 100, 1),
        "dd_max": round(drawdown * 100, 1),
        "ganancia_perdida": ratio,
        "dias_prom": round(float(np.mean([t["dias"] for t in trades])), 1),
    }


def _trades_de(df: pd.DataFrame, eventos: list[dict], cfg: dict, *, cost: float, include_open: bool) -> list[dict]:
    cruce = tuple(cfg["exit_cross"]) if cfg.get("exit_cross") else None
    return backtest(
        df,
        eventos,
        cfg["stop"],
        int(cfg["max_hold"]),
        cruce,
        cost=cost,
        include_open=include_open,
        cfg=cfg,
    )


def estado_ticker(ticker: str, df: pd.DataFrame, cfg: dict) -> dict:
    """Estado al último cierre: abiertas, ventas recientes y la etiqueta."""
    df = preparar_serie(df)
    eventos = detectar_senales(df, cfg, ticker)
    if df is None or df.empty:
        return {"ticker": ticker, "etiqueta": None, "eventos": [], "posiciones_abiertas": [], "ventas_recientes": []}
    n = len(df)
    d = _indicadores(df, cfg)
    mirada = int(cfg["max_hold"]) + int(cfg["recent_days"]) + 1
    recientes = [e for e in eventos if e["idx"] >= n - mirada]
    trades = _trades_de(df, [e for e in recientes if e["idx"] + 1 < n], cfg, cost=0.0, include_open=True)
    ventas = []
    abiertas = []
    for evento, trade in zip([e for e in recientes if e["idx"] + 1 < n], trades):
        if trade["salida"] == "abierta":
            abiertas.append(
                {
                    "origen": evento["tipo"],
                    "fecha_senal": evento["fecha"],
                    "precio_entrada": trade["precio_entrada"],
                    "stop": trade["stop"],
                    "ruedas": trade["dias"],
                    "ret_pct": round(trade["ret"] * 100, 2),
                    "fecha_ultimo": trade["fecha_salida"],
                    "idx": evento.get("idx"),
                    "idx_compra": _idx_compra(evento),
                }
            )
        elif trade["exit_idx"] >= n - int(cfg["recent_days"]):
            ventas.append(
                {
                    "ticker": ticker,
                    "fecha": trade["fecha_salida"],
                    "fecha_senal": evento["fecha"],
                    "tipo": "venta",
                    "motivo": trade["salida"],
                    "origen": evento["tipo"],
                    "precio_salida": trade["precio_salida"],
                    "precio_entrada": trade["precio_entrada"],
                    "stop": trade["stop"],
                    "ret_pct": round(trade["ret"] * 100, 2),
                    "ruedas": trade["dias"],
                    "idx": evento.get("idx"),
                    "idx_compra": _idx_compra(evento),
                }
            )
    senales_recientes = [e for e in eventos if e["idx"] >= n - int(cfg["recent_days"])]
    if ventas and not abiertas:
        etiqueta = "Venta"
    elif senales_recientes or abiertas:
        etiqueta = "Compra"
    else:
        etiqueta = None
    ultimo = float(d["Close"].iloc[-1])
    return {
        "ticker": ticker,
        "fecha": str(pd.Timestamp(d.index[-1]).date()),
        "ultimo_cierre": round(ultimo, 2),
        "etiqueta": etiqueta,
        "eventos": eventos,
        "senal_reciente": senales_recientes,
        "posiciones_abiertas": abiertas,
        "ventas_recientes": ventas,
    }


def _idx_compra(evento: dict) -> int | None:
    """La confirmación apunta a la compra que consumió. Sin eso, no hay cadena."""
    if evento.get("tipo") != "confirmacion":
        return None
    if evento.get("idx") is None or evento.get("dias_desde_compra") is None:
        return None
    return int(evento["idx"]) - int(evento["dias_desde_compra"])


def fuerza_compra(estado: dict) -> str:
    """La confirmación es la señal fuerte. La compra sola es la débil."""
    if any(p.get("origen") == "confirmacion" for p in estado.get("posiciones_abiertas") or []):
        return "fuerte"
    if any(e.get("tipo") == "confirmacion" for e in estado.get("senal_reciente") or []):
        return "fuerte"
    return "debil"


def filas_de_estado(estado: dict, ultimo: float | None = None) -> list[dict]:
    """Como máximo una fila vigente por ETF. Sin etiqueta, nada.

    La compra y la confirmación que la consume son la misma posición. Si
    conviven, queda Compra fuerte: la entrada es la de la compra original
    y se ven las dos fechas. Dos ventas de esa cadena también colapsan.
    """
    if not estado.get("etiqueta"):
        return []
    precio = float(ultimo) if ultimo else float(estado["ultimo_cierre"])
    filas = []
    if estado["etiqueta"] == "Compra":
        posiciones = estado.get("posiciones_abiertas") or []
        if not posiciones:
            for evento in estado.get("senal_reciente") or []:
                filas.append(_fila_pendiente(estado, evento, precio))
            return consolidar_filas(filas)
        ya = {p["fecha_senal"] for p in posiciones}
        for posicion in posiciones:
            # La confirmación es la señal fuerte. La compra que todavía no confirmó es la débil.
            es_fuerte = posicion.get("origen") == "confirmacion"
            entrada = float(posicion["precio_entrada"])
            filas.append(
                {
                    "ticker": estado["ticker"],
                    "senal": "Compra fuerte" if es_fuerte else "Compra débil",
                    "fuerza": "fuerte" if es_fuerte else "debil",
                    "origen": posicion.get("origen") or ("confirmacion" if es_fuerte else "compra"),
                    "fecha": posicion["fecha_senal"],
                    "fecha_confirmacion": posicion["fecha_senal"] if es_fuerte else None,
                    "idx": posicion.get("idx"),
                    "idx_compra": posicion.get("idx_compra"),
                    "precio_entrada": entrada,
                    "stop": posicion.get("stop"),
                    "ultimo": round(precio, 2),
                    "desde_senal": round((precio / entrada - 1) * 100, 2) if entrada else None,
                    "ruedas": posicion.get("ruedas"),
                    "estado_posicion": "abierta",
                    "motivo": None,
                    "detalle": _detalle_compra(es_fuerte, posicion),
                }
            )
        for evento in estado.get("senal_reciente") or []:
            # Señal del último cierre: la apertura siguiente todavía no existe.
            if evento["fecha"] == estado["fecha"] and evento["fecha"] not in ya:
                filas.append(_fila_pendiente(estado, evento, precio))
        return consolidar_filas(filas)
    for venta in estado.get("ventas_recientes") or []:
        entrada = float(venta["precio_entrada"])
        filas.append(
            {
                "ticker": estado["ticker"],
                "senal": "Venta",
                "fuerza": None,
                "origen": venta.get("origen") or "compra",
                "fecha": venta["fecha"],
                "fecha_senal": venta["fecha_senal"],
                "fecha_confirmacion": venta["fecha_senal"] if venta.get("origen") == "confirmacion" else None,
                "idx": venta.get("idx"),
                "idx_compra": venta.get("idx_compra"),
                "precio_entrada": entrada,
                "precio_salida": venta["precio_salida"],
                "stop": venta.get("stop"),
                "ultimo": round(precio, 2),
                "desde_senal": venta["ret_pct"],
                "ruedas": venta.get("ruedas"),
                "estado_posicion": "cerrada",
                "motivo": venta.get("motivo"),
                "detalle": (
                    f"Salió el {venta['fecha']}. {MOTIVOS_SALIDA.get(venta.get('motivo'), '')} "
                    "No es una instrucción de vender lo que tengas: es la salida de la posición teórica."
                ),
            }
        )
    return consolidar_filas(filas)


def _detalle_compra(fuerte: bool, posicion: dict) -> str:
    if fuerte:
        return (
            f"Compra fuerte: la media de 10 cruzó para arriba a la de 50 "
            f"(señal del {posicion['fecha_senal']}). "
            f"Va por la rueda {posicion.get('ruedas')} desde la entrada."
        )
    return (
        f"Compra débil: la media de 10 cruzó a la de 20 con volumen "
        f"(señal del {posicion['fecha_senal']}). La confirmación con la media de 50 todavía no llegó. "
        f"Va por la rueda {posicion.get('ruedas')} desde la entrada."
    )


def _detalle_confirmada(fila: dict) -> str:
    compra = fila.get("fecha_compra") or fila.get("fecha")
    confirmacion = fila.get("fecha_confirmacion")
    texto = (
        f"Compra fuerte: la media de 10 cruzó a la de 20 con volumen "
        f"(compra del {compra}) y después cruzó para arriba a la de 50 "
        f"(confirmación del {confirmacion}). Es la misma posición teórica."
    )
    if fila.get("estado_posicion") == "pendiente" or fila.get("precio_entrada") is None:
        return texto + " La entrada teórica es la apertura de la rueda siguiente; todavía no hay precio."
    return texto + f" Va por la rueda {fila.get('ruedas')} desde la entrada."


def _fila_pendiente(estado: dict, evento: dict, precio: float) -> dict:
    fuerte = evento.get("tipo") == "confirmacion"
    return {
        "ticker": estado["ticker"],
        "senal": "Compra fuerte" if fuerte else "Compra débil",
        "fuerza": "fuerte" if fuerte else "debil",
        "origen": evento.get("tipo") or "compra",
        "fecha": evento["fecha"],
        "fecha_confirmacion": evento["fecha"] if fuerte else None,
        "idx": evento.get("idx"),
        "idx_compra": _idx_compra(evento),
        "precio_entrada": None,
        "stop": evento.get("stop_sugerido"),
        "ultimo": round(precio, 2),
        "desde_senal": None,
        "ruedas": 0,
        "estado_posicion": "pendiente",
        "motivo": None,
        "detalle": "La señal es de este cierre. La entrada teórica es la apertura de la rueda siguiente; todavía no hay precio.",
    }


def _fecha_de_senal(fila: dict) -> str:
    if fila.get("estado_posicion") == "cerrada":
        return str(fila.get("fecha_senal") or fila.get("fecha") or "")
    return str(fila.get("fecha") or "")


def _es_confirmacion(fila: dict) -> bool:
    # Una fila ya fusionada conserva el origen «compra» y la etiqueta fuerte.
    # No vuelve a buscar otra compra a la que pegarse.
    if fila.get("origen") == "compra":
        return False
    return fila.get("origen") == "confirmacion" or fila.get("fuerza") == "fuerte"


def _buscar_origen(confirmacion: dict, compras: list[dict], usadas: set[int]) -> dict | None:
    idx_compra = confirmacion.get("idx_compra")
    if idx_compra is not None:
        for compra in compras:
            if id(compra) not in usadas and compra.get("idx") == idx_compra:
                return compra
        # El idx dice a qué compra pertenece. Si esa compra no está en la lista,
        # no se toma otra: sería otra posición.
        return None
    limite = _fecha_de_senal(confirmacion)
    candidatas = [c for c in compras if id(c) not in usadas and _fecha_de_senal(c) <= limite]
    if not candidatas:
        return None
    return max(candidatas, key=_fecha_de_senal)


def _fusionar(origen: dict, confirmacion: dict) -> dict:
    """La confirmación no abre otra posición: sube la etiqueta y deja la entrada original."""
    if origen.get("estado_posicion") == "cerrada" and confirmacion.get("estado_posicion") == "cerrada":
        return _fusionar_venta(origen, confirmacion)
    if origen.get("precio_entrada") is not None and origen.get("estado_posicion") != "pendiente":
        fila = dict(origen)
    elif confirmacion.get("precio_entrada") is not None and confirmacion.get("estado_posicion") != "pendiente":
        fila = dict(confirmacion)
    else:
        fila = dict(origen)
    fila["senal"] = "Compra fuerte"
    fila["fuerza"] = "fuerte"
    fila["fecha"] = origen.get("fecha") or fila.get("fecha")
    fila["fecha_compra"] = _fecha_de_senal(origen)
    fila["fecha_confirmacion"] = _fecha_de_senal(confirmacion)
    fila["detalle"] = _detalle_confirmada(fila)
    return fila


def _fusionar_venta(origen: dict, confirmacion: dict) -> dict:
    """Una sola salida: la de la compra original. La confirmación no suma otra venta."""
    fila = dict(origen)
    fila["senal"] = "Venta"
    fila["fuerza"] = None
    fila["fecha_compra"] = origen.get("fecha_senal") or origen.get("fecha")
    fila["fecha_confirmacion"] = confirmacion.get("fecha_senal") or _fecha_de_senal(confirmacion)
    motivo = MOTIVOS_SALIDA.get(fila.get("motivo"), "")
    fila["detalle"] = (
        f"Salió el {fila['fecha']}. {motivo} "
        f"La compra fue el {fila['fecha_compra']} y se confirmó el {fila['fecha_confirmacion']}. "
        "Es la misma posición teórica. "
        "No es una instrucción de vender lo que tengas: es la salida de la posición teórica."
    )
    return fila


def _prioridad_vigente(fila: dict) -> tuple:
    """Fuerte le gana a débil. Si empatan, la que ya tiene entrada y, después, la más reciente."""
    rango = {"fuerte": 2, "debil": 1}.get(fila.get("fuerza") or "", 0)
    con_entrada = 0 if fila.get("estado_posicion") == "pendiente" or fila.get("precio_entrada") is None else 1
    momento = max(str(fila.get("fecha") or ""), str(fila.get("fecha_confirmacion") or ""))
    return (rango, con_entrada, momento)


def _unir_cadenas(filas: list[dict]) -> list[dict]:
    compras = [fila for fila in filas if not _es_confirmacion(fila)]
    confirmaciones = [fila for fila in filas if _es_confirmacion(fila)]
    usadas: set[int] = set()
    consumidas: set[int] = set()
    unidas: list[dict] = []
    for confirmacion in confirmaciones:
        origen = _buscar_origen(confirmacion, compras, usadas)
        if origen is None:
            continue
        usadas.add(id(origen))
        consumidas.add(id(confirmacion))
        unidas.append(_fusionar(origen, confirmacion))
    for fila in filas:
        if id(fila) in usadas or id(fila) in consumidas:
            continue
        unidas.append(fila)
    return unidas


def consolidar_filas(filas: list[dict]) -> list[dict]:
    """Como máximo una fila vigente por ticker."""
    if len(filas) <= 1:
        return list(filas)
    grupos: dict[str, list[dict]] = {}
    orden: list[str] = []
    for fila in filas:
        ticker = str(fila.get("ticker") or "")
        if ticker not in grupos:
            orden.append(ticker)
            grupos[ticker] = []
        grupos[ticker].append(fila)
    salida: list[dict] = []
    for ticker in orden:
        grupo = grupos[ticker]
        if len(grupo) == 1:
            salida.extend(grupo)
            continue
        unidas = _unir_cadenas(grupo)
        if len(unidas) <= 1:
            salida.extend(unidas)
            continue
        salida.append(max(unidas, key=_prioridad_vigente))
    return salida


def aplicar_semaforo(filas: list[dict], lecturas: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Si el contraste está en rojo, esa señal no se emite."""
    emitidas = []
    bloqueadas = []
    for fila in filas:
        lectura = lecturas.get(fila["ticker"]) or {}
        if lectura.get("bloquea_senal") or lectura.get("estado") == ROJO:
            bloqueadas.append({**fila, "motivo_bloqueo": lectura.get("motivo") or "Contraste en rojo."})
        else:
            emitidas.append(fila)
    return emitidas, bloqueadas


def resumen_costos(series: dict[str, pd.DataFrame], cfg: dict) -> list[dict]:
    """Media por operación, neta de un costo supuesto por vuelta. Sin impuestos."""
    anos = int(str(cfg.get("period", "2y")).rstrip("y") or 2)
    filas = []
    for tipo, nombre in (("compra", "Compra débil"), ("confirmacion", "Compra fuerte")):
        for costo_nombre, costo in (
            ("Bruto", 0.0),
            ("0,6% por vuelta", float(cfg["cost_base"])),
            ("1,2% por vuelta", float(cfg["cost_conservative"])),
        ):
            trades = []
            for ticker, df in series.items():
                serie = preparar_serie(df)
                if serie.empty:
                    continue
                corte = pd.Timestamp(serie.index[-1]) - pd.DateOffset(years=anos)
                eventos = [e for e in detectar_senales(serie, cfg, ticker) if e["tipo"] == tipo and pd.Timestamp(e["fecha"]) >= corte]
                trades.extend(_trades_de(serie, eventos, cfg, cost=costo, include_open=False))
            stats = resumir(trades)
            filas.append({"entrada": nombre, "costo": costo_nombre, **stats})
    return filas
