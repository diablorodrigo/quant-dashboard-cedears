"""Rotación de sectores e índices contra SPY.

Cuenta propia: no usa código de terceros. La fuerza es el precio del ETF
dividido por SPY, suavizado y llevado a 100 en su promedio de unos seis meses.
El momentum compara esa fuerza con la de diez ruedas atrás, también en 100.
La cola del gráfico son las últimas cinco semanas, con una marca por semana.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEMANA = 5
MES = 21
TRIMESTRE = 63
# Cinco semanas de ruedas, muestreadas una vez por semana (4 a 6 marcas).
COLA_RUEDAS = 25
PASO_COLA = 5
VENTANA_BASE = 126
SUAVIZADO = 10
CRUCE = 100.0

# Nombre en español y CEDEARs del panel que pertenecen a ese sector.
# No es la cartera completa del ETF: es el recorte que este tablero sigue.
SECTORES: dict[str, dict] = {
    "XLK": {
        "nombre": "Tecnología",
        "cedears": [
            "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "ACN",
            "AMD", "INTC", "QCOM", "TXN", "MU", "LRCX", "ADI", "PANW",
            "CRWD", "PLTR", "DELL", "HPQ", "ARM", "ASML", "TSM", "MRVL", "SNDK",
            "TWLO", "SPCX", "RGTI",
        ],
    },
    "XLF": {
        "nombre": "Finanzas",
        "cedears": [
            "JPM", "BAC", "GS", "MS", "BNY", "AXP", "V", "MA", "BRK-B", "PYPL",
            "COIN", "NU", "BBD", "ITUB", "PAGS",
        ],
    },
    "XLE": {
        "nombre": "Energía",
        "cedears": ["XOM", "CVX", "OXY", "HAL", "BKR", "PSX", "EQNR", "PBR", "VIST", "YPF", "GPRK"],
    },
    "XLV": {
        "nombre": "Salud",
        "cedears": ["LLY", "UNH", "JNJ", "ABBV", "AMGN", "PFE", "BMY", "MRNA", "CVS", "HIMS"],
    },
    "XLY": {
        "nombre": "Consumo discrecional",
        "cedears": ["AMZN", "TSLA", "HD", "MCD", "SBUX", "F", "GM", "STLA", "TM", "UBER", "RACE", "EBAY", "ARCO"],
    },
    "XLP": {
        "nombre": "Consumo básico",
        "cedears": ["WMT", "COST", "PG", "KO", "PEP", "MDLZ", "CL", "HSY", "UL", "SYY", "BG"],
    },
    "XLI": {
        "nombre": "Industria",
        "cedears": ["CAT", "DE", "HON", "MMM", "BA", "LMT", "GEV", "AAL", "UAL", "EMBJ"],
    },
    "XLB": {
        "nombre": "Materiales",
        "cedears": ["VALE", "GGB"],
    },
    "XLU": {
        "nombre": "Servicios públicos",
        "cedears": ["CEG"],
    },
    "XLRE": {
        "nombre": "Inmuebles",
        "cedears": ["O"],
    },
    "XLC": {
        "nombre": "Comunicaciones",
        "cedears": ["GOOGL", "META", "NFLX", "SPOT"],
    },
}

INDICES: dict[str, str] = {
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "EEM": "Emergentes",
    "EWZ": "Brasil",
    "ARGT": "Argentina",
}

PALETA = {
    "XLK": "#1e3a34",
    "XLF": "#1d6a8a",
    "XLE": "#8d6b4a",
    "XLV": "#2f6f4e",
    "XLY": "#b07a30",
    "XLP": "#5c7a72",
    "XLI": "#3e5568",
    "XLB": "#a33b32",
    "XLU": "#6e7f8d",
    "XLRE": "#7a5c8a",
    "XLC": "#1f7a4d",
}


def simbolos_extra() -> list[str]:
    """Símbolos que no están en el universo de CEDEARs y hacen falta acá."""
    return ["XLRE", "ARGT"]


def cuadrante(fuerza: float, momentum: float) -> str:
    if fuerza >= CRUCE and momentum >= CRUCE:
        return "Líder"
    if fuerza >= CRUCE and momentum < CRUCE:
        return "Debilitándose"
    if fuerza < CRUCE and momentum >= CRUCE:
        return "Mejorando"
    return "Rezagado"


def _alinear(precio: pd.Series, spy: pd.Series) -> tuple[pd.Series, pd.Series]:
    tabla = pd.concat({"p": precio, "s": spy}, axis=1).dropna()
    return tabla["p"].astype(float), tabla["s"].astype(float)


def curvas_rrg(precio: pd.Series, spy: pd.Series) -> pd.DataFrame:
    activo, benchmark = _alinear(precio, spy)
    if len(activo) < VENTANA_BASE:
        return pd.DataFrame()
    relativo = activo / benchmark.replace(0, np.nan)
    suave = relativo.ewm(span=SUAVIZADO, adjust=False).mean()
    base = suave.rolling(VENTANA_BASE, min_periods=60).mean()
    fuerza = 100.0 * suave / base.replace(0, np.nan)
    momentum = 100.0 * fuerza / fuerza.shift(SUAVIZADO).replace(0, np.nan)
    salida = pd.DataFrame({"fuerza": fuerza, "momentum": momentum}).replace([np.inf, -np.inf], np.nan).dropna()
    return salida


def cola_reciente(curva: pd.DataFrame) -> pd.DataFrame:
    """Últimas cinco semanas, una observación por semana, siempre con el cierre de hoy."""
    if curva.empty:
        return curva
    recorte = curva.tail(COLA_RUEDAS)
    posiciones = list(range(0, len(recorte), PASO_COLA))
    if not posiciones or posiciones[-1] != len(recorte) - 1:
        posiciones.append(len(recorte) - 1)
    return recorte.iloc[posiciones]


def _exceso(activo: pd.Series, spy: pd.Series, desde: int, hasta: int) -> float | None:
    if len(activo) < abs(desde) + 1:
        return None
    pa0, pa1 = float(activo.iloc[desde]), float(activo.iloc[hasta])
    ps0, ps1 = float(spy.iloc[desde]), float(spy.iloc[hasta])
    if min(pa0, pa1, ps0, ps1) <= 0:
        return None
    return (pa1 / pa0) - (ps1 / ps0)


def _flecha(reciente: float | None, anterior: float | None) -> str:
    if reciente is None or anterior is None:
        return "→"
    if reciente > anterior + 0.0015:
        return "▲"
    if reciente < anterior - 0.0015:
        return "▼"
    return "→"


def _bloque(activo: pd.Series, spy: pd.Series, sesiones: int) -> tuple[float | None, str]:
    reciente = _exceso(activo, spy, -sesiones - 1, -1)
    anterior = _exceso(activo, spy, -(2 * sesiones) - 1, -sesiones - 1)
    return reciente, _flecha(reciente, anterior)


def _fila_ranking(ticker: str, nombre: str, grupo: str, precio: pd.Series, spy: pd.Series, curva: pd.DataFrame) -> dict | None:
    if curva.empty:
        return None
    ultimo = curva.iloc[-1]
    fuerza = float(ultimo["fuerza"])
    momentum = float(ultimo["momentum"])
    s1, f1 = _bloque(precio, spy, SEMANA)
    s2, f2 = _bloque(precio, spy, MES)
    s3, f3 = _bloque(precio, spy, TRIMESTRE)
    return {
        "Ticker": ticker,
        "Nombre": nombre,
        "Grupo": grupo,
        "Fuerza": round(fuerza, 1),
        "Momentum": round(momentum, 1),
        "Cuadrante": cuadrante(fuerza, momentum),
        "ex_1s": s1,
        "flecha_1s": f1,
        "ex_1m": s2,
        "flecha_1m": f2,
        "ex_3m": s3,
        "flecha_3m": f3,
        "Ritmo": f1,
    }


def frase_rotacion(sectores: pd.DataFrame) -> str:
    """Una oración, en castellano llano, sobre qué sectores entran y salen."""
    if sectores is None or sectores.empty:
        return "No hay datos suficientes para leer la rotación entre sectores."

    def _nombres(mask: pd.Series) -> list[str]:
        return sectores.loc[mask, "Nombre"].tolist()

    entran = _nombres(sectores["Cuadrante"].isin(["Líder", "Mejorando"]) & (sectores["Ritmo"] == "▲"))
    salen = _nombres(sectores["Cuadrante"].isin(["Debilitándose", "Rezagado"]) & (sectores["Ritmo"] == "▼"))
    if not entran:
        entran = _nombres(sectores["Cuadrante"] == "Mejorando")
    if not salen:
        salen = _nombres(sectores["Cuadrante"] == "Debilitándose")

    def _lista(nombres: list[str]) -> str:
        if not nombres:
            return "ningún sector con un giro claro"
        if len(nombres) == 1:
            return nombres[0]
        return ", ".join(nombres[:-1]) + " y " + nombres[-1]

    return f"Está rotando a favor de {_lista(entran)}; está saliendo de {_lista(salen)}."


def armar_rotacion(cierres: pd.DataFrame) -> dict:
    """Arma colas, ranking y la frase. `cierres` son precios de cierre por símbolo."""
    vacio = {"colas": pd.DataFrame(), "ranking": pd.DataFrame(), "frase": frase_rotacion(pd.DataFrame()), "sin_datos": []}
    if cierres is None or cierres.empty or "SPY" not in cierres.columns:
        return vacio

    spy = cierres["SPY"].dropna()
    colas = []
    filas = []
    sin_datos = []

    series = [(t, d["nombre"], "Sector") for t, d in SECTORES.items()]
    series += [(t, nombre, "Índice") for t, nombre in INDICES.items()]

    for ticker, nombre, grupo in series:
        if ticker not in cierres.columns:
            sin_datos.append(ticker)
            continue
        precio, benchmark = _alinear(cierres[ticker], spy)
        curva = curvas_rrg(precio, benchmark)
        fila = _fila_ranking(ticker, nombre, grupo, precio, benchmark, curva)
        if fila is None:
            sin_datos.append(ticker)
            continue
        filas.append(fila)
        if grupo != "Sector":
            continue
        nodos = cola_reciente(curva)
        for orden, (fecha, nodo) in enumerate(nodos.iterrows()):
            colas.append(
                {
                    "Ticker": ticker,
                    "Nombre": nombre,
                    "Fecha": fecha,
                    "Fuerza": float(nodo["fuerza"]),
                    "Momentum": float(nodo["momentum"]),
                    "Orden": orden,
                    "Ultimo": orden == len(nodos) - 1,
                }
            )

    ranking = pd.DataFrame(filas)
    sectores = ranking[ranking["Grupo"] == "Sector"] if not ranking.empty else ranking
    return {
        "colas": pd.DataFrame(colas),
        "ranking": ranking,
        "frase": frase_rotacion(sectores),
        "sin_datos": sin_datos,
    }


def texto_periodo(valor: float | None, flecha: str) -> str:
    if valor is None or not np.isfinite(valor):
        return "—"
    return f"{valor * 100:+.1f}% {flecha}"


def cedears_visibles(ticker_sector: str, presentes: set[str]) -> list[str]:
    pedidos = SECTORES.get(ticker_sector, {}).get("cedears", [])
    return [t for t in pedidos if t in presentes]
