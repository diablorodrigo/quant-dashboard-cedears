"""Panel Zeta v2 (22/10/2026): termómetro, mapa de calor, tablero Argentina, balances y filtros rápidos.

Solo fuentes gratuitas: Yahoo Finance (yfinance), dolarapi.com, argentinadatos.com y data912.com.
Si una fuente no responde se muestra "Sin dato": nunca se completa con valores inventados.
"""

from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import yfinance as yf

from zeta.senales import fechas_de_balance
from zeta.tiempo import ahora_art
from zeta.universo import WATCHLIST

SIN_DATO = "Sin dato"
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _hoy() -> date:
    return ahora_art().date()


def _sello(fuente: str) -> str:
    return f"Fuente: {fuente}. Consulta al {ahora_art():%d/%m/%Y %H:%M} (hora Argentina). Información educativa, no es recomendación."


def _num(valor, dec: int = 2, pre: str = "", suf: str = "") -> str:
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return SIN_DATO
    texto = f"{float(valor):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{pre}{texto}{suf}"


def _json(url: str):
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "PanelZeta/2.0"})
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Marcas por activo (las usan el termómetro y los filtros rápidos del monitor)
# ---------------------------------------------------------------------------
def marcas_tecnicas(panel: dict) -> pd.DataFrame:
    """Por ticker: sobre EMA 200, sobre SMA 50, cerca de máximo/mínimo de 52 semanas (±2%)."""
    filas = []
    for clave, hist in panel["historicos"].items():
        close = hist["Close"].astype(float).dropna()
        if len(close) < 210:
            continue
        precio = float(close.iloc[-1])
        ult = close.iloc[-252:]
        filas.append(
            {
                "ticker": clave,
                "sobre_ema200": precio > float(close.ewm(span=200, adjust=False).mean().iloc[-1]),
                "sobre_sma50": precio > float(close.rolling(50).mean().iloc[-1]),
                "cerca_max": precio >= float(ult.max()) * 0.98,
                "cerca_min": precio <= float(ult.min()) * 1.02,
            }
        )
    return pd.DataFrame(filas, columns=["ticker", "sobre_ema200", "sobre_sma50", "cerca_max", "cerca_min"])


# ---------------------------------------------------------------------------
# Calendario de balances (una consulta por subyacente, en paralelo y cacheada 6 h)
# ---------------------------------------------------------------------------
def _proximo_balance(simbolo: str) -> date | None:
    try:
        fechas = fechas_de_balance(yf.Ticker(simbolo).calendar)
    except Exception:
        return None
    hoy = _hoy()
    futuras = [f for f in fechas if (f - hoy).days >= -1]
    return min(futuras) if futuras else None


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def fechas_balance() -> dict[str, date]:
    claves = list(WATCHLIST)
    with ThreadPoolExecutor(8) as ex:
        fechas = list(ex.map(lambda k: _proximo_balance(WATCHLIST[k]["underlying"]), claves))
    return {k: f for k, f in zip(claves, fechas) if f is not None}


# ---------------------------------------------------------------------------
# Filtros rápidos del monitor
# ---------------------------------------------------------------------------
FILTROS = {
    "Cerca de máximos 52s": "cerca_max",
    "Cerca de mínimos 52s": "cerca_min",
    "Sobre EMA 200": "sobre_ema200",
    "Debajo de EMA 200": "debajo_ema200",
    "Volumen inusual (+50%)": "vol_inusual",
    "Balance esta semana": "balance_semana",
}


def filtros_rapidos(panel: dict, df: pd.DataFrame) -> pd.DataFrame:
    marcas = marcas_tecnicas(panel).set_index("ticker")
    balances = fechas_balance()
    hoy = _hoy()
    base = pd.DataFrame(index=df["ticker"])
    base["cerca_max"] = marcas["cerca_max"].reindex(base.index).fillna(False).astype(bool)
    base["cerca_min"] = marcas["cerca_min"].reindex(base.index).fillna(False).astype(bool)
    sobre = marcas["sobre_ema200"].reindex(base.index)
    base["sobre_ema200"] = sobre.fillna(False).astype(bool)
    base["debajo_ema200"] = sobre.notna() & ~sobre.fillna(True).astype(bool)
    base["vol_inusual"] = (df.set_index("ticker")["vol_relativo"] >= 150).reindex(base.index).fillna(False)
    base["balance_semana"] = [k in balances and 0 <= (balances[k] - hoy).days <= 7 for k in base.index]

    st.markdown("**⚡ Filtros rápidos**")
    columnas = st.columns(3) + st.columns(3)
    activos = []
    for col, (titulo, campo) in zip(columnas, FILTROS.items()):
        if col.toggle(f"{titulo} ({int(base[campo].sum())})", key=f"filtro_{campo}"):
            activos.append(campo)
    if not activos:
        return df
    mask = base[activos].all(axis=1)
    return df[df["ticker"].map(mask).fillna(False).astype(bool)]


# ---------------------------------------------------------------------------
# Página "Mercado": termómetro + mapa de calor
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60 * 15, show_spinner=False)
def _vix() -> tuple[float | None, float | None]:
    try:
        h = yf.Ticker("^VIX").history(period="1mo")
        if h.empty:
            return None, None
        return float(h["Close"].iloc[-1]), (float(h["Close"].iloc[-6]) if len(h) > 6 else None)
    except Exception:
        return None, None


def _estado(pct200: float | None, pct50: float | None, vix: float | None) -> tuple[str, str, str]:
    if pct200 is None:
        return "❔", "Sin datos suficientes para el termómetro", "#7f8c8d"
    puntos = (1 if pct200 >= 60 else -1 if pct200 < 40 else 0) + (1 if pct50 >= 60 else -1 if pct50 < 40 else 0)
    if vix is not None:
        puntos += 1 if vix < 18 else -1 if vix > 25 else 0
    if puntos >= 2:
        return "☀️", "Soleado: la mayoría de los activos acompaña la tendencia", "#27ae60"
    if puntos <= -2:
        return "⛈️", "Tormenta: predominan activos debajo de sus medias y la volatilidad es alta", "#c0392b"
    return "⛅", "Nublado: mercado mixto, conviene cuidar lo ganado y no apurarse", "#e67e22"


def bloque_termometro(panel: dict) -> None:
    st.markdown("### 🌡️ Termómetro del mercado")
    m = marcas_tecnicas(panel)
    n = len(m)
    pct200 = 100 * m["sobre_ema200"].mean() if n else None
    pct50 = 100 * m["sobre_sma50"].mean() if n else None
    vix, vix_prev = _vix()
    icono, texto, color = _estado(pct200, pct50, vix)
    st.markdown(
        f"<div style='border-left:6px solid {color};padding:10px 14px;border-radius:6px;"
        f"background:rgba(127,140,141,0.10);'><span style='font-size:1.8em;'>{icono}</span> "
        f"<b style='color:{color};font-size:1.1em;'>{html.escape(texto)}</b></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sobre EMA 200", _num(pct200, 0, suf="%"), help="% del universo cuyo subyacente cotiza sobre su EMA de 200 ruedas.")
    c2.metric("Sobre SMA 50", _num(pct50, 0, suf="%"), help="% del universo sobre su media de 50 ruedas.")
    c3.metric("Cerca de máximos 52s", str(int(m["cerca_max"].sum())) if n else SIN_DATO, help="A menos de 2% del máximo de 52 semanas.")
    c4.metric("Cerca de mínimos 52s", str(int(m["cerca_min"].sum())) if n else SIN_DATO, help="A menos de 2% del mínimo de 52 semanas.")
    delta = f"{vix - vix_prev:+.2f} vs hace 5 ruedas".replace(".", ",") if (vix and vix_prev) else None
    c5.metric("VIX (volatilidad EE.UU.)", _num(vix), delta, delta_color="inverse")
    st.caption(f"Base: {n} activos con 210 ruedas o más, precios del subyacente en USD + ^VIX. " + _sello("Yahoo Finance vía yfinance"))


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _capitalizaciones() -> dict[str, float]:
    def una(clave):
        try:
            return clave, float(yf.Ticker(WATCHLIST[clave]["underlying"]).fast_info["market_cap"])
        except Exception:
            return clave, None
    with ThreadPoolExecutor(8) as ex:
        return {k: v for k, v in ex.map(una, list(WATCHLIST)) if v}


def bloque_mapa_calor(panel: dict, cerrar_grafico) -> None:
    st.markdown("### 🗺️ Mapa de calor por rubro")
    plazo = st.radio("Variación:", ["1 día", "1 semana", "1 mes"], horizontal=True, key="plazo_mapa")
    ruedas = {"1 día": 1, "1 semana": 5, "1 mes": 21}[plazo]
    caps = _capitalizaciones()
    filas = []
    for fila in panel["filas"].itertuples(index=False):
        hist = panel["historicos"].get(fila.ticker)
        if hist is None or len(hist) <= ruedas:
            continue
        close = hist["Close"].astype(float)
        filas.append(
            {
                "Rubro": fila.rubro,
                "Ticker": fila.ticker,
                "Empresa": fila.nombre,
                "Var": round(100 * (float(close.iloc[-1]) / float(close.iloc[-1 - ruedas]) - 1), 2),
                "Cap": caps.get(fila.ticker),
            }
        )
    if not filas:
        st.info("Sin dato para armar el mapa en este momento.")
        return
    df = pd.DataFrame(filas)
    usa_cap = df["Cap"].notna().mean() > 0.8
    # Raíz de la capitalización: evita que tres gigantes tapen el mapa.
    df["Tamaño"] = (df["Cap"].fillna(df["Cap"].median()) ** 0.5) if usa_cap else 1.0
    limite = 3.0 if ruedas == 1 else max(3.0, float(df["Var"].abs().quantile(0.9)))
    fig = px.treemap(
        df, path=[px.Constant("Panel Zeta"), "Rubro", "Ticker"], values="Tamaño", color="Var",
        color_continuous_scale=["#c0392b", "#7f8c8d", "#27ae60"], range_color=[-limite, limite],
        custom_data=["Empresa", "Var"],
    )
    traza = fig.data[0]
    datos = [list(x) for x in traza.customdata]
    for i, x in enumerate(datos):
        if str(x[0]) == "(?)":  # recuadros de rubro: muestran el promedio ponderado, no "(?)"
            x[0] = "Promedio ponderado del grupo"
            x[1] = float(traza.marker.colors[i])
    traza.customdata = datos
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]:+.2f}%",
        hovertemplate="<b>%{label}</b> %{customdata[0]}<br>Variación: %{customdata[1]:+.2f}%<extra></extra>",
    )
    fig = cerrar_grafico(fig)
    fig.update_layout(height=620, margin=dict(t=30, b=10, l=10, r=10), coloraxis_colorbar=dict(title="Var %"))
    st.plotly_chart(fig, width="stretch", key=f"mapa_{ruedas}")
    st.caption(
        f"Color: variación % del subyacente en USD ({plazo}). Tamaño: "
        f"{'raíz de la capitalización de mercado' if usa_cap else 'igual para todos'}. " + _sello("Yahoo Finance vía yfinance")
    )


def vista_mercado() -> None:
    from zeta.vistas import _cerrar_grafico, panel_o_aviso

    panel = panel_o_aviso()
    if panel is None:
        return
    bloque_termometro(panel)
    st.divider()
    bloque_mapa_calor(panel, _cerrar_grafico)


# ---------------------------------------------------------------------------
# Página "Argentina"
# ---------------------------------------------------------------------------
ADRS = ["GGAL", "YPF", "BMA", "PAM", "VIST", "TGS", "CEPU", "BBAR", "SUPV", "LOMA", "IRS", "TEO", "EDN", "CRESY"]
BONOS = ["AL29D", "AL30D", "AL35D", "AE38D", "AL41D", "GD29D", "GD30D", "GD35D", "GD38D", "GD41D", "GD46D"]


@st.cache_data(ttl=600, show_spinner=False)
def _dolares():
    return _json("https://dolarapi.com/v1/dolares")


@st.cache_data(ttl=3600, show_spinner=False)
def _riesgo_pais():
    return _json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo")


@st.cache_data(ttl=600, show_spinner=False)
def _bonos():
    return _json("https://data912.com/live/arg_bonds")


@st.cache_data(ttl=900, show_spinner=False)
def _merval_y_adrs() -> dict[str, tuple[float, float]]:
    salida = {}
    try:
        data = yf.download(["^MERV", *ADRS], period="10d", group_by="ticker", progress=False, threads=True, auto_adjust=True)
        for t in ["^MERV", *ADRS]:
            try:
                c = data[t]["Close"].dropna()
                if len(c) >= 2:
                    salida[t] = (float(c.iloc[-1]), 100 * (float(c.iloc[-1]) / float(c.iloc[-2]) - 1))
            except Exception:
                pass
    except Exception:
        pass
    return salida


def vista_argentina() -> None:
    from zeta.vistas import mostrar_tabla

    st.markdown("### 🇦🇷 Tablero Argentina")
    dol = _dolares()
    casas = {x.get("casa"): x for x in dol} if isinstance(dol, list) else {}
    oficial = casas.get("oficial", {}).get("venta")
    st.markdown("**💵 Dólares (venta) y brecha contra el oficial**")
    for col, (casa, nombre) in zip(
        st.columns(5), [("oficial", "Oficial"), ("bolsa", "MEP"), ("contadoconliqui", "CCL"), ("blue", "Blue"), ("tarjeta", "Tarjeta")]
    ):
        v = casas.get(casa, {}).get("venta")
        brecha = f"Brecha {_num(100 * (v / oficial - 1), 1, suf='%')}" if (v and oficial and casa != "oficial") else None
        col.metric(nombre, _num(v, 2, pre="$"), brecha, delta_color="off")

    rp = _riesgo_pais()
    mv = _merval_y_adrs()
    c1, c2 = st.columns(2)
    if isinstance(rp, dict) and rp.get("valor") is not None:
        fecha = pd.Timestamp(rp["fecha"]).strftime("%d/%m/%Y") if rp.get("fecha") else ""
        c1.metric("Riesgo país (puntos básicos)", _num(rp["valor"], 0), f"Dato del {fecha}", delta_color="off")
    else:
        c1.metric("Riesgo país", SIN_DATO)
    if "^MERV" in mv:
        c2.metric("S&P Merval (ARS)", _num(mv["^MERV"][0], 0), _num(mv["^MERV"][1], 2, suf="%"))
    else:
        c2.metric("S&P Merval", SIN_DATO)

    a, b = st.columns(2)
    with a:
        st.markdown("**🏦 ADRs argentinos en Nueva York (USD)**")
        filas = sorted(((t, *mv[t]) for t in ADRS if t in mv), key=lambda x: -x[2])
        if filas:
            mostrar_tabla(pd.DataFrame([{"Ticker": t, "Precio USD": _num(p, 2, pre="US$"), "Var. 1D": f"{v:+.2f}%"} for t, p, v in filas]), alto=420)
        else:
            st.info("Sin dato de ADRs en este momento (Yahoo Finance no respondió).")
    with b:
        st.markdown("**📜 Bonos soberanos en dólares (MEP, cada 100 VN)**")
        bonos = _bonos()
        mapa = {x["symbol"]: x for x in bonos if isinstance(x, dict) and "symbol" in x} if isinstance(bonos, list) else {}
        filas = [
            {"Bono": s[:-1], "Ley": "NY" if s.startswith("GD") else "AR", "Precio USD": _num(mapa[s].get("c"), 2, pre="US$"),
             "Var. 1D": _num(mapa[s].get("pct_change"), 2, suf="%")}
            for s in BONOS if s in mapa
        ]
        if filas:
            mostrar_tabla(pd.DataFrame(filas), alto=420)
        else:
            st.info("Sin dato de bonos en este momento (data912 no respondió).")
        st.caption("TIR: próximamente (requiere cargar el flujo de fondos de cada bono).")
    st.caption(_sello("dolarapi.com (dólares), argentinadatos.com (riesgo país), Yahoo Finance (Merval y ADRs), data912.com (bonos)"))


# ---------------------------------------------------------------------------
# Página "Balances"
# ---------------------------------------------------------------------------
def vista_balances() -> None:
    from zeta.vistas import mostrar_tabla

    st.markdown("### 🗓️ Calendario de balances")
    with st.spinner("Buscando fechas de presentación de balances…"):
        cal = fechas_balance()
    if not cal:
        st.info("Sin dato: Yahoo Finance no devolvió fechas de balances en este momento. Probá más tarde.")
        return
    hoy = _hoy()
    filas = []
    for clave, f in sorted(cal.items(), key=lambda x: x[1]):
        dias = (f - hoy).days
        if dias > 21:
            continue
        cuando = "Hoy" if dias == 0 else "Mañana" if dias == 1 else "Ayer" if dias < 0 else f"En {dias} días"
        filas.append({"Fecha": f"{f:%d/%m}", "Día": DIAS_SEMANA[f.weekday()], "Ticker": clave,
                      "Empresa": WATCHLIST[clave]["name"], "Cuándo": cuando, "Esta semana": "📌 Sí" if dias <= 7 else ""})
    c1, c2 = st.columns([1, 3])
    c1.metric("Reportan en los próximos 7 días", sum(1 for f in cal.values() if -1 <= (f - hoy).days <= 7))
    c1.caption("Antes de un balance la volatilidad suele subir. En el Monitor podés filtrar «Balance esta semana».")
    with c2:
        if filas:
            mostrar_tabla(pd.DataFrame(filas), alto=520)
        else:
            st.info("Ninguna empresa del panel presenta balance en las próximas 3 semanas.")
    st.caption("Fechas estimadas o confirmadas por cada empresa; pueden cambiar. " + _sello("Yahoo Finance vía yfinance"))
