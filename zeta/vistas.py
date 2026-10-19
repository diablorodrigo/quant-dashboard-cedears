"""Páginas del panel."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from zeta.carteras import PERFILES, composicion, metricas_historicas, pesos_variable
from zeta.datos import cargar_panel, ficha_activo
from zeta.indicadores import bollinger, ema, macd, rsi, sma
from zeta.marca import LOGO, LOGO_HEADER, SITIO, WHATSAPP, aviso, linea_identidad
from zeta.rotacion import INDICES, PALETA, SECTORES, armar_rotacion, cedears_visibles, texto_periodo
from zeta.rrg import calcular_rrg
from zeta.senales import (
    ALCISTA_CON_VOLUMEN,
    ALCISTA_SIN_VOLUMEN,
    EN_OBSERVACION_RIESGO,
    SESGO_ALCISTA,
    SESGO_ALCISTA_MARCADO,
)
from zeta.tiempo import ahora_art, clave_cierre, texto_actualizacion
from zeta.universo import WATCHLIST

COLORES_CUADRANTE = {
    "Líderes": "#1f7a4d",
    "Mejorando": "#1d6a8a",
    "Debilitándose": "#b07a30",
    "Rezagados": "#a33b32",
}
COLORES_TORTA = ["#1e3a34", "#2f6f4e", "#5c9478", "#8fb5a1", "#d4c4a8", "#8d6b4a", "#3e5568", "#6e7f8d"]
TRADUCCION_CONSENSO = {
    "strong_buy": "Muy positivo",
    "buy": "Positivo",
    "hold": "Neutro",
    "underperform": "Cauto",
    "sell": "Cauto",
    "strong_sell": "Muy cauto",
}


def _plantilla() -> str:
    return "plotly_dark" if st.session_state.get("tema") == "Oscuro" else "plotly_white"


def _finito(valor) -> bool:
    return isinstance(valor, (int, float, np.floating)) and np.isfinite(valor)


def _pct(valor: float | None, decimales: int = 2) -> str:
    if not _finito(valor):
        return "—"
    return f"{valor * 100:.{decimales}f}%"


def _num(valor, decimales: int = 2, sufijo: str = "") -> str:
    if not _finito(valor):
        return "—"
    return f"{float(valor):,.{decimales}f}{sufijo}"


def panel_o_aviso() -> dict | None:
    try:
        with st.spinner("Descargando cotizaciones de Yahoo Finance…"):
            return cargar_panel(clave_cierre())
    except Exception:
        logging.exception("No se pudo armar el panel")
        st.error(
            "Yahoo Finance no respondió con datos suficientes. "
            "Esperá un minuto y recargá la página. No se muestra una lectura a medias."
        )
        return None


def barra_lateral() -> None:
    if LOGO.exists():
        st.sidebar.image(str(LOGO), width=78)
    st.sidebar.markdown("**Zeta Finance**")
    st.sidebar.caption(linea_identidad())
    st.sidebar.radio("Apariencia", ["Claro", "Oscuro"], key="tema")
    st.sidebar.link_button("zetafinance.com.ar", SITIO, width="stretch")
    st.sidebar.link_button("WhatsApp", WHATSAPP, width="stretch")

    def _salir():
        st.session_state["autenticado"] = False

    st.sidebar.button("Cerrar sesión", on_click=_salir, width="stretch")


def encabezado() -> None:
    import base64

    logo_html = ""
    origen = LOGO_HEADER if LOGO_HEADER.exists() else LOGO
    if origen.exists():
        encoded = base64.b64encode(origen.read_bytes()).decode("ascii")
        logo_html = (
            f'<img alt="Zeta Finance" src="data:image/png;base64,{encoded}" '
            'style="height:62px;width:62px;object-fit:contain;display:block;" />'
        )
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:14px;margin:0 0 0.2rem;">
          {logo_html}
          <div>
            <div style="font-size:1.65rem;font-weight:700;line-height:1.15;letter-spacing:-0.02em;">
              Zeta Finance · Panel de análisis
            </div>
            <p class="zeta-sub" style="margin:0.15rem 0 0;">CEDEARs · {texto_actualizacion()}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    aviso()


def pie() -> None:
    st.divider()
    aviso()


def _estilo_lectura(valor: str) -> str:
    if not isinstance(valor, str):
        return ""
    texto = valor.lower()
    if "observación" in texto or "distribución" in texto or "sin volumen" in texto:
        return "background-color: rgba(176,122,48,0.22); font-weight: 650;"
    if "marcado" in texto and "alcista" in texto or "con volumen" in texto:
        return "background-color: rgba(31,122,77,0.30); font-weight: 700;"
    if "alcista" in texto:
        return "background-color: rgba(31,122,77,0.16); font-weight: 650;"
    if "marcado" in texto and "bajista" in texto:
        return "background-color: rgba(163,59,50,0.28); font-weight: 700;"
    if "bajista" in texto:
        return "background-color: rgba(163,59,50,0.14); font-weight: 650;"
    return ""


def _estilo_variacion(valor: str) -> str:
    if not isinstance(valor, str) or "%" not in valor:
        return ""
    try:
        numero = float(valor.replace("%", "").replace("+", ""))
    except ValueError:
        return ""
    if numero > 0:
        return "color: #1f7a4d; font-weight: 650;"
    if numero < 0:
        return "color: #a33b32; font-weight: 650;"
    return ""


def _estilo_volumen(valor: str) -> str:
    if not isinstance(valor, str) or "%" not in valor:
        return ""
    try:
        numero = float(valor.replace("%", ""))
    except ValueError:
        return ""
    if numero > 120:
        return "color: #1d6a8a; font-weight: 700;"
    if numero < 80:
        return "color: #7b8782;"
    return ""


def _tabla(df: pd.DataFrame) -> pd.DataFrame:
    def dinero(valor):
        if valor is None or (isinstance(valor, float) and not np.isfinite(valor)) or pd.isna(valor):
            return "N/D"
        return f"{float(valor):,.2f}"

    def gap(valor):
        if valor is None or (isinstance(valor, float) and not np.isfinite(valor)) or pd.isna(valor):
            return "N/D"
        return f"{float(valor):+.2f}%"

    return pd.DataFrame(
        {
            "Ticker": df["ticker"],
            "Nombre": df["nombre"],
            "Rubro": df["rubro"],
            "Precio USD": df["precio_usd"].map(dinero),
            "Var. 1D": df["variacion"].map(lambda v: f"{float(v):+.2f}%"),
            "RSI": df["rsi14"].map(lambda v: f"{float(v):.2f}"),
            "Vol. relativo": df["vol_relativo"].map(lambda v: f"{float(v):.1f}%"),
            "Stage 2": [
                "N/D" if bool(corta) else ("Sí" if bool(stage) else "No")
                for corta, stage in zip(df["historia_corta"], df["stage2"])
            ],
            "Lectura": df["lectura"],
            "Notas": df["penalizaciones"].map(lambda notas: " · ".join(notas) if notas else "—"),
            "Precio ARS": df["precio_ars"].map(dinero),
            "Gap vs CCL": df["gap_ccl"].map(gap),
        }
    )


def _mostrar_tabla(vista: pd.DataFrame) -> None:
    estilizada = (
        vista.style.map(_estilo_lectura, subset=["Lectura"])
        .map(_estilo_variacion, subset=["Var. 1D", "Gap vs CCL"])
        .map(_estilo_volumen, subset=["Vol. relativo"])
    )
    st.dataframe(estilizada, width="stretch", hide_index=True, height=520)


def vista_resumen() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    df = panel["filas"]
    ccl = panel["ccl"]
    alcistas = df["lectura"].str.contains("alcista", case=False) & ~df["lectura"].str.contains("observación", case=False)
    con_media = df.loc[~df["historia_corta"].astype(bool)]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CCL implícito (AAPL)", "N/D" if not ccl else f"{ccl:,.0f} ARS")
    m2.metric("Lecturas alcistas", f"{int(alcistas.sum())} / {len(df)}")
    m3.metric("Stage 2 (sobre EMA 200)", f"{int(con_media['stage2'].sum())}")
    m4.metric("CEDEARs en el panel", f"{len(df)}")
    st.caption(
        "El CCL sale de AAPL.BA y AAPL con ratio 20. "
        "La lectura es técnica y de corto plazo: no es una instrucción de operar."
    )

    st.markdown("### Movimiento del día")
    c1, c2, c3, c4 = st.columns(4)
    bloques = (
        (c1, "Mayores subas", df.nlargest(5, "variacion"), "variacion", lambda v: f"{v:+.2f}%"),
        (c2, "Mayores bajas", df.nsmallest(5, "variacion"), "variacion", lambda v: f"{v:+.2f}%"),
        (c3, "RSI más bajo", df.nsmallest(5, "rsi14"), "rsi14", lambda v: f"{v:.2f}"),
        (c4, "RSI más alto", df.nlargest(5, "rsi14"), "rsi14", lambda v: f"{v:.2f}"),
    )
    for columna, titulo, bloque, campo, fmt in bloques:
        with columna:
            st.markdown(f"**{titulo}**")
            mini = bloque[["ticker", campo]].copy()
            mini.columns = ["Ticker", titulo]
            mini[titulo] = bloque[campo].map(fmt).values
            st.dataframe(mini, hide_index=True, width="stretch", height=230)

    cambios = df[df["giro"].notna()]
    st.markdown("### Cambios de lectura")
    if cambios.empty:
        st.info("Hoy no hay cambios de sesgo entre la rueda previa y la última.")
    else:
        for fila in cambios.itertuples(index=False):
            st.warning(f"**{fila.ticker}** ({fila.nombre}): {fila.giro}. Variación del día {fila.variacion:+.2f}%.")

    if panel["sin_precio_ars"] or panel["sin_precio_usd"] or panel["sin_historia"]:
        with st.expander("Símbolos fuera de esta descarga"):
            if panel["sin_precio_usd"]:
                st.write("Sin serie en USD:", ", ".join(panel["sin_precio_usd"]))
            if panel["sin_precio_ars"]:
                st.write("Sin precio en pesos:", ", ".join(panel["sin_precio_ars"]))
            if panel["sin_historia"]:
                st.write("Con poca historia para la EMA 200:", ", ".join(panel["sin_historia"]))


def vista_monitor() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    df = panel["filas"].copy()
    st.markdown("### Monitor")
    st.caption(
        "Gap vs CCL: positivo quiere decir que el CEDEAR implica un dólar más caro que el CCL de Apple. "
        "El calendario de balances se consulta recién en Análisis por activo."
    )
    f1, f2, f3 = st.columns([1.4, 1, 1])
    with f1:
        busqueda = st.text_input("Buscar ticker o nombre", placeholder="Ej. MELI, bancos, oro")
    with f2:
        rubro = st.selectbox("Rubro", ["Todos", *sorted(df["rubro"].unique())])
    with f3:
        lectura = st.selectbox("Lectura", ["Todas", *sorted(df["lectura"].unique())])
    solo_stage = st.checkbox("Solo Stage 2")

    if busqueda.strip():
        texto = busqueda.strip().lower()
        mask = (
            df["ticker"].str.lower().str.contains(texto, regex=False)
            | df["nombre"].str.lower().str.contains(texto, regex=False)
            | df["rubro"].str.lower().str.contains(texto, regex=False)
        )
        df = df[mask]
    if rubro != "Todos":
        df = df[df["rubro"] == rubro]
    if lectura != "Todas":
        df = df[df["lectura"] == lectura]
    if solo_stage:
        df = df[df["stage2"]]

    st.caption(f"{len(df)} activos")
    if df.empty:
        st.info("Ningún activo coincide con el filtro.")
        return
    _mostrar_tabla(_tabla(df))


def _grafico(fila: pd.Series, hist: pd.DataFrame) -> go.Figure:
    close = hist["Close"].astype(float)
    volumen = hist["Volume"].astype(float) if "Volume" in hist.columns else pd.Series(0.0, index=hist.index)
    sma10, sma20, sma50 = sma(close, 10), sma(close, 20), sma(close, 50)
    ema200 = ema(close, 200)
    rsi14 = rsi(close, 14)
    macd_line, macd_signal, _ = macd(close)
    boll_up, _, boll_low = bollinger(close)
    vol_media = sma(volumen, 20)
    vista = hist.iloc[-252:]
    idx = vista.index

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.52, 0.16, 0.16, 0.16],
        subplot_titles=(f"{fila['nombre']} ({fila['ticker']})", "Volumen", "RSI 14", "MACD"),
    )
    fig.add_trace(
        go.Candlestick(
            x=idx,
            open=vista["Open"],
            high=vista["High"],
            low=vista["Low"],
            close=vista["Close"],
            name="Precio",
            increasing_line_color="#1f7a4d",
            decreasing_line_color="#a33b32",
        ),
        row=1,
        col=1,
    )
    for serie, nombre, color in (
        (sma10, "SMA 10", "#1d6a8a"),
        (sma20, "SMA 20", "#b07a30"),
        (sma50, "SMA 50", "#8d6b4a"),
        (ema200, "EMA 200", "#1e3a34"),
    ):
        fig.add_trace(go.Scatter(x=idx, y=serie.loc[idx], name=nombre, line=dict(width=1.4, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=boll_up.loc[idx], name="Bollinger sup.", line=dict(width=1, dash="dot", color="#8aa099")), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=boll_low.loc[idx], name="Bollinger inf.", line=dict(width=1, dash="dot", color="#8aa099")), row=1, col=1)

    colores = ["#1f7a4d" if c >= o else "#a33b32" for o, c in zip(vista["Open"], vista["Close"])]
    fig.add_trace(go.Bar(x=idx, y=vista["Volume"], name="Volumen", marker_color=colores), row=2, col=1)
    fig.add_trace(go.Scatter(x=idx, y=vol_media.loc[idx], name="Volumen 20d", line=dict(width=1.2, color="#b07a30")), row=2, col=1)
    fig.add_trace(go.Scatter(x=idx, y=rsi14.loc[idx], name="RSI", line=dict(width=1.4, color="#3e5568")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#a33b32", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#1f7a4d", row=3, col=1)
    fig.add_trace(go.Scatter(x=idx, y=macd_line.loc[idx], name="MACD", line=dict(width=1.4, color="#1d6a8a")), row=4, col=1)
    fig.add_trace(go.Scatter(x=idx, y=macd_signal.loc[idx], name="Señal", line=dict(width=1.4, color="#b07a30")), row=4, col=1)
    fig.update_layout(
        height=820,
        template=_plantilla(),
        xaxis_rangeslider_visible=False,
        margin=dict(t=40, b=16, l=8, r=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def _consenso(ficha: dict, precio: float, lectura: str) -> None:
    col_lectura, col_gauge = st.columns([1, 1.15])
    with col_lectura:
        st.markdown("**Lectura técnica de corto plazo**")
        st.subheader(lectura)
        st.write(f"Precio USD: **{precio:,.2f}**")
        objetivo = ficha.get("objetivo")
        upside = None
        if _finito(objetivo) and precio:
            upside = objetivo / precio - 1
            st.write(f"Precio objetivo promedio a 12 meses: **{objetivo:,.2f}** ({upside * 100:+.1f}%)")
            firmas = ficha.get("analistas")
            if _finito(firmas):
                st.caption(f"Promedio de {int(firmas)} firmas, según Yahoo Finance.")
        else:
            st.caption("Este activo no tiene precio objetivo de analistas en Yahoo.")

        if upside is not None and upside < 0:
            st.warning(
                "El precio objetivo promedio está por debajo de la cotización. "
                "Esa meta a 12 meses y la lectura técnica de corto plazo son datos distintos, "
                "y ninguno es una instrucción de operar."
            )
        elif upside is not None and upside > 0.05 and lectura in (
            SESGO_ALCISTA,
            SESGO_ALCISTA_MARCADO,
            ALCISTA_CON_VOLUMEN,
            ALCISTA_SIN_VOLUMEN,
        ):
            st.info(
                "La lectura técnica y el objetivo a 12 meses están del lado positivo. "
                "Sigue siendo una descripción de datos, no una recomendación."
            )

    with col_gauge:
        puntaje = ficha.get("puntaje")
        if not _finito(puntaje):
            st.info("Sin puntaje de consenso para este activo.")
            return
        clave = str(ficha.get("recomendacion") or "").lower()
        nombre = TRADUCCION_CONSENSO.get(clave, clave.replace("_", " ").title() or "Sin etiqueta")
        visual = 6 - float(puntaje)
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=round(visual, 2),
                number={"valueformat": ".2f", "suffix": " / 5"},
                title={"text": f"Consenso de analistas<br><span style='font-size:0.85em'>{nombre}</span>"},
                gauge={
                    "axis": {
                        "range": [1, 5],
                        "tickvals": [1, 2, 3, 4, 5],
                        "ticktext": ["Muy cauto", "Cauto", "Neutro", "Positivo", "Muy positivo"],
                    },
                    "bar": {"color": "#1e3a34", "thickness": 0.28},
                    "steps": [
                        {"range": [1, 1.8], "color": "#e7c7c3"},
                        {"range": [1.8, 2.6], "color": "#f0ddc4"},
                        {"range": [2.6, 3.4], "color": "#efe6c8"},
                        {"range": [3.4, 4.2], "color": "#d5e8dc"},
                        {"range": [4.2, 5], "color": "#b7d7c4"},
                    ],
                },
            )
        )
        fig.update_layout(height=280, margin=dict(t=50, b=8, l=24, r=24), template=_plantilla())
        st.plotly_chart(fig, width="stretch", theme=None, key="gauge_consenso")


def vista_activo() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    df = panel["filas"]
    opciones = df.sort_values("ticker")["ticker"].tolist()
    ticker = st.selectbox(
        "Activo",
        opciones,
        format_func=lambda clave: f"{clave} — {WATCHLIST[clave]['name']}",
    )
    fila = df.loc[df["ticker"] == ticker].iloc[0]
    hist = panel["historicos"][ticker]
    with st.spinner("Consultando consenso y calendario…"):
        ficha = ficha_activo(WATCHLIST[ticker]["underlying"], clave_cierre())

    dias = ficha.get("dias_balance")
    if ficha.get("balance_cerca"):
        st.warning(
            f"Hay un balance informado dentro de los próximos {dias} días. "
            "Con una lectura alcista, el criterio del panel es dejar el activo en observación."
        )
        if fila["lectura"] in (SESGO_ALCISTA, SESGO_ALCISTA_MARCADO, ALCISTA_CON_VOLUMEN):
            fila = fila.copy()
            fila["lectura"] = EN_OBSERVACION_RIESGO
    elif dias is not None:
        st.caption(f"Próximo balance informado en {dias} días.")

    _consenso(ficha, float(fila["precio_usd"]), fila["lectura"])

    a, b, c, d = st.columns(4)
    a.metric("RSI 14", f"{fila['rsi14']:.2f}")
    b.metric("Volumen relativo", f"{fila['vol_relativo']:.1f}%")
    c.metric("Stage 2", "Alineada" if fila["stage2"] else "No alineada")
    d.metric("Gap vs CCL", "N/D" if fila["gap_ccl"] is None or pd.isna(fila["gap_ccl"]) else f"{fila['gap_ccl']:+.2f}%")

    st.plotly_chart(_grafico(fila, hist), width="stretch", theme=None, key=f"grafico_{ticker}")

    st.markdown("### Datos del negocio")
    st.caption("Cifras del subyacente en Yahoo Finance. Describen la empresa: no arman una recomendación.")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Sector", str(ficha.get("sector") or "—"))
    g2.metric("PER", _num(ficha.get("per")))
    g3.metric("PEG", _num(ficha.get("peg")))
    g4.metric("ROE", _pct(ficha.get("roe"), 1))
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Margen neto", _pct(ficha.get("margen"), 1))
    h2.metric("Deuda / patrimonio", _num(ficha.get("deuda_patrimonio"), 0, "%"))
    h3.metric("Crecimiento de ingresos", _pct(ficha.get("crecimiento"), 1))
    h4.metric("Dividendo", _num(ficha.get("dividendo"), 2, "%"))


def _rrg_de_panel(panel: dict) -> pd.DataFrame:
    precios = panel["precios_usd"]
    columnas = {}
    for clave, cfg in WATCHLIST.items():
        simbolo = cfg["underlying"]
        if simbolo in precios.columns:
            columnas[clave] = precios[simbolo]
    if "SPY" in precios.columns and "SPY" not in columnas:
        columnas["SPY"] = precios["SPY"]
    return calcular_rrg(pd.DataFrame(columnas).sort_index())


def vista_radar() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    st.markdown("### Radar de fuerza relativa")
    st.caption(
        "Cada punto compara el subyacente contra SPY. "
        "La fuerza es el z-score de 50 ruedas del ratio de precios y el momentum es su cambio a 10 ruedas. "
        "Los nombres se leen en la tabla: en el gráfico solo se etiquetan los más alejados del centro, para que no se pisen."
    )
    df = _rrg_de_panel(panel)
    if df.empty:
        st.error("No alcanzó la historia para armar el radar. Recargá en unos minutos.")
        return

    grafico, lista = st.columns([1.6, 1])
    with grafico:
        etiquetar = set()
        for _, bloque in df.groupby("Cuadrante"):
            distancia = bloque["Fuerza_X"].abs() + bloque["Momentum_Y"].abs()
            etiquetar.update(bloque.loc[distancia.nlargest(5).index, "Ticker"])
        plot = df.copy()
        plot["Etiqueta"] = plot["Ticker"].where(plot["Ticker"].isin(etiquetar), "")
        fig = px.scatter(
            plot,
            x="Fuerza_X",
            y="Momentum_Y",
            text="Etiqueta",
            color="Cuadrante",
            hover_name="Ticker",
            color_discrete_map=COLORES_CUADRANTE,
            labels={"Fuerza_X": "Fuerza relativa", "Momentum_Y": "Momentum"},
        )
        pad_x = max(0.35, float(df["Fuerza_X"].abs().max()) * 0.18)
        pad_y = max(0.35, float(df["Momentum_Y"].abs().max()) * 0.18)
        x0, x1 = float(df["Fuerza_X"].min()) - pad_x, float(df["Fuerza_X"].max()) + pad_x
        y0, y1 = float(df["Momentum_Y"].min()) - pad_y, float(df["Momentum_Y"].max()) + pad_y
        for xa, xb, ya, yb, color in (
            (0, x1, 0, y1, "rgba(31,122,77,0.08)"),
            (x0, 0, 0, y1, "rgba(29,106,138,0.08)"),
            (0, x1, y0, 0, "rgba(176,122,48,0.10)"),
            (x0, 0, y0, 0, "rgba(163,59,50,0.08)"),
        ):
            fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=color, line_width=0, layer="below")
        fig.add_hline(y=0, line_width=1, line_color="#8aa099")
        fig.add_vline(x=0, line_width=1, line_color="#8aa099")
        for x, y, texto, ancla_x, ancla_y, color in (
            (x1, y1, "Líderes", "right", "top", "#1f7a4d"),
            (x0, y1, "Mejorando", "left", "top", "#1d6a8a"),
            (x1, y0, "Debilitándose", "right", "bottom", "#b07a30"),
            (x0, y0, "Rezagados", "left", "bottom", "#a33b32"),
        ):
            fig.add_annotation(
                x=x,
                y=y,
                text=texto,
                showarrow=False,
                xanchor=ancla_x,
                yanchor=ancla_y,
                font=dict(color=color, size=13),
            )
        fig.update_traces(textposition="top center", marker=dict(size=11, line=dict(width=0.6, color="#1c2430")))
        fig.update_layout(
            height=640,
            template=_plantilla(),
            margin=dict(t=24, b=16, l=8, r=8),
            legend_title_text="",
            xaxis=dict(range=[x0, x1]),
            yaxis=dict(range=[y0, y1]),
        )
        st.plotly_chart(fig, width="stretch", theme=None, key="radar_rrg")

    with lista:
        st.markdown("**Activos con fuerza relativa**")
        st.caption("Líderes y mejorando, ordenados por momentum.")
        destacados = df[df["Cuadrante"].isin(["Líderes", "Mejorando"])].sort_values("Momentum_Y", ascending=False).head(10)
        if destacados.empty:
            st.info("Ningún activo en líderes o mejorando.")
        else:
            for fila in destacados.itertuples(index=False):
                st.markdown(f"**{fila.Ticker}** · {fila.Cuadrante}")

    cuadrante = st.selectbox("Ver cuadrante", ["Todos", *COLORES_CUADRANTE.keys()])
    tabla = df if cuadrante == "Todos" else df[df["Cuadrante"] == cuadrante]
    st.dataframe(
        tabla.sort_values(["Cuadrante", "Momentum_Y"], ascending=[True, False]),
        width="stretch",
        hide_index=True,
        height=360,
    )


def _tabla_ranking(bloque: pd.DataFrame) -> pd.DataFrame:
    ordenado = bloque.sort_values(["Fuerza", "Momentum"], ascending=False)
    filas = []
    for fila in ordenado.itertuples(index=False):
        filas.append(
            {
                "Símbolo": fila.Ticker,
                "Nombre": fila.Nombre,
                "Cuadrante": fila.Cuadrante,
                "Fuerza": f"{fila.Fuerza:.1f}",
                "Momentum": f"{fila.Momentum:.1f}",
                "1 semana": texto_periodo(fila.ex_1s, fila.flecha_1s),
                "1 mes": texto_periodo(fila.ex_1m, fila.flecha_1m),
                "3 meses": texto_periodo(fila.ex_3m, fila.flecha_3m),
            }
        )
    return pd.DataFrame(filas)


def _grafico_rotacion(colas: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    color_texto = "#e7eeea" if st.session_state.get("tema") == "Oscuro" else "#1c2430"
    posiciones = ["top center", "bottom center", "middle right", "middle left"]
    for indice, (ticker, grupo) in enumerate(colas.groupby("Ticker", sort=False)):
        grupo = grupo.sort_values("Orden")
        nombre = str(grupo["Nombre"].iloc[0])
        n = len(grupo)
        textos = [""] * n
        textos[-1] = ticker
        fig.add_trace(
            go.Scatter(
                x=grupo["Fuerza"],
                y=grupo["Momentum"],
                mode="lines+markers+text",
                name=f"{ticker} · {nombre}",
                text=textos,
                textposition=posiciones[indice % len(posiciones)],
                textfont=dict(size=12, color=color_texto),
                line=dict(color=PALETA.get(ticker, "#3e5568"), width=2),
                marker=dict(
                    size=[8 + 8 * (i / max(n - 1, 1)) for i in range(n)],
                    color=PALETA.get(ticker, "#3e5568"),
                    line=dict(width=0.6, color=color_texto),
                ),
                hovertemplate=f"{ticker} · {nombre}<br>Fuerza %{{x:.1f}}<br>Momentum %{{y:.1f}}<extra></extra>",
            )
        )

    xs = colas["Fuerza"]
    ys = colas["Momentum"]
    pad_x = max(3.0, float(xs.max() - xs.min()) * 0.22)
    pad_y = max(3.0, float(ys.max() - ys.min()) * 0.28)
    x0, x1 = min(float(xs.min()), 100.0) - pad_x, max(float(xs.max()), 100.0) + pad_x
    y0, y1 = min(float(ys.min()), 100.0) - pad_y, max(float(ys.max()), 100.0) + pad_y
    for xa, xb, ya, yb, color in (
        (100, x1, 100, y1, "rgba(31,122,77,0.08)"),
        (x0, 100, 100, y1, "rgba(29,106,138,0.08)"),
        (100, x1, y0, 100, "rgba(176,122,48,0.10)"),
        (x0, 100, y0, 100, "rgba(163,59,50,0.08)"),
    ):
        fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=color, line_width=0, layer="below")
    fig.add_hline(y=100, line_width=1, line_color="#8aa099")
    fig.add_vline(x=100, line_width=1, line_color="#8aa099")
    margen_x = (x1 - x0) * 0.012
    margen_y = (y1 - y0) * 0.012
    for x, y, texto, ancla_x, ancla_y, color in (
        (x1 - margen_x, y1 - margen_y, "Líder", "right", "top", "#1f7a4d"),
        (x0 + margen_x, y1 - margen_y, "Mejorando", "left", "top", "#1d6a8a"),
        (x1 - margen_x, y0 + margen_y, "Debilitándose", "right", "bottom", "#b07a30"),
        (x0 + margen_x, y0 + margen_y, "Rezagado", "left", "bottom", "#a33b32"),
    ):
        fig.add_annotation(
            x=x,
            y=y,
            text=texto,
            showarrow=False,
            xanchor=ancla_x,
            yanchor=ancla_y,
            font=dict(color=color, size=14),
        )
    fig.update_layout(
        height=680,
        template=_plantilla(),
        margin=dict(t=36, b=48, l=24, r=24),
        legend_title_text="",
        legend=dict(font=dict(size=12)),
        xaxis=dict(title="Fuerza relativa (100 = promedio de 6 meses)", range=[x0, x1]),
        yaxis=dict(title="Momentum (100 = hace 10 ruedas)", range=[y0, y1]),
    )
    return fig


def vista_rotacion() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    st.markdown("### Rotación sectorial")
    rotacion = armar_rotacion(panel["precios_usd"])
    st.markdown(f"**{rotacion['frase']}**")
    st.caption(
        "Lectura descriptiva de cómo se movieron los sectores contra SPY. "
        "No es una instrucción de compra ni de venta."
    )

    colas = rotacion["colas"]
    if colas.empty:
        st.error("No alcanzó la historia para armar el gráfico de rotación. Recargá en unos minutos.")
    else:
        st.plotly_chart(_grafico_rotacion(colas), width="stretch", theme=None, key="rotacion_rrg")
        st.caption(
            "Cada cola son las últimas cinco semanas, una marca por semana. El punto grande es el cierre de hoy. "
            "Arriba a la derecha: Líder. Arriba a la izquierda: Mejorando. "
            "Abajo a la derecha: Debilitándose. Abajo a la izquierda: Rezagado."
        )

    ranking = rotacion["ranking"]
    if ranking.empty:
        st.warning("Sin ranking: Yahoo no devolvió los ETF de sector.")
    else:
        st.markdown("**Fuerza y ritmo contra SPY**")
        st.caption(
            "El porcentaje es el exceso de retorno contra SPY en 1 semana, 1 mes y 3 meses. "
            "▲ ganó ritmo contra la ventana anterior del mismo largo; ▼ lo perdió; → quedó parejo."
        )
        sectores = ranking[ranking["Grupo"] == "Sector"]
        indices = ranking[ranking["Grupo"] == "Índice"]
        st.markdown("Sectores")
        st.dataframe(_tabla_ranking(sectores), width="stretch", hide_index=True)
        if not indices.empty:
            st.markdown("Índices")
            st.dataframe(_tabla_ranking(indices), width="stretch", hide_index=True)

    if rotacion["sin_datos"]:
        st.caption("Sin serie suficiente en Yahoo: " + ", ".join(rotacion["sin_datos"]) + ".")

    presentes = set(panel["filas"]["ticker"].astype(str))
    mapa = []
    for ticker, datos in SECTORES.items():
        nombres = cedears_visibles(ticker, presentes)
        etf = WATCHLIST.get(ticker)
        mapa.append(
            {
                "Sector": datos["nombre"],
                "ETF": ticker,
                "CEDEAR del ETF": etf["cedear"] if etf else "—",
                "CEDEARs del panel": ", ".join(nombres) if nombres else "—",
            }
        )
    st.markdown("**CEDEARs del panel en cada sector**")
    st.dataframe(pd.DataFrame(mapa), width="stretch", hide_index=True)
    indices_cedear = []
    for ticker, nombre in INDICES.items():
        cfg = WATCHLIST.get(ticker)
        if cfg:
            indices_cedear.append(f"{nombre} ({ticker}) → {cfg['cedear']}")
        else:
            indices_cedear.append(f"{nombre} ({ticker}) no tiene CEDEAR en el panel")
    st.caption(
        "Es el recorte que sigue este tablero, no la cartera completa del ETF. "
        "Índices: " + " · ".join(indices_cedear) + "."
    )


def _torta(tabla: pd.DataFrame) -> go.Figure:
    fig = px.pie(
        tabla,
        values="Porcentaje",
        names="Activo",
        hole=0.46,
        color_discrete_sequence=COLORES_TORTA,
    )
    fig.update_traces(textinfo="percent", textposition="inside", sort=False)
    fig.update_layout(
        showlegend=True,
        template=_plantilla(),
        margin=dict(t=8, b=8, l=8, r=8),
        height=420,
        legend=dict(font=dict(size=12)),
    )
    return fig


def _bloque_cartera(clave: str, precios: pd.DataFrame) -> None:
    perfil = PERFILES[clave]
    tabla = composicion(clave)
    st.markdown(f"**{perfil['titulo']}**")
    st.caption(perfil["detalle_fija"])
    try:
        stats = metricas_historicas(precios, pesos_variable(clave))
    except Exception:
        logging.exception("Métricas de cartera %s", clave)
        stats = None

    if stats is None:
        st.warning("No se pudieron calcular las métricas históricas con los precios de hoy.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            f"Rendimiento {stats['inicio']:%d/%m/%y}–{stats['fin']:%d/%m/%y}",
            _pct(stats["rendimiento"]),
        )
        c2.metric("Volatilidad anualizada", _pct(stats["volatilidad"]))
        c3.metric("Caída máxima", _pct(stats["caida_maxima"]))
        c4.metric("VaR 95% diario", _pct(stats["var_95"]))
        momento = ahora_art()
        st.caption(
            f"Período {stats['inicio']:%d/%m/%Y} – {stats['fin']:%d/%m/%Y} "
            f"({stats['sesiones']} ruedas de USD). Calculado el {momento:%d/%m/%Y %H:%M} ART "
            "con QuantStats, sobre el bloque de renta variable, pesos constantes y rebalanceo diario implícito. "
            f"Sharpe {stats['sharpe']:.2f} · Sortino {stats['sortino']:.2f}. "
            "Es una descripción de lo que pasó, no un rendimiento esperado ni una promesa."
        )
        if stats["faltantes"]:
            st.caption("Sin serie y fuera del cálculo: " + ", ".join(stats["faltantes"]) + ".")

    grafico, detalle = st.columns([1.15, 1])
    with grafico:
        st.plotly_chart(_torta(tabla), width="stretch", theme=None, key=f"torta_{clave}")
    with detalle:
        vista = tabla.copy()
        vista["Porcentaje"] = vista["Porcentaje"].map(lambda v: f"{v:.1f}%")
        st.dataframe(vista, hide_index=True, width="stretch")
        variable = tabla[tabla["Bloque"] == "Renta variable"]["Porcentaje"].sum()
        fija = tabla[tabla["Bloque"] == "Renta fija"]["Porcentaje"].sum()
        st.caption(f"Renta fija {fija:.1f}% · renta variable {variable:.1f}%.")


def vista_carteras() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    st.markdown("### Carteras modelo")
    st.caption(
        "La asignación de renta fija es la que ya estaba publicada (65% y 30%). "
        "El bloque de acciones se reescaló para que la torta cierre en 100% y coincida con ese texto: "
        "antes los pesos sumaban 90 y 92,8 y el gráfico los inflaba."
    )
    conservadora, agresiva = st.tabs(["Perfil conservador", "Perfil de crecimiento"])
    with conservadora:
        _bloque_cartera("conservador", panel["precios_usd"])
    with agresiva:
        _bloque_cartera("agresivo", panel["precios_usd"])


def vista_metodologia() -> None:
    st.markdown("### Cómo está armada la lectura")
    st.markdown(
        """
El puntaje técnico mira, en dólares y sobre el subyacente:

- la EMA de 200 ruedas (si el precio está debajo, resta);
- el orden de las medias de 10 y 20, con una excepción si el precio ya recuperó ambas;
- el MACD (suma si está arriba de su señal; no resta si está abajo pero la curva ya gira);
- los cruces al alza de la media de 10 contra la de 20 y contra la de 50;
- el RSI (suma en 35 o menos, resta en 70 o más) y las bandas de Bollinger.

**Sesgo alcista marcado** pide un puntaje de 3 o más. **Sesgo alcista** pide 1 o 2.
**Sesgo bajista** es −2. **Sesgo bajista marcado** es −3 o menos. Cero y −1 quedan **neutrales**.
Antes, la rama de sesgo bajista más extremo no se podía alcanzar: quedaba tapada por la condición anterior.

Después entra el volumen relativo a 20 ruedas. Arriba de 120% y con vela verde, la lectura alcista pasa a
**alcista con volumen**. Con vela roja, a **distribución con volumen**. Debajo de 80% queda
**alcista sin volumen**. Si la lectura es bajista pero el día sube con volumen alto, pasa a
**en observación (ruptura)**.

Una caída intradía mayor a dos veces el ATR, o un balance dentro de los 5 días (esto último solo
en la ficha del activo), deja una lectura alcista **en observación (riesgo)**.

**Stage 2** significa precio sobre la EMA 200 y esa media subiendo contra 20 ruedas atrás.
Si el subyacente tiene menos de 210 ruedas (hoy, SpaceX), entra igual al monitor como **Historia corta**,
con precio y gap, pero sin sesgo de medias.

**Gap vs CCL** compara el dólar implícito de cada CEDEAR con el de Apple
`(precio ARS × ratio) / precio USD`. Los ratios y los símbolos de Yahoo se revisaron contra el listado de BYMA.
En particular: 3M usa `MMM.BA` (antes apuntaba a CrowdStrike), Bank of America usa `BA-C.BA`,
Constellation usa `CEG.BA`, Halliburton figura como `HAL`, Morgan Stanley usa ratio 41,
Japón (`EWJ`) ratio 14 y el sector de comunicaciones (`XLC`) ratio 19.
`BNG.BA` (Bunge) y `SPCX.BA` (SpaceX) cotizan y se dejaron como estaban.

**Radar.** Fuerza relativa contra SPY, normalizada a 50 ruedas, y su cambio a 10 ruedas.
Arriba a la derecha: líderes. Arriba a la izquierda: mejorando. Abajo a la derecha: debilitándose.
Abajo a la izquierda: rezagados.

**Rotación sectorial.** Otra cuenta, sobre los ETF de sector (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC)
y los índices QQQ, IWM, EEM, EWZ y ARGT, siempre contra SPY. La fuerza es el ratio de precios suavizado,
puesto en 100 contra su promedio de unos seis meses. El momentum compara esa fuerza con la de diez ruedas atrás.
La cola del gráfico son las últimas cinco semanas. Las flechas de 1 semana, 1 mes y 3 meses dicen si el
exceso contra SPY de esa ventana mejoró o empeoró contra la ventana anterior del mismo largo.
El listado de CEDEARs es el recorte de este panel, no la cartera completa del ETF.

**Carteras modelo.** Los pesos de renta fija se respetan. Las métricas (rendimiento compuesto,
volatilidad anualizada, caída máxima, VaR 95% diario, Sharpe y Sortino) las calcula QuantStats
sobre el bloque de renta variable, con los precios de Yahoo, en la moneda del subyacente.
No incluyen las obligaciones negociables. No son un pronóstico.

Los datos salen de Yahoo Finance en una descarga agrupada, con caché hasta el próximo cierre
de las 18:00, hora de Argentina. El consenso de analistas y el calendario se piden solo
cuando se abre un activo.
        """
    )
    st.markdown("### Contacto")
    c1, c2 = st.columns(2)
    c1.link_button("Escribir por WhatsApp", WHATSAPP, width="stretch")
    c2.link_button("zetafinance.com.ar", SITIO, width="stretch")
