"""Páginas del panel."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from zeta.analisis_global import armar_analisis_global
from zeta.carteras import PERFILES, composicion, metricas_historicas, pesos_variable
from zeta.datos import cargar_panel, ficha_activo
from zeta.indicadores import bollinger, ema, macd, rsi, sma
from zeta.marca import LOGO, LOGO_HEADER, aviso, linea_identidad, mostrar_enlaces, selector_tema
from zeta.paleta import paleta, tema_activo
from zeta.rotacion import (
    INDICES,
    SECTORES,
    armar_rotacion,
    cedears_visibles,
    cuadrante,
    texto_periodo,
    ubicar_etiquetas,
)
from zeta.rrg import calcular_rrg, rango_ejes
from zeta.senales import (
    ALCISTA_CON_VOLUMEN,
    ALCISTA_SIN_VOLUMEN,
    EN_OBSERVACION_RIESGO,
    SESGO_ALCISTA,
    SESGO_ALCISTA_MARCADO,
)
from zeta.tiempo import ahora_art, clave_cierre, linea_datos
from zeta.universo import WATCHLIST

TRADUCCION_CONSENSO = {
    "strong_buy": "Muy positivo",
    "buy": "Positivo",
    "hold": "Neutro",
    "underperform": "Cauto",
    "sell": "Cauto",
    "strong_sell": "Muy cauto",
}


# El Radar mira ~50 ruedas. La rotación, el promedio de ~126. Misma lectura, otro plazo.
HORIZONTE_RADAR = "Corto plazo, ~2,5 meses"
HORIZONTE_ROTACION = "Mediano plazo, ~6 meses"
NOTA_RADAR_Y_ROTACION = (
    "Un mismo activo puede figurar distinto en el Radar y en la rotación, y no es una contradicción. "
    "El Radar (corto plazo, ~2,5 meses) reacciona antes. "
    "La rotación (mediano plazo, ~6 meses) confirma más tarde."
)


def _colores_cuadrante() -> dict[str, str]:
    p = paleta()
    return {
        "Líderes": p["lider"],
        "Mejorando": p["mejorando"],
        "Debilitándose": p["debilitando"],
        "Rezagados": p["rezagado"],
    }


def _color_cola(nombre: str) -> str:
    return _colores_cuadrante()[nombre]


def _titulo_horizonte(fig: go.Figure, texto: str) -> None:
    """El plazo va pegado al borde de arriba, por encima de la leyenda y de las siglas."""
    p = paleta()
    fig.update_layout(
        title=dict(
            text=texto,
            x=0,
            xanchor="left",
            y=1,
            yanchor="top",
            yref="container",
            pad=dict(t=10, b=0, l=8, r=0),
            font=dict(family=p["fuente"], size=15, color=p["texto_grafico"]),
        )
    )


def _cerrar_grafico(fig: go.Figure) -> go.Figure:
    p = paleta()
    fig.update_layout(
        template=p["plantilla"],
        paper_bgcolor=p["fondo_grafico"],
        plot_bgcolor=p["fondo_grafico"],
        font=dict(color=p["texto_grafico"], family=p["fuente"]),
        legend=dict(font=dict(color=p["texto_grafico"])),
    )
    eje = dict(
        gridcolor=p["grilla"],
        zeroline=False,
        linecolor=p["borde"],
        tickfont=dict(color=p["mute_grafico"], family=p["fuente"]),
        title_font=dict(color=p["titulo_eje"], family=p["fuente"]),
    )
    fig.update_xaxes(**eje)
    fig.update_yaxes(**eje)
    return fig


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
        with st.spinner("Descargando cotizaciones…"):
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
    selector_tema()
    mostrar_enlaces(barra=True)

    def _salir():
        st.session_state["autenticado"] = False

    st.sidebar.button("Cerrar sesión", on_click=_salir, width="stretch")


def aviso_datos(panel: dict | None, extra: str = "", precios: bool = True) -> None:
    """Sello visible. La hora es la de la descarga cacheada, no la de abrir la página."""
    import html

    if not panel or not panel.get("obtenido_en"):
        texto = "Datos actualizados: sin una descarga vigente. Usá Actualizar datos para pedirla de nuevo."
    elif precios:
        texto = linea_datos(
            pd.Timestamp(panel["obtenido_en"]),
            pd.Timestamp(panel["ultima_rueda"]) if panel.get("ultima_rueda") else None,
            ultima_rueda_ars=pd.Timestamp(panel["ultima_rueda_ars"]) if panel.get("ultima_rueda_ars") else None,
        )
        if extra:
            texto = f"{texto} · {extra}"
    else:
        obtenido = ahora_art(pd.Timestamp(panel["obtenido_en"]))
        texto = f"Datos actualizados: {obtenido:%d/%m/%Y %H:%M} (hora Argentina)"
        if extra:
            texto = f"{texto} · {extra}"
    st.markdown(f'<div class="zeta-datos">{html.escape(texto)}</div>', unsafe_allow_html=True)


def _refrescar_datos() -> None:
    st.cache_data.clear()


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
            <p class="zeta-sub" style="margin:0.15rem 0 0;">CEDEARs</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        with st.spinner("Descargando cotizaciones…"):
            panel = cargar_panel(clave_cierre())
    except Exception:
        logging.exception("No se pudo leer el sello de la descarga")
        panel = None
    texto, boton = st.columns([5.2, 1], vertical_alignment="center")
    with texto:
        extra = "Precios en vivo de data912" if panel and panel.get("fuente_viva") else ""
        aviso_datos(panel, extra=extra)
    if panel is not None and not panel.get("fuente_viva"):
        st.warning("data912 no respondió. Las señales quedan con el precio de Yahoo y sin contraste en vivo.")
    if panel is not None and isinstance(panel.get("sin_senal"), pd.DataFrame) and not panel["sin_senal"].empty:
        st.error(
            f"{len(panel['sin_senal'])} activos con el contraste en rojo. "
            "De esos no se calcula la señal."
        )
    with boton:
        st.button("Actualizar datos", on_click=_refrescar_datos, width="stretch")
    aviso()


def pie() -> None:
    st.divider()
    aviso()


def _estilo_lectura(valor: str) -> str:
    if not isinstance(valor, str):
        return ""
    p = paleta()
    texto = valor.lower()
    if "observación" in texto or "distribución" in texto or "sin volumen" in texto:
        return p["lectura_observacion"]
    if "marcado" in texto and "alcista" in texto or "con volumen" in texto:
        return p["lectura_alcista_fuerte"]
    if "alcista" in texto:
        return p["lectura_alcista"]
    if "marcado" in texto and "bajista" in texto:
        return p["lectura_bajista_fuerte"]
    if "bajista" in texto:
        return p["lectura_bajista"]
    return ""


def _estilo_variacion(valor: str) -> str:
    if not isinstance(valor, str) or "%" not in valor:
        return ""
    try:
        numero = float(valor.replace("%", "").replace("+", ""))
    except ValueError:
        return ""
    p = paleta()
    if numero > 0:
        return f"color: {p['variacion_pos']}; font-weight: 650;"
    if numero < 0:
        return f"color: {p['variacion_neg']}; font-weight: 650;"
    return ""


def _estilo_contraste(valor: str) -> str:
    texto = (valor or "").lower()
    if texto == "verde":
        return "color: #1e7f4f; font-weight: 650;"
    if texto == "amarillo":
        return "color: #a56b12; font-weight: 650;"
    if texto == "rojo":
        return "color: #a32020; font-weight: 650;"
    return ""


def _estilo_volumen(valor: str) -> str:
    if not isinstance(valor, str) or "%" not in valor:
        return ""
    try:
        numero = float(valor.replace("%", ""))
    except ValueError:
        return ""
    p = paleta()
    if numero > 120:
        return f"color: {p['volumen_alto']}; font-weight: 700;"
    if numero < 80:
        return f"color: {p['volumen_bajo']};"
    return ""


def mostrar_tabla(vista: pd.DataFrame, estilos: dict | None = None, alto: int = 420) -> None:
    """Tabla HTML pintada con la paleta activa. No depende del tema nativo de Streamlit."""
    import html

    p = paleta()
    estilos = estilos or {}
    encabezados = "".join(f"<th>{html.escape(str(columna))}</th>" for columna in vista.columns)
    cuerpo = []
    for fila in vista.itertuples(index=False):
        celdas = []
        for columna, valor in zip(vista.columns, fila):
            texto = "" if valor is None or (isinstance(valor, float) and not np.isfinite(valor)) else str(valor)
            if texto == "nan":
                texto = ""
            extra = estilos[columna](texto) if columna in estilos else ""
            celdas.append(f'<td style="{extra}">{html.escape(texto)}</td>')
        cuerpo.append("<tr>" + "".join(celdas) + "</tr>")
    st.markdown(
        f"""
        <div class="zeta-tabla-marco" style="max-height:{alto}px;">
          <table class="zeta-tabla">
            <thead><tr>{encabezados}</tr></thead>
            <tbody>{"".join(cuerpo)}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            "Contraste": df["contraste"].map(lambda v: str(v or "—").capitalize()) if "contraste" in df.columns else "—",
        }
    )


def _mostrar_tabla(vista: pd.DataFrame) -> None:
    mostrar_tabla(
        vista,
        estilos={
            "Lectura": _estilo_lectura,
            "Var. 1D": _estilo_variacion,
            "Gap vs CCL": _estilo_variacion,
            "Vol. relativo": _estilo_volumen,
            "Contraste": _estilo_contraste,
        },
        alto=520,
    )


def _cuadro_dolares(cuadro: dict | None) -> None:
    if not cuadro:
        return
    st.markdown("**Dólares y riesgo país, con contraste**")
    columnas = st.columns(4)
    for columna, (clave, titulo) in zip(
        columnas,
        (("mep", "MEP"), ("ccl", "CCL"), ("oficial", "Oficial mayorista"), ("riesgo", "Riesgo país")),
    ):
        pieza = cuadro.get(clave) or {}
        principal = pieza.get("principal")
        if principal is None:
            texto = "N/D"
        elif clave == "riesgo":
            texto = f"{principal:,.0f}"
        else:
            texto = f"{principal:,.1f}"
        estado = str(pieza.get("estado") or "sin dato")
        columna.metric(titulo, texto, estado)
        contraste = pieza.get("contraste")
        if contraste is not None:
            columna.caption(f"{pieza.get('fuente_contraste')}: {contraste:,.1f}" if clave != "riesgo" else f"{pieza.get('fuente_contraste')}: {contraste:,.0f}")
    fechas = cuadro.get("fechas") or {}
    st.caption(
        "MEP y CCL contra ArgentinaDatos (verde si difieren menos del 1%). "
        "El oficial es el mayorista de referencia del BCRA contra el mayorista de ArgentinaDatos. "
        "El riesgo país de Ámbito se contrasta con ArgentinaDatos (verde bajo 0,5%). "
        "Rojo si la diferencia pasa el 2%. "
        f"Fechas: MEP {fechas.get('bolsa') or '—'}, CCL {fechas.get('ccl') or '—'}, "
        f"BCRA {fechas.get('bcra') or '—'}, riesgo Ámbito {fechas.get('riesgo_ambito') or '—'}, "
        f"ArgentinaDatos {fechas.get('riesgo_argentina') or '—'}."
    )


def vista_resumen() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    df = panel["filas"]
    ccl = panel["ccl"]
    alcistas = df["lectura"].str.contains("alcista", case=False) & ~df["lectura"].str.contains("observación", case=False)
    con_media = df.loc[~df["historia_corta"].astype(bool)]
    m1, m2, m3, m4 = st.columns(4)
    sin_verificar = panel.get("sin_verificar")
    n_sin_verificar = 0 if not isinstance(sin_verificar, pd.DataFrame) else len(sin_verificar)
    n_universo = len(df) + n_sin_verificar + (0 if not isinstance(panel.get("sin_senal"), pd.DataFrame) else len(panel["sin_senal"]))
    m1.metric("CCL implícito (mediana)", "N/D" if not ccl else f"{ccl:,.0f} ARS")
    m2.metric("Lecturas alcistas", f"{int(alcistas.sum())} / {len(df)}")
    m3.metric("Stage 2 (sobre EMA 200)", f"{int(con_media['stage2'].sum())}")
    m4.metric("CEDEARs en el universo", f"{n_universo}")
    pares = panel.get("ccl_pares") or 0
    st.caption(
        f"El CCL es la mediana de {pares} pares con ratio verificado ({panel.get('ccl_fuente') or 'sin fuente'}). "
        f"Sin verificar: {n_sin_verificar}. Esos no entran al CCL ni al gap. "
        "La lectura es técnica y de corto plazo: no es una instrucción de operar."
    )
    _cuadro_dolares(panel.get("dolares"))

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
            mostrar_tabla(mini, estilos={titulo: _estilo_variacion} if campo == "variacion" else None, alto=230)

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
        "Gap vs CCL: positivo quiere decir que el CEDEAR implica un dólar más caro que la mediana de los pares verificados. "
        "El calendario completo de balances está en la página Balances."
    )
    if df.empty:
        st.info("Ningún activo tiene señal en esta rueda.")
    else:
        f1, f2, f3 = st.columns([1.4, 1, 1])
        with f1:
            busqueda = st.text_input("Buscar ticker o nombre", placeholder="Ej. MELI, bancos, oro")
        with f2:
            rubro = st.selectbox("Rubro", ["Todos", *sorted(df["rubro"].dropna().unique())])
        with f3:
            lectura = st.selectbox("Lectura", ["Todas", *sorted(df["lectura"].dropna().unique())])
        solo_stage = st.checkbox("Solo Stage 2")
        from zeta.extras import filtros_rapidos

        df = filtros_rapidos(panel, df)

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

        st.caption(f"{len(df)} activos con señal")
        if df.empty:
            st.info("Ningún activo coincide con el filtro.")
        else:
            _mostrar_tabla(_tabla(df))
    sin_verificar = panel.get("sin_verificar")
    if isinstance(sin_verificar, pd.DataFrame) and not sin_verificar.empty:
        with st.expander(f"Sin verificar ({len(sin_verificar)})"):
            st.caption(
                "Están en el feed de BYMA, pero el ratio no se pudo verificar. "
                "No entran al CCL, al gap ni a una señal que dependa de ese ratio."
            )
            mostrar_tabla(
                sin_verificar[["ticker", "nombre", "rubro", "precio_ars", "variacion", "contraste_motivo"]].rename(
                    columns={
                        "ticker": "Ticker",
                        "nombre": "Nombre",
                        "rubro": "Rubro",
                        "precio_ars": "Precio ARS",
                        "variacion": "Var. 1D",
                        "contraste_motivo": "Por qué",
                    }
                ),
                alto=360,
            )
    sin_senal = panel.get("sin_senal")
    if isinstance(sin_senal, pd.DataFrame) and not sin_senal.empty:
        with st.expander(f"Sin señal por contraste ({len(sin_senal)})"):
            st.caption("El contraste está en rojo. El precio se muestra y la señal no se calcula.")
            mostrar_tabla(
                sin_senal[["ticker", "nombre", "precio_ars", "contraste_motivo"]].rename(
                    columns={
                        "ticker": "Ticker",
                        "nombre": "Nombre",
                        "precio_ars": "Precio ARS",
                        "contraste_motivo": "Motivo",
                    }
                ),
                alto=280,
            )


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
            increasing_line_color=paleta()["vela_alta"],
            decreasing_line_color=paleta()["vela_baja"],
        ),
        row=1,
        col=1,
    )
    p = paleta()
    for serie, nombre, color in (
        (sma10, "SMA 10", p["sma10"]),
        (sma20, "SMA 20", p["sma20"]),
        (sma50, "SMA 50", p["sma50"]),
        (ema200, "EMA 200", p["ema200"]),
    ):
        fig.add_trace(go.Scatter(x=idx, y=serie.loc[idx], name=nombre, line=dict(width=1.4, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=boll_up.loc[idx], name="Bollinger sup.", line=dict(width=1, dash="dot", color=p["bollinger"])), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=boll_low.loc[idx], name="Bollinger inf.", line=dict(width=1, dash="dot", color=p["bollinger"])), row=1, col=1)

    colores = [p["vela_alta"] if c >= o else p["vela_baja"] for o, c in zip(vista["Open"], vista["Close"])]
    fig.add_trace(go.Bar(x=idx, y=vista["Volume"], name="Volumen", marker_color=colores), row=2, col=1)
    fig.add_trace(go.Scatter(x=idx, y=vol_media.loc[idx], name="Volumen 20d", line=dict(width=1.2, color=p["sma20"])), row=2, col=1)
    fig.add_trace(go.Scatter(x=idx, y=rsi14.loc[idx], name="RSI", line=dict(width=1.4, color=p["rsi"])), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color=p["vela_baja"], row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=p["vela_alta"], row=3, col=1)
    fig.add_trace(go.Scatter(x=idx, y=macd_line.loc[idx], name="MACD", line=dict(width=1.4, color=p["macd"])), row=4, col=1)
    fig.add_trace(go.Scatter(x=idx, y=macd_signal.loc[idx], name="Señal", line=dict(width=1.4, color=p["macd_senal"])), row=4, col=1)
    fig.update_layout(
        height=820,
        xaxis_rangeslider_visible=False,
        margin=dict(t=40, b=16, l=8, r=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig = _cerrar_grafico(fig)
    for nota in fig.layout.annotations:
        nota.font.color = p["texto_grafico"]
    return fig


def _hechos_tecnicos(hist: pd.DataFrame, historia_corta: bool) -> dict:
    """Estado de tendencia, medias y MACD para explicar la lectura, sin volver a puntuarla."""
    vacio = {"precio_sobre_ema": None, "medias_ordenadas": None, "precio_sobre_medias": None, "macd_estado": None}
    if historia_corta or hist is None or len(hist) < 30 or "Close" not in hist.columns:
        return vacio
    close = hist["Close"].astype(float)
    precio = float(close.iloc[-1])
    if not np.isfinite(precio) or precio <= 0:
        return vacio
    sma10, sma20 = sma(close, 10), sma(close, 20)
    ema200 = ema(close, 200)
    macd_line, macd_signal, _ = macd(close)
    ema_hoy = ema200.iloc[-1]
    media10, media20 = sma10.iloc[-1], sma20.iloc[-1]
    linea, senal = float(macd_line.iloc[-1]), float(macd_signal.iloc[-1])
    previa = float(macd_line.iloc[-2])
    if linea > senal:
        estado = "arriba"
    elif linea < senal and linea > previa:
        estado = "girando"
    else:
        estado = "abajo"
    return {
        "precio_sobre_ema": bool(pd.notna(ema_hoy) and precio > float(ema_hoy)),
        "medias_ordenadas": bool(pd.notna(media10) and pd.notna(media20) and float(media10) > float(media20)),
        "precio_sobre_medias": bool(
            pd.notna(media10) and pd.notna(media20) and precio > float(media10) and precio > float(media20)
        ),
        "macd_estado": estado,
    }


def _bloque_analisis_global(fila: pd.Series, ficha: dict, hist: pd.DataFrame) -> None:
    import html

    hechos = _hechos_tecnicos(hist, bool(fila.get("historia_corta")))
    nombre = None
    clave = str(ficha.get("recomendacion") or "").lower()
    if clave:
        nombre = TRADUCCION_CONSENSO.get(clave, clave.replace("_", " "))
    analisis = armar_analisis_global(
        lectura=str(fila["lectura"]),
        rsi=fila.get("rsi14"),
        stage2=bool(fila.get("stage2")),
        precio_sobre_ema=hechos["precio_sobre_ema"],
        medias_ordenadas=hechos["medias_ordenadas"],
        precio_sobre_medias=hechos["precio_sobre_medias"],
        macd_estado=hechos["macd_estado"],
        per=ficha.get("per"),
        precio=fila.get("precio_usd"),
        objetivo=ficha.get("objetivo"),
        consenso_media=ficha.get("puntaje"),
        consenso_nombre=nombre,
        margen=ficha.get("margen"),
        roe=ficha.get("roe"),
        historia_corta=bool(fila.get("historia_corta")),
    )
    p = paleta()
    if analisis["sesgo"] == "Alcista":
        fondo = p["lectura_alcista_fuerte_bg"]
    elif analisis["sesgo"] == "Bajista":
        fondo = p["lectura_bajista_fuerte_bg"]
    else:
        fondo = p["lectura_observacion_bg"]
    filas = []
    for item in analisis["tecnicos"]:
        filas.append(
            "<div class='zeta-comp'>"
            f"<span class='zeta-comp-titulo'>{html.escape(item['titulo'])}</span>"
            f"<span>{html.escape(item['texto'])}</span>"
            "</div>"
        )
    for item in analisis["fundamentales"]:
        puntos = item["puntos"]
        color = p["variacion_pos"] if puntos > 0 else p["variacion_neg"] if puntos < 0 else p["mute"]
        signo = f"+{puntos}" if puntos > 0 else f"−{abs(puntos)}" if puntos < 0 else "0"
        filas.append(
            "<div class='zeta-comp'>"
            f"<span class='zeta-comp-titulo'>{html.escape(item['titulo'])}</span>"
            f"<span class='zeta-comp-puntos' style='color:{color}'>{signo}</span>"
            f"<span>{html.escape(item['texto'])}</span>"
            "</div>"
        )
    tecnico = analisis["tecnico"]
    fundamental = analisis["fundamental"]
    combinado = analisis["combinado"]
    nota_tope = ""
    if analisis["recortado"]:
        bruto = analisis["fundamental_bruto"]
        signo_bruto = f"+{bruto}" if bruto > 0 else f"−{abs(bruto)}"
        signo_tope = f"+{fundamental}" if fundamental > 0 else f"−{abs(fundamental)}" if fundamental < 0 else "0"
        nota_tope = (
            f"<p class='zeta-intro'>La suma de valuación, consenso y márgenes era {signo_bruto}. "
            f"El tope la deja en {signo_tope}.</p>"
        )
    st.markdown(
        f"""
        <div class="zeta-global">
          <div class="zeta-global-top">
            <div>
              <div class="zeta-kicker">Análisis global</div>
              <span class="zeta-sesgo" style="background:{fondo};color:{p["texto"]}">{html.escape(analisis["sesgo"])}</span>
            </div>
            <div class="zeta-score">
              <div class="zeta-score-num">{'+' if combinado > 0 else '−' if combinado < 0 else ''}{abs(combinado)}</div>
              <div class="zeta-score-label">Puntaje combinado · técnico {'+' if tecnico > 0 else '−' if tecnico < 0 else ''}{abs(tecnico)} · fundamental {'+' if fundamental > 0 else '−' if fundamental < 0 else ''}{abs(fundamental)}</div>
            </div>
          </div>
          <p class="zeta-intro">{html.escape(analisis["intro"])}</p>
          <p class="zeta-frase"><strong>{html.escape(analisis["frase"])}</strong></p>
          <div class="zeta-grupo">Técnico</div>
          {''.join(filas[:4])}
          <div class="zeta-grupo">Fundamental</div>
          {nota_tope}
          {''.join(filas[4:])}
          <p class="zeta-legal">{html.escape(analisis["aviso"])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
                    "bar": {"color": paleta()["barra_gauge"], "thickness": 0.28},
                    "steps": [
                        {"range": [1, 1.8], "color": paleta()["pasos_gauge"][0]},
                        {"range": [1.8, 2.6], "color": paleta()["pasos_gauge"][1]},
                        {"range": [2.6, 3.4], "color": paleta()["pasos_gauge"][2]},
                        {"range": [3.4, 4.2], "color": paleta()["pasos_gauge"][3]},
                        {"range": [4.2, 5], "color": paleta()["pasos_gauge"][4]},
                    ],
                },
            )
        )
        fig.update_layout(height=280, margin=dict(t=50, b=8, l=24, r=24))
        _cerrar_grafico(fig)
        st.plotly_chart(fig, width="stretch", theme=None, key=f"gauge_consenso_{tema_activo()}")


def vista_activo() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    df = panel["filas"]
    if df.empty:
        st.info("No hay activos con señal para abrir la ficha.")
        return
    opciones = df.sort_values("ticker")["ticker"].tolist()
    configs = panel.get("configs") or WATCHLIST
    ticker = st.selectbox(
        "Activo",
        opciones,
        format_func=lambda clave: f"{clave} — {configs.get(clave, {}).get('name', clave)}",
    )
    fila = df.loc[df["ticker"] == ticker].iloc[0]
    hist = panel["historicos"][ticker]
    aviso_datos(panel, extra="Precio y gráfico de este activo")
    with st.spinner("Consultando consenso y calendario…"):
        ficha = ficha_activo(configs[ticker]["underlying"], clave_cierre())
    if ficha.get("obtenido_en"):
        aviso_datos(
            {"obtenido_en": ficha["obtenido_en"]},
            extra="Consenso y calendario de este activo",
            precios=False,
        )

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

    _bloque_analisis_global(fila, ficha, hist)
    _consenso(ficha, float(fila["precio_usd"]), fila["lectura"])

    a, b, c, d = st.columns(4)
    a.metric("RSI 14", f"{fila['rsi14']:.2f}")
    b.metric("Volumen relativo", f"{fila['vol_relativo']:.1f}%")
    c.metric("Stage 2", "Alineada" if fila["stage2"] else "No alineada")
    d.metric("Gap vs CCL", "N/D" if fila["gap_ccl"] is None or pd.isna(fila["gap_ccl"]) else f"{fila['gap_ccl']:+.2f}%")

    st.plotly_chart(_grafico(fila, hist), width="stretch", theme=None, key=f"grafico_{ticker}_{tema_activo()}")

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
    configs = panel.get("configs") or WATCHLIST
    for clave, cfg in configs.items():
        simbolo = cfg["underlying"]
        if simbolo in precios.columns:
            columnas[clave] = precios[simbolo]
    if "SPY" in precios.columns and "SPY" not in columnas:
        columnas["SPY"] = precios["SPY"]
    return calcular_rrg(pd.DataFrame(columnas).sort_index())


def _grafico_radar(df: pd.DataFrame) -> go.Figure:
    """Dispersión ancha. La escala inicial usa los percentiles 2–98 para abrir el centro."""
    p = paleta()
    x0, x1 = rango_ejes(df["Fuerza_X"])
    y0, y1 = rango_ejes(df["Momentum_Y"])
    dentro = df[
        df["Fuerza_X"].between(x0, x1) & df["Momentum_Y"].between(y0, y1)
    ]
    if dentro.empty:
        dentro = df
    etiquetar: list[tuple[str, float, float]] = []
    for _, bloque in dentro.groupby("Cuadrante"):
        distancia = bloque["Fuerza_X"].abs() + bloque["Momentum_Y"].abs()
        for fila in bloque.loc[distancia.nlargest(2).index].itertuples(index=False):
            etiquetar.append((str(fila.Ticker), float(fila.Fuerza_X), float(fila.Momentum_Y)))

    fig = px.scatter(
        df,
        x="Fuerza_X",
        y="Momentum_Y",
        color="Cuadrante",
        hover_name="Ticker",
        custom_data=["Cuadrante"],
        color_discrete_map=_colores_cuadrante(),
        category_orders={"Cuadrante": list(_colores_cuadrante().keys())},
        labels={"Fuerza_X": "Fuerza relativa", "Momentum_Y": "Momentum"},
    )
    for xa, xb, ya, yb, color in (
        (0, x1, 0, y1, p["tint_lider"]),
        (x0, 0, 0, y1, p["tint_mejorando"]),
        (0, x1, y0, 0, p["tint_debilitando"]),
        (x0, 0, y0, 0, p["tint_rezagado"]),
    ):
        fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=color, line_width=0, layer="below")
    fig.add_hline(y=0, line_dash="dash", line_width=1, line_color=p["cruce"])
    fig.add_vline(x=0, line_dash="dash", line_width=1, line_color=p["cruce"])
    inset_x = (x1 - x0) * 0.015
    inset_y = (y1 - y0) * 0.02
    for x, y, texto, ancla_x, ancla_y, color in (
        (x1 - inset_x, y1 - inset_y, "LÍDERES", "right", "top", p["esquina_lider"]),
        (x0 + inset_x, y1 - inset_y, "MEJORANDO", "left", "top", p["esquina_mejorando"]),
        (x1 - inset_x, y0 + inset_y, "DEBILITÁNDOSE", "right", "bottom", p["esquina_debilitando"]),
        (x0 + inset_x, y0 + inset_y, "REZAGADOS", "left", "bottom", p["esquina_rezagado"]),
    ):
        fig.add_annotation(
            x=x,
            y=y,
            text=texto,
            showarrow=False,
            xanchor=ancla_x,
            yanchor=ancla_y,
            font=dict(color=color, size=12, family=p["fuente_mono"]),
        )
    for ticker, (lx, ly) in ubicar_etiquetas(etiquetar, x0, x1, y0, y1).items():
        fig.add_annotation(
            x=lx,
            y=ly,
            text=ticker,
            showarrow=False,
            font=dict(color=p["etiqueta"], size=12, family=p["fuente_mono"]),
        )
    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>%{customdata[0]}"
            "<br>Fuerza %{x:.2f}<br>Momentum %{y:.2f}<extra></extra>"
        ),
        marker=dict(size=8, opacity=0.92, line=dict(width=1.5, color=p["aro"])),
        cliponaxis=True,
    )
    fig.update_layout(
        height=840,
        margin=dict(t=108, b=56, l=64, r=28),
        legend_title_text="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="closest",
        dragmode="pan",
        xaxis=dict(range=[x0, x1], fixedrange=False, showgrid=False),
        yaxis=dict(range=[y0, y1], fixedrange=False, showgrid=False),
    )
    fig = _cerrar_grafico(fig)
    _titulo_horizonte(fig, HORIZONTE_RADAR)
    fig.update_layout(dragmode="pan")
    fig.update_xaxes(range=[x0, x1], fixedrange=False)
    fig.update_yaxes(range=[y0, y1], fixedrange=False)
    return fig


def vista_radar() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    st.markdown("### Radar de fuerza relativa")
    st.caption(HORIZONTE_RADAR)
    aviso_datos(panel)
    st.info(NOTA_RADAR_Y_ROTACION)
    st.caption(
        "Cada punto compara el subyacente contra SPY. "
        "La fuerza es el z-score de 50 ruedas del ratio de precios y el momentum es su cambio a 10 ruedas. "
        "La escala inicial usa los percentiles 2 y 98, con margen, para que el centro no quede apretado. "
        "Arrastrá para mover y usá la rueda del mouse para acercar o alejar. "
        "Solo se etiquetan las dos siglas más alejadas de cada cuadrante; el resto aparece al pasar el mouse."
    )
    df = _rrg_de_panel(panel)
    if df.empty:
        st.error("No alcanzó la historia para armar el radar. Recargá en unos minutos.")
        return

    st.plotly_chart(
        _grafico_radar(df),
        width="stretch",
        theme=None,
        key=f"radar_rrg_{tema_activo()}",
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )
    st.markdown("**Activos con fuerza relativa**")
    st.caption("Líderes y Mejorando, ordenados por momentum.")
    destacados = df[df["Cuadrante"].isin(["Líderes", "Mejorando"])].sort_values("Momentum_Y", ascending=False).head(10)
    if destacados.empty:
        st.info("Ningún activo en Líderes o Mejorando.")
    else:
        nombres = " · ".join(f"**{fila.Ticker}** ({fila.Cuadrante})" for fila in destacados.itertuples(index=False))
        st.markdown(nombres)

    cuadrante = st.selectbox("Ver cuadrante", ["Todos", *_colores_cuadrante().keys()])
    tabla = df if cuadrante == "Todos" else df[df["Cuadrante"] == cuadrante]
    mostrar_tabla(
        tabla.sort_values(["Cuadrante", "Momentum_Y"], ascending=[True, False]),
        alto=360,
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


def _grafico_rotacion(
    colas: pd.DataFrame,
    benchmark: str = "SPY",
    marcas: list[dict] | None = None,
) -> go.Figure:
    """RRG oscuro, centrado en 0. El 0 es la fuerza 100 y el momentum 100."""
    fig = go.Figure()
    series = []
    for ticker, grupo in colas.groupby("Ticker", sort=False):
        grupo = grupo.sort_values("Orden")
        fuerza = float(grupo["Fuerza"].iloc[-1])
        momentum = float(grupo["Momentum"].iloc[-1])
        nombre_cuad = cuadrante(fuerza, momentum)
        series.append(
            {
                "ticker": ticker,
                "nombre": str(grupo["Nombre"].iloc[0]),
                "x": grupo["Fuerza"].astype(float) - 100.0,
                "y": grupo["Momentum"].astype(float) - 100.0,
                "fuerza": fuerza,
                "momentum": momentum,
                "cuadrante": nombre_cuad,
                "color": _color_cola(nombre_cuad),
            }
        )

    xs = np.concatenate([s["x"].to_numpy() for s in series])
    ys = np.concatenate([s["y"].to_numpy() for s in series])
    alcance_x = max(float(np.max(np.abs(xs))), 1.4)
    alcance_y = max(float(np.max(np.abs(ys))), 1.4)
    x0, x1 = -alcance_x * 1.38, alcance_x * 1.38
    y0, y1 = -alcance_y * 1.42, alcance_y * 1.42

    p = paleta()
    for xa, xb, ya, yb, color in (
        (0, x1, 0, y1, p["tint_lider"]),
        (x0, 0, 0, y1, p["tint_mejorando"]),
        (0, x1, y0, 0, p["tint_debilitando"]),
        (x0, 0, y0, 0, p["tint_rezagado"]),
    ):
        fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=color, line_width=0, layer="below")
    fig.add_hline(y=0, line_dash="dash", line_width=1, line_color=p["cruce"])
    fig.add_vline(x=0, line_dash="dash", line_width=1, line_color=p["cruce"])

    cabezas = []
    for serie in series:
        color = serie["color"]
        n = len(serie["x"])
        fig.add_trace(
            go.Scatter(
                x=serie["x"],
                y=serie["y"],
                mode="lines",
                line=dict(color=color, width=2.4, shape="spline" if n >= 4 else "linear"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        hx, hy = float(serie["x"].iloc[-1]), float(serie["y"].iloc[-1])
        cabezas.append((serie["ticker"], hx, hy))
        fig.add_trace(
            go.Scatter(
                x=[hx],
                y=[hy],
                mode="markers",
                marker=dict(size=26, color=color, opacity=0.28, line=dict(width=0)),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[hx],
                y=[hy],
                mode="markers",
                marker=dict(size=12, color=color, line=dict(width=2, color=p["aro"])),
                name=serie["ticker"],
                hovertemplate=(
                    f"{serie['ticker']} · {serie['nombre']}<br>"
                    f"{serie['cuadrante']}<br>"
                    f"Fuerza {serie['fuerza']:.1f}<br>"
                    f"Momentum {serie['momentum']:.1f}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if marcas:
        puestos = {ticker: (x, y) for ticker, x, y in cabezas}
        for marca in marcas:
            puesto = puestos.get(marca.get("ticker"))
            if puesto is None:
                continue
            compra = "compra" in str(marca.get("senal") or "").lower()
            coincide = marca.get("relacion") == "coincide"
            fig.add_trace(
                go.Scatter(
                    x=[puesto[0]],
                    y=[puesto[1]],
                    mode="markers",
                    name=str(marca.get("senal") or "Señal"),
                    marker=dict(
                        size=22,
                        symbol="diamond" if compra else "x",
                        color="#1e7f4f" if compra else "#a32020",
                        line=dict(width=3, color="#1e7f4f" if coincide else "#a32020"),
                    ),
                    hovertemplate=(
                        f"{marca.get('ticker')} · {marca.get('senal')}"
                        f"<br>{marca.get('cuadrante') or 'Sin cuadrante'}"
                        f"<br>{'Coincide' if coincide else 'Se contradice'}<extra></extra>"
                    ),
                    showlegend=False,
                )
            )

    for ticker, (lx, ly) in ubicar_etiquetas(cabezas, x0, x1, y0, y1).items():
        fig.add_annotation(
            x=lx,
            y=ly,
            text=ticker,
            showarrow=False,
            xanchor="center",
            yanchor="middle",
            font=dict(family=p["fuente_mono"], size=13, color=p["etiqueta"]),
        )

    for x, y, texto, ancla_x, ancla_y, color in (
        (0.985, 0.975, "LÍDERES", "right", "top", p["esquina_lider"]),
        (0.015, 0.975, "MEJORANDO", "left", "top", p["esquina_mejorando"]),
        (0.985, 0.03, "DEBILITÁNDOSE", "right", "bottom", p["esquina_debilitando"]),
        (0.015, 0.03, "REZAGADOS", "left", "bottom", p["esquina_rezagado"]),
    ):
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=x,
            y=y,
            text=texto,
            showarrow=False,
            xanchor=ancla_x,
            yanchor=ancla_y,
            font=dict(family=p["fuente_mono"], size=11, color=color),
        )
    for x, ancla, texto in (
        (0, "left", f"◂ MÁS DÉBIL QUE {benchmark}"),
        (1, "right", f"MÁS FUERTE QUE {benchmark} ▸"),
    ):
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=x,
            y=-0.14,
            text=texto,
            showarrow=False,
            xanchor=ancla,
            font=dict(family=p["fuente_mono"], size=11, color=p["mute_grafico"]),
        )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=-0.045,
        y=1.02,
        text="ACELERA ▸",
        showarrow=False,
        xanchor="right",
        font=dict(family=p["fuente_mono"], size=11, color=p["mute_grafico"]),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=-0.045,
        y=-0.02,
        text="◂ FRENA",
        showarrow=False,
        xanchor="right",
        font=dict(family=p["fuente_mono"], size=11, color=p["mute_grafico"]),
    )
    _cerrar_grafico(fig)
    _titulo_horizonte(fig, HORIZONTE_ROTACION)
    fig.update_layout(
        height=720,
        margin=dict(t=96, b=72, l=78, r=28),
        showlegend=False,
        xaxis=dict(
            title=dict(text=f"FUERZA RELATIVA vs {benchmark}", font=dict(family=p["fuente_mono"], size=12, color=p["titulo_eje"])),
            range=[x0, x1],
            showgrid=False,
            zeroline=False,
            tickfont=dict(family=p["fuente_mono"], size=11, color=p["mute_grafico"]),
        ),
        yaxis=dict(
            title=dict(text="MOMENTUM DE LA FUERZA RELATIVA", font=dict(family=p["fuente_mono"], size=12, color=p["titulo_eje"])),
            range=[y0, y1],
            showgrid=False,
            zeroline=False,
            tickfont=dict(family=p["fuente_mono"], size=11, color=p["mute_grafico"]),
        ),
    )
    return fig


def vista_rotacion() -> None:
    panel = panel_o_aviso()
    if panel is None:
        return
    st.markdown("### Rotación sectorial")
    st.caption(HORIZONTE_ROTACION)
    aviso_datos(panel)
    st.info(NOTA_RADAR_Y_ROTACION)
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
        st.plotly_chart(_grafico_rotacion(colas), width="stretch", theme=None, key=f"rotacion_rrg_{tema_activo()}")
        st.caption(
            "El centro es cero: a la derecha hay más fuerza contra SPY que el promedio de seis meses, y arriba esa fuerza se acelera. "
            "La cola son las últimas cinco semanas. Verde Líderes, azul Mejorando, ámbar Debilitándose, rojo Rezagados."
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
        mostrar_tabla(_tabla_ranking(sectores), alto=460)
        if not indices.empty:
            st.markdown("Índices")
            mostrar_tabla(_tabla_ranking(indices), alto=280)

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
    mostrar_tabla(pd.DataFrame(mapa), alto=480)
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
        color_discrete_sequence=list(paleta()["torta"]),
    )
    fig.update_traces(textinfo="percent", textposition="inside", sort=False, textfont_color=paleta()["texto_sobre_serie"])
    fig.update_layout(
        showlegend=True,
        margin=dict(t=8, b=8, l=8, r=8),
        height=420,
        legend=dict(font=dict(size=12)),
    )
    return _cerrar_grafico(fig)


def _bloque_cartera(clave: str, precios: pd.DataFrame, panel: dict) -> None:
    perfil = PERFILES[clave]
    tabla = composicion(clave)
    st.markdown(f"**{perfil['titulo']}**")
    aviso_datos(panel)
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
        st.caption(
            f"Período {stats['inicio']:%d/%m/%Y} – {stats['fin']:%d/%m/%Y} "
            f"({stats['sesiones']} ruedas de USD). QuantStats, sobre el bloque de renta variable, "
            "pesos constantes y rebalanceo diario implícito, con los precios de la descarga de arriba. "
            f"Sharpe {stats['sharpe']:.2f} · Sortino {stats['sortino']:.2f}. "
            "Es una descripción de lo que pasó, no un rendimiento esperado ni una promesa."
        )
        if stats["faltantes"]:
            st.caption("Sin serie y fuera del cálculo: " + ", ".join(stats["faltantes"]) + ".")

    grafico, detalle = st.columns([1.15, 1])
    with grafico:
        st.plotly_chart(_torta(tabla), width="stretch", theme=None, key=f"torta_{clave}_{tema_activo()}")
    with detalle:
        vista = tabla.copy()
        vista["Porcentaje"] = vista["Porcentaje"].map(lambda v: f"{v:.1f}%")
        mostrar_tabla(vista, alto=480)
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
        _bloque_cartera("conservador", panel["precios_usd"], panel)
    with agresiva:
        _bloque_cartera("agresivo", panel["precios_usd"], panel)


def vista_metodologia() -> None:
    st.markdown("### Cómo está armada la lectura")
    st.markdown(
        f"""
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

**Análisis global.** En la ficha de cada activo, la lectura técnica cerrada aporta +3 si es alcista,
0 si quedó neutral o en observación, y −3 si es bajista. El fundamental suma la valuación (resta 1 si el PER
pasa de 30), el consenso (el precio objetivo suma 1 si está más de 15% arriba y resta 1 si está abajo; si no
hay objetivo, se mira el promedio de las firmas) y el margen neto (suma 1 por encima de 15% y resta 1 si es
negativo). Esa suma fundamental se corta en ±2. El puntaje combinado es alcista desde +3 y bajista desde −3.
En el medio el sesgo global es neutral. Son ideas de análisis, no una recomendación de inversión.

**Stage 2** significa precio sobre la EMA 200 y esa media subiendo contra 20 ruedas atrás.
Si el subyacente tiene menos de 210 ruedas (hoy, SpaceX), entra igual al monitor como **Historia corta**,
con precio y gap, pero sin sesgo de medias.

**Gap vs CCL** compara el dólar implícito de cada CEDEAR con la mediana de varios pares
con ratio verificado: `(precio ARS × ratio) / precio USD`. No sale de un solo ticker.
Los ratios y los símbolos se revisaron contra data912 y contra Yahoo el 28/10/2026.
Bank of America en pesos es `BA.C` en BYMA y `BA-C.BA` en Yahoo (el símbolo `BAC.BA` es otra especie).
Bunge es `BNG` en BYMA y `BNG.BA` en Yahoo: `BG.BA` no existe. El ratio 5 cierra contra el CCL.
3M usa `MMM.BA`, Constellation usa `CEG.BA`, Halliburton figura como `HAL`,
Morgan Stanley usa ratio 41, Japón (`EWJ`) ratio 14 y comunicaciones (`XLC`) ratio 19.

**Contraste.** El precio en vivo es el de data912. Se lo compara con Yahoo `.BA`.
Verde si difieren menos de 0,5%, amarillo hasta 2% y rojo si pasan de 2% o si el dato
tiene más de 30 minutos con el mercado abierto. En rojo no se calcula la señal de ese activo.
data912 no manda la hora de la operación: esos 30 minutos se cuentan desde que el panel
leyó el feed, y el feed se vuelve a pedir al minuto. El MEP, el CCL, el oficial y el riesgo
país se publican una vez por día: ahí se mira la diferencia de valor, no el reloj.
El MEP y el CCL se contrastan con ArgentinaDatos, el mayorista de referencia con el BCRA
y el riesgo país de Ámbito con ArgentinaDatos. Los desvíos quedan en un CSV del día.
Un CEDEAR cuyo ratio no se puede verificar figura como «Sin verificar» y no entra al CCL ni al gap.

**Radar ({HORIZONTE_RADAR}).** Fuerza relativa contra SPY, normalizada a 50 ruedas, y su cambio a 10 ruedas.
Arriba a la derecha: Líderes. Arriba a la izquierda: Mejorando. Abajo a la derecha: Debilitándose.
Abajo a la izquierda: Rezagados. La escala de entrada deja afuera el 2% de cada punta para que
el centro se lea; la rueda acerca y aleja, y arrastrar mueve el gráfico.

**Rotación sectorial ({HORIZONTE_ROTACION}).** Otra cuenta, sobre los ETF de sector (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC)
y los índices QQQ, IWM, EEM, EWZ y ARGT, siempre contra SPY. La fuerza es el ratio de precios suavizado,
puesto en 100 contra su promedio de unos seis meses. El momentum compara esa fuerza con la de diez ruedas atrás.
En el gráfico el centro es cero (ese 100). La cola son las últimas cinco semanas, pintada según el cuadrante
de hoy: verde Líderes, azul Mejorando, ámbar Debilitándose, rojo Rezagados. Las flechas de 1 semana, 1 mes
y 3 meses dicen si el exceso contra SPY de esa ventana mejoró o empeoró contra la ventana anterior del mismo largo.
El listado de CEDEARs es el recorte de este panel, no la cartera completa del ETF.

{NOTA_RADAR_Y_ROTACION}

**Carteras modelo.** Los pesos de renta fija se respetan. Las métricas (rendimiento compuesto,
volatilidad anualizada, caída máxima, VaR 95% diario, Sharpe y Sortino) las calcula QuantStats
sobre el bloque de renta variable, con los precios de Yahoo, en la moneda del subyacente.
No incluyen las obligaciones negociables. No son un pronóstico.

La historia sale de Yahoo Finance en una descarga agrupada. El precio en vivo de BYMA sale de data912.
El sello
«Datos actualizados» es la hora de Argentina en que esa descarga respondió, guardada con la caché:
abrir otra sección no la cambia. **Actualizar datos** borra la caché y vuelve a pedir los precios.
La rueda de CEDEARs figura abierta de lunes a viernes, de 11:00 a 17:00, hora de Argentina
(horario habitual, sin feriados). Yahoo no es tiempo real: los precios traen una demora de unos 15 minutos.
El consenso de analistas y el calendario se piden solo cuando se abre un activo, y llevan su propio sello.
        """
    )
    st.markdown("### Contacto")
    mostrar_enlaces(en_fila=True)
