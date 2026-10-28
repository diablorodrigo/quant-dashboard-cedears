"""Acciones argentinas: panel líder, panel general, mapa y rotación contra el Merval.

Los precios en vivo salen de data912. La historia sale de Yahoo. El rubro
verificado está en ``data/acciones_ar.csv``; si no se pudo verificar, el
papel queda en «Sin clasificar» y no entra al mapa ni a la rotación.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from zeta.contraste import ROJO, contrastar_cotizacion
from zeta.rotacion import _fila_ranking, cola_reciente, curvas_rrg, frase_rotacion
from zeta.universo import ESTADO_OK, yahoo_cedear

# Nombres líquidos de siempre. No sale del volumen de una sola rueda:
# a la apertura ese número miente.
PANEL_LIDER = (
    "GGAL", "YPFD", "SUPV", "PAMP", "VALO", "BMA", "LOMA", "BBAR",
    "TGSU2", "BYMA", "EDN", "TGNO4", "COME", "TXAR", "TECO2", "METR",
    "TRAN", "ALUA", "CEPU", "CRES", "IRSA", "ECOG",
)


def es_lider(simbolo: str) -> bool:
    return simbolo in PANEL_LIDER


def variacion_ruedas(serie: pd.Series, ruedas: int) -> float | None:
    limpia = serie.dropna().astype(float)
    if len(limpia) <= ruedas:
        return None
    base = float(limpia.iloc[-1 - ruedas])
    if base <= 0:
        return None
    return float(limpia.iloc[-1]) / base - 1


def indice_equitativo(precios: pd.DataFrame) -> pd.Series:
    """Índice en base 1, promedio simple de los retornos diarios del grupo."""
    if precios is None or precios.empty:
        return pd.Series(dtype=float)
    retornos = precios.astype(float).pct_change(fill_method=None).mean(axis=1, skipna=True)
    return (1 + retornos.fillna(0)).cumprod()


def armar_rotacion_merval(indices: dict[str, pd.Series], merval: pd.Series) -> dict:
    """Misma cuenta que la rotación de CEDEARs, con el Merval en lugar del SPY."""
    vacio = {"colas": pd.DataFrame(), "ranking": pd.DataFrame(), "frase": frase_rotacion(pd.DataFrame()), "sin_datos": []}
    if merval is None or merval.dropna().empty or not indices:
        return vacio
    filas = []
    colas = []
    sin_datos = []
    for nombre, serie in indices.items():
        if serie is None or serie.dropna().empty:
            sin_datos.append(nombre)
            continue
        curva = curvas_rrg(serie.astype(float), merval.astype(float))
        fila = _fila_ranking(nombre, nombre, "Sector", serie.astype(float), merval.astype(float), curva)
        if fila is None:
            sin_datos.append(nombre)
            continue
        filas.append(fila)
        nodos = cola_reciente(curva)
        for orden, (fecha, nodo) in enumerate(nodos.iterrows()):
            colas.append(
                {
                    "Ticker": nombre,
                    "Nombre": nombre,
                    "Fecha": fecha,
                    "Fuerza": float(nodo["fuerza"]),
                    "Momentum": float(nodo["momentum"]),
                    "Orden": orden,
                    "Ultimo": orden == len(nodos) - 1,
                }
            )
    ranking = pd.DataFrame(filas)
    return {
        "colas": pd.DataFrame(colas),
        "ranking": ranking,
        "frase": frase_rotacion(ranking),
        "sin_datos": sin_datos,
    }


def filas_acciones(
    cotizaciones: dict[str, dict],
    manual: dict[str, dict],
    yahoo: dict[str, float],
    *,
    yahoo_es_hoy: dict[str, bool],
    edad_minutos: float | None,
    mercado_abierto: bool,
) -> list[dict]:
    """Una fila por acción del feed. El contraste rojo no saca el precio: saca el mapa."""
    filas = []
    for simbolo, quote in sorted(cotizaciones.items()):
        cfg = manual.get(simbolo, {})
        precio = quote.get("c")
        try:
            precio_f = float(precio) if precio is not None else None
        except (TypeError, ValueError):
            precio_f = None
        precio_yahoo = yahoo.get(simbolo)
        if precio_f is None:
            lectura = {"estado": "amarillo", "motivo": "Sin precio en data912.", "bloquea_senal": False, "diferencia": None}
        else:
            lectura = contrastar_cotizacion(
                precio_vivo=precio_f,
                variacion_pct=quote.get("pct_change"),
                precio_yahoo=precio_yahoo,
                yahoo_es_hoy=bool(yahoo_es_hoy.get(simbolo)),
                edad_minutos=edad_minutos,
                mercado_abierto=mercado_abierto,
            )
        volumen = quote.get("v")
        try:
            volumen_f = float(volumen) if volumen is not None else None
        except (TypeError, ValueError):
            volumen_f = None
        monto = None
        if precio_f and volumen_f:
            monto = precio_f * volumen_f
        rubro = cfg.get("rubro") or "Sin clasificar"
        sector_ok = cfg.get("sector_estado") == ESTADO_OK and rubro not in ("Sin clasificar", "Sin verificar", "")
        filas.append(
            {
                "ticker": simbolo,
                "nombre": cfg.get("name") or simbolo,
                "rubro": rubro,
                "panel": cfg.get("panel") or ("lider" if es_lider(simbolo) else "general"),
                "precio": precio_f,
                "variacion": quote.get("pct_change"),
                "volumen": volumen_f,
                "monto": monto,
                "contraste": lectura.get("estado"),
                "motivo": lectura.get("motivo") or "",
                "entra_mapa": sector_ok and lectura.get("estado") != ROJO and precio_f is not None,
                "sector_ok": sector_ok,
            }
        )
    return filas


def variaciones_historia(cierres: pd.DataFrame, ruedas: int) -> dict[str, float]:
    salida = {}
    if cierres is None or cierres.empty:
        return salida
    for columna in cierres.columns:
        valor = variacion_ruedas(cierres[columna], ruedas)
        if valor is not None:
            salida[str(columna)] = valor
    return salida


def indices_por_rubro(cierres: pd.DataFrame, filas: list[dict]) -> dict[str, pd.Series]:
    """Un índice por rubro, solo con acciones que entran al cálculo."""
    grupos: dict[str, list[str]] = {}
    for fila in filas:
        if not fila.get("entra_mapa"):
            continue
        if fila["ticker"] not in cierres.columns:
            continue
        grupos.setdefault(fila["rubro"], []).append(fila["ticker"])
    indices = {}
    for rubro, tickers in grupos.items():
        if len(tickers) < 2:
            continue
        indices[rubro] = indice_equitativo(cierres[tickers])
    return indices


def simbolos_yahoo(simbolos: list[str]) -> dict[str, str]:
    """Símbolo BYMA → ticker de Yahoo en Buenos Aires."""
    return {simbolo: yahoo_cedear(simbolo) for simbolo in simbolos}


def vista_acciones_argentinas() -> None:
    import streamlit as st

    from zeta.datos import descargar_simbolos
    from zeta.fuentes import cotizaciones_acciones, edad_cache
    from zeta.marca import aviso
    from zeta.tiempo import ahora_art, mercado_cedears_abierto
    from zeta.universo import cargar_acciones
    from zeta.vistas import _cerrar_grafico, _estilo_variacion, _grafico_rotacion, _tabla_ranking, mostrar_tabla

    st.markdown("### Acciones argentinas")
    st.caption(
        "Precios en vivo de data912, contrastados con Yahoo. "
        "El panel líder es la lista de nombres líquidos que mantenemos a mano: "
        "no se arma con el volumen de una sola rueda, porque antes de las 11 ese número no dice nada. "
        "No es asesoramiento de inversión."
    )
    aviso()

    with st.spinner("Buscando cotizaciones de acciones…"):
        vivos = cotizaciones_acciones() or {}
        manual = cargar_acciones()
        historia = _historia_acciones()
    if not vivos:
        st.error("data912 no respondió con el panel de acciones. No se muestran precios inventados.")
        return

    momento = ahora_art()
    hoy = pd.Timestamp(momento.date())
    yahoo_px = {}
    yahoo_hoy = {}
    cierres = historia.get("cierres")
    if isinstance(cierres, pd.DataFrame) and not cierres.empty:
        for simbolo in cierres.columns:
            serie = cierres[simbolo].dropna()
            if serie.empty:
                continue
            yahoo_px[str(simbolo)] = float(serie.iloc[-1])
            yahoo_hoy[str(simbolo)] = pd.Timestamp(serie.index[-1]).normalize() == hoy

    filas = filas_acciones(
        vivos,
        manual,
        yahoo_px,
        yahoo_es_hoy=yahoo_hoy,
        edad_minutos=edad_cache("acciones"),
        mercado_abierto=mercado_cedears_abierto(momento),
    )
    rojos = [fila for fila in filas if fila["contraste"] == ROJO]
    if rojos:
        nombres = ", ".join(fila["ticker"] for fila in rojos[:12])
        st.error(
            f"{len(rojos)} acciones con contraste en rojo ({nombres}). "
            "Esas no entran al mapa ni a la rotación."
        )

    lider = [fila for fila in filas if fila["panel"] == "lider"]
    general = [fila for fila in filas if fila["panel"] != "lider"]
    tab_lider, tab_general = st.tabs([f"Panel líder ({len(lider)})", f"Panel general ({len(general)})"])
    with tab_lider:
        _tabla_acciones(lider, mostrar_tabla, _estilo_variacion)
    with tab_general:
        st.caption("El panel general tiene menos liquidez. El precio está, el análisis pide más cuidado.")
        _tabla_acciones(general, mostrar_tabla, _estilo_variacion)

    st.divider()
    st.markdown("### Mapa de calor por rubro")
    plazo = st.radio("Variación:", ["Día", "Semana", "Mes"], horizontal=True, key="plazo_mapa_ar")
    incluir = st.checkbox("Incluir el panel general", value=False)
    base = filas if incluir else lider
    _mapa(base, cierres, plazo, _cerrar_grafico)

    st.divider()
    st.markdown("### Rotación contra el Merval")
    st.caption(
        "Cada rubro es un índice equitativo de las acciones que tienen rubro verificado y contraste que no está en rojo. "
        "Se mide contra el Merval, no contra el SPY. Es una descripción, no una instrucción de operar."
    )
    merval = historia.get("merval")
    if not isinstance(cierres, pd.DataFrame) or cierres.empty or merval is None or merval.dropna().empty:
        st.info("Sin historia suficiente de Yahoo para la rotación contra el Merval.")
        return
    indices = indices_por_rubro(cierres, [fila for fila in filas if fila.get("entra_mapa")])
    rotacion = armar_rotacion_merval(indices, merval.astype(float))
    st.markdown(f"**{rotacion['frase']}**")
    if rotacion["colas"].empty:
        st.info("No alcanzó la historia para el gráfico de rotación.")
    else:
        st.plotly_chart(
            _grafico_rotacion(rotacion["colas"], benchmark="MERVAL"),
            width="stretch",
            theme=None,
            key="rotacion_merval",
        )
    if not rotacion["ranking"].empty:
        mostrar_tabla(_tabla_ranking(rotacion["ranking"]), alto=420)
    if rotacion["sin_datos"]:
        st.caption("Sin serie suficiente: " + ", ".join(rotacion["sin_datos"]) + ".")


def _tabla_acciones(filas: list[dict], mostrar_tabla, estilo_variacion) -> None:
    import streamlit as st

    if not filas:
        st.info("Sin papeles en este panel.")
        return

    def precio(valor):
        if valor is None:
            return "—"
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def variacion(valor):
        if valor is None:
            return "—"
        return f"{float(valor):+.2f}%"

    def entero(valor):
        if valor is None:
            return "—"
        return f"{valor:,.0f}".replace(",", ".")

    vista = pd.DataFrame(
        [
            {
                "Ticker": fila["ticker"],
                "Nombre": fila["nombre"],
                "Rubro": fila["rubro"],
                "Precio ARS": precio(fila["precio"]),
                "Var. 1D": variacion(fila["variacion"]),
                "Volumen": entero(fila["volumen"]),
                "Monto": entero(None if fila["monto"] is None else fila["monto"] / 1_000_000) + " M" if fila["monto"] else "—",
                "Contraste": (fila["contraste"] or "—").capitalize(),
            }
            for fila in sorted(filas, key=lambda item: -(item["monto"] or 0))
        ]
    )
    mostrar_tabla(vista, estilos={"Var. 1D": estilo_variacion, "Contraste": _estilo_contraste}, alto=520)


def _estilo_contraste(valor: str) -> str:
    texto = (valor or "").lower()
    if texto == "verde":
        return "color: #1e7f4f; font-weight: 650;"
    if texto == "amarillo":
        return "color: #a56b12; font-weight: 650;"
    if texto == "rojo":
        return "color: #a32020; font-weight: 650;"
    return ""


def _mapa(filas: list[dict], cierres: pd.DataFrame | None, plazo: str, cerrar_grafico) -> None:
    import plotly.express as px
    import streamlit as st

    ruedas = {"Día": 1, "Semana": 5, "Mes": 21}[plazo]
    historias = variaciones_historia(cierres, ruedas) if plazo != "Día" and isinstance(cierres, pd.DataFrame) else {}
    puntos = []
    for fila in filas:
        if not fila.get("entra_mapa"):
            continue
        if plazo == "Día":
            if fila.get("variacion") is None:
                continue
            var = float(fila["variacion"])
        else:
            if fila["ticker"] not in historias:
                continue
            var = historias[fila["ticker"]] * 100
        puntos.append(
            {
                "Rubro": fila["rubro"],
                "Ticker": fila["ticker"],
                "Empresa": fila["nombre"],
                "Var": round(var, 2),
                "Monto": fila["monto"] or 1.0,
            }
        )
    if not puntos:
        st.info("Sin datos para el mapa en este plazo. Puede faltar historia o el contraste está en rojo.")
        return
    df = pd.DataFrame(puntos)
    df["Tamaño"] = df["Monto"].clip(lower=1) ** 0.5
    limite = 3.0 if ruedas == 1 else max(3.0, float(df["Var"].abs().quantile(0.9)))
    fig = px.treemap(
        df,
        path=[px.Constant("Acciones argentinas"), "Rubro", "Ticker"],
        values="Tamaño",
        color="Var",
        color_continuous_scale=["#c0392b", "#7f8c8d", "#27ae60"],
        range_color=[-limite, limite],
        custom_data=["Empresa", "Var"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]:+.2f}%",
        hovertemplate="<b>%{label}</b> %{customdata[0]}<br>Variación: %{customdata[1]:+.2f}%<extra></extra>",
    )
    fig = cerrar_grafico(fig)
    fig.update_layout(height=620, margin=dict(t=30, b=10, l=10, r=10), coloraxis_colorbar=dict(title="Var %"))
    st.plotly_chart(fig, width="stretch", key=f"mapa_ar_{ruedas}")
    fuente = "data912 (variación del día)" if plazo == "Día" else "Yahoo Finance, historia en pesos"
    st.caption(f"Color: variación en {plazo.lower()} ({fuente}). Tamaño: raíz del monto operado hoy. Entran solo rubros verificados.")


def _historia_acciones() -> dict:
    import streamlit as st

    @st.cache_data(ttl=60 * 60 * 4, show_spinner=False)
    def _bajar() -> dict:
        from zeta.datos import descargar_simbolos
        from zeta.universo import cargar_acciones

        manual = cargar_acciones()
        simbolos = list(manual)
        pares = simbolos_yahoo(simbolos)
        series, _faltan = descargar_simbolos(list(pares.values()) + ["^MERV"], "1y")
        columnas = {}
        for simbolo, yahoo in pares.items():
            historia = series.get(yahoo)
            if historia is not None and "Close" in historia.columns:
                columnas[simbolo] = historia["Close"]
        cierres = pd.DataFrame(columnas).sort_index() if columnas else pd.DataFrame()
        merval = None
        if "^MERV" in series and "Close" in series["^MERV"].columns:
            merval = series["^MERV"]["Close"].dropna()
        return {"cierres": cierres, "merval": merval}

    return _bajar()
