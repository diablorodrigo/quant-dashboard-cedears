"""Pestaña Señales. Acá, y solo acá, las etiquetas son Compra y Venta."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from zeta.estrategia import (
    AVISO_ESTRATEGIA,
    LIMITACIONES,
    MOTIVOS_SALIDA,
    NOMBRE_CUADRANTE,
    aplicar_semaforo,
    cargar_backtest,
    cargar_config,
    estado_ticker,
    filas_de_estado,
    recortar_vela_abierta,
    relacion_rrg,
    tickers_de,
    universo_por_id,
)
from zeta.contraste import contrastar_cotizacion
from zeta.fuentes import cotizaciones_cedears, edad_cache
from zeta.tiempo import ahora_art, mercado_cedears_abierto
from zeta.vistas import _estilo_variacion, _grafico_rotacion, mostrar_tabla


def _ars(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    texto = f"{float(valor):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    return f"{float(valor):+.2f}%".replace(".", ",")


def _yahoo(ticker: str) -> str:
    return str(ticker).replace(".", "-") + ".BA"


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def _historia(simbolos: tuple[str, ...], periodo: str) -> dict:
    from zeta.datos import descargar_simbolos

    series, faltan = descargar_simbolos(list(simbolos), periodo)
    return {"series": series, "faltan": faltan}


def _lecturas(historias: dict[str, pd.DataFrame], vivos: dict | None, ahora: pd.Timestamp) -> dict[str, dict]:
    lecturas = {}
    mercado = mercado_cedears_abierto(ahora)
    edad = edad_cache("cedears")
    hoy = pd.Timestamp(ahora.date())
    for ticker, df in historias.items():
        quote = (vivos or {}).get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            continue
        cierre = float(df["Close"].iloc[-1])
        fecha = pd.Timestamp(df.index[-1])
        if fecha.tzinfo is not None:
            fecha = fecha.tz_localize(None)
        if not quote or quote.get("c") is None:
            lecturas[ticker] = {
                "estado": "amarillo",
                "bloquea_senal": False,
                "motivo": "Sin cotización en data912 para contrastar.",
            }
            continue
        lecturas[ticker] = contrastar_cotizacion(
            precio_vivo=float(quote["c"]),
            variacion_pct=quote.get("pct_change"),
            precio_yahoo=cierre,
            yahoo_es_hoy=fecha.normalize() == hoy,
            edad_minutos=edad,
            mercado_abierto=mercado,
        )
    return lecturas


def _estilo_senal(valor: str) -> str:
    texto = (valor or "").lower()
    if "fuerte" in texto:
        return "color: #1e7f4f; font-weight: 700;"
    if "débil" in texto or "debil" in texto:
        return "color: #a56b12; font-weight: 650;"
    if texto == "venta":
        return "color: #a32020; font-weight: 700;"
    return ""


def _todos(cfg: dict) -> list[str]:
    vistos: list[str] = []
    for universo in cfg.get("universos") or []:
        for ticker in universo.get("tickers") or []:
            if ticker not in vistos:
                vistos.append(ticker)
    return vistos


def _cuadrantes(ranking: pd.DataFrame | None) -> dict[str, str]:
    if ranking is None or ranking.empty or "Ticker" not in ranking.columns:
        return {}
    return {str(fila.Ticker): str(fila.Cuadrante) for fila in ranking.itertuples(index=False)}


def _anotar_rrg(filas: list[dict], cuadrantes: dict[str, str]) -> None:
    for fila in filas:
        crudo = cuadrantes.get(fila["ticker"])
        fila["cuadrante"] = NOMBRE_CUADRANTE.get(crudo, crudo)
        fila["rrg"] = relacion_rrg(fila["senal"], crudo)


def _estilo_rrg(valor: str) -> str:
    texto = (valor or "").lower()
    if texto == "coincide":
        return "color: #1e7f4f; font-weight: 700;"
    if "contradice" in texto:
        return "color: #a32020; font-weight: 700;"
    return ""


def _tabla_backtest(filas: list[dict]) -> pd.DataFrame:
    if not filas:
        return pd.DataFrame()
    columnas = [
        ("universo", "Universo"),
        ("entrada", "Entrada"),
        ("salida", "Salida"),
        ("costo", "Costo"),
        ("n", "Operaciones"),
        ("media", "Media"),
        ("media_06", "Neta 0,6%"),
        ("media_12", "Neta 1,2%"),
        ("mediana", "Mediana"),
        ("acierto", "Acierto"),
        ("peor", "Peor"),
        ("dd_max", "Drawdown"),
        ("ganancia_perdida", "Gan./pérd."),
        ("dias_prom", "Ruedas prom."),
        ("media_a1", "Media año 1"),
        ("media_a2", "Media año 2"),
        ("contra", "Contra la referencia"),
    ]
    presentes = [par for par in columnas if any(par[0] in fila and fila.get(par[0]) not in (None, "") for fila in filas)]
    porcentajes = {"media", "media_06", "media_12", "mediana", "peor", "dd_max", "media_a1", "media_a2"}
    vista = []
    for fila in filas:
        texto = {}
        for clave, titulo in presentes:
            valor = fila.get(clave)
            if valor is None or valor == "":
                texto[titulo] = "—"
            elif clave in porcentajes:
                texto[titulo] = _pct(valor)
            elif clave == "acierto":
                texto[titulo] = f"{float(valor):.1f}%".replace(".", ",")
            else:
                texto[titulo] = str(valor)
        vista.append(texto)
    return pd.DataFrame(vista)


def _tabla(filas: list[dict], *, cerradas: bool) -> pd.DataFrame:
    vista = []
    for fila in filas:
        base = {
            "Ticker": fila["ticker"],
            "Señal": fila["senal"],
            "Fecha": fila["fecha"],
            "Entrada teórica": _ars(fila.get("precio_entrada")),
            "Stop": _ars(fila.get("stop")),
            "Último precio": _ars(fila.get("ultimo")),
            "Desde la señal": _pct(fila.get("desde_senal")),
            "Ruedas": "—" if fila.get("ruedas") is None else str(fila["ruedas"]),
            "Cuadrante RRG": fila.get("cuadrante") or "Sin cuadrante",
            "Con el RRG": {"coincide": "Coincide", "contradice": "Se contradice"}.get(fila.get("rrg"), "Sin cuadrante"),
            "Detalle": fila.get("detalle") or "",
        }
        if cerradas:
            base["Salida"] = _ars(fila.get("precio_salida"))
            base["Por qué"] = MOTIVOS_SALIDA.get(fila.get("motivo"), fila.get("motivo") or "")
        vista.append(base)
    return pd.DataFrame(vista)


def vista_senales() -> None:
    cfg = cargar_config()
    universos = cfg.get("universos") or []
    opciones = [u["id"] for u in universos]
    defecto = cfg.get("universo_default") if cfg.get("universo_default") in opciones else (opciones[0] if opciones else "")
    st.markdown("### Señales")
    elegido = st.selectbox(
        "Universo",
        opciones,
        index=opciones.index(defecto) if defecto in opciones else 0,
        format_func=lambda clave: next((u["titulo"] for u in universos if u["id"] == clave), clave),
    )
    universo = universo_por_id(cfg, elegido)
    if universo.get("nota"):
        st.caption(universo["nota"])
    tickers = tickers_de(cfg, elegido)
    st.caption(
        "Cruce de la media de 10 sobre la de 20, con volumen de al menos 1,5 veces el promedio. "
        "Si dentro de las 30 ruedas la media de 10 cruza la de 50, la compra pasa a ser fuerte. "
        "La entrada teórica es la apertura de la rueda siguiente. "
        "Se sale por un stop fijo del 7% o a las 20 ruedas, lo que pase primero."
    )
    st.info(
        "Venta no quiere decir que vendas lo que tengas. "
        "Quiere decir que la posición teórica de esta estrategia ya salió: "
        "tocó el stop, cumplió las 20 ruedas, o cruzó para abajo si esa salida está activada en el config."
    )

    with st.spinner("Armando las señales con la historia en pesos…"):
        ahora = ahora_art()
        pares = {ticker: _yahoo(ticker) for ticker in _todos(cfg)}
        crudo = _historia(tuple(pares.values()), str(cfg.get("history_period") or "5y"))
        historias = {}
        for ticker, yahoo in pares.items():
            serie = crudo["series"].get(yahoo)
            if serie is None or serie.empty:
                continue
            serie = recortar_vela_abierta(serie, ahora, int(cfg.get("close_hour", 17)))
            if serie is None or serie.empty:
                continue
            historias[ticker] = serie
        vivos = cotizaciones_cedears() or {}
        lecturas = _lecturas(historias, vivos, ahora)
        filas = []
        sin_datos = [ticker for ticker in tickers if ticker not in historias]
        for ticker in tickers:
            serie = historias.get(ticker)
            if serie is None or getattr(serie, "empty", True):
                continue
            estado = estado_ticker(ticker, serie, cfg)
            ultimo = None
            lectura = lecturas.get(ticker) or {}
            quote = vivos.get(ticker) or {}
            if quote.get("c") is not None and not lectura.get("bloquea_senal"):
                ultimo = float(quote["c"])
            filas.extend(filas_de_estado(estado, ultimo))
        emitidas, bloqueadas = aplicar_semaforo(filas, lecturas)
        cuadrantes = {}
        rotacion = {"ranking": pd.DataFrame(), "colas": pd.DataFrame(), "frase": ""}
        try:
            from zeta.datos import cargar_panel
            from zeta.rotacion import armar_rotacion
            from zeta.tiempo import clave_cierre

            panel = cargar_panel(clave_cierre())
            rotacion = armar_rotacion(panel["precios_usd"])
            cuadrantes = _cuadrantes(rotacion.get("ranking"))
        except Exception:
            rotacion = {"ranking": pd.DataFrame(), "colas": pd.DataFrame(), "frase": ""}
        _anotar_rrg(emitidas, cuadrantes)
        _anotar_rrg(bloqueadas, cuadrantes)
        backtest = cargar_backtest()

    if not tickers:
        st.info(universo.get("nota") or "Este universo no tiene tickers en el archivo. Cuando se carguen, la pestaña los toma solos.")
        _bloque_backtest(backtest, elegido)
        _pie()
        return

    if not historias:
        st.error("No llegó historia de Yahoo para armar las señales. No se inventan precios.")
        _bloque_backtest(backtest, elegido)
        _pie()
        return

    if bloqueadas:
        nombres = ", ".join(dict.fromkeys(fila["ticker"] for fila in bloqueadas))
        st.error(
            f"No se emite señal de {nombres}: el contraste está en rojo. "
            "Cuando las dos fuentes se separan más del 2%, o el dato tiene más de 30 minutos con el mercado abierto, "
            "esa compra o esa venta no se muestra."
        )

    abiertas = [fila for fila in emitidas if fila.get("estado_posicion") != "cerrada"]
    cerradas = [fila for fila in emitidas if fila.get("estado_posicion") == "cerrada"]
    fuertes = sum(1 for fila in abiertas if fila.get("fuerza") == "fuerte")
    debiles = sum(1 for fila in abiertas if fila.get("fuerza") == "debil")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Compra fuerte", fuertes)
    c2.metric("Compra débil", debiles)
    c3.metric("Ventas recientes", len(cerradas))
    c4.metric("Sin datos", len(sin_datos))
    fechas = [s.index[-1] for s in historias.values() if len(s.index)]
    fecha_txt = f"{max(fechas):%d/%m/%Y}" if fechas else "sin cierre"
    st.caption(
        f"Historia al {fecha_txt}. "
        "El último precio, si el semáforo no está en rojo, es el de data912. "
        "La señal se calculó con el cierre: antes de las 17 no entra la vela de hoy. "
        f"Parámetros en data/estrategia_senales.json."
    )

    st.markdown("#### Posiciones teóricas")
    st.caption(
        "Compra fuerte es la que ya confirmó con la media de 50. "
        "Compra débil es el cruce de 10 sobre 20 con volumen, todavía sin esa confirmación. "
        "«Desde la señal» compara el precio de ahora con la entrada teórica, sin costos."
    )
    if abiertas:
        mostrar_tabla(
            _tabla(abiertas, cerradas=False),
            estilos={"Señal": _estilo_senal, "Desde la señal": _estilo_variacion, "Con el RRG": _estilo_rrg},
            alto=480,
        )
    else:
        st.info("No hay una compra teórica abierta en la ventana de señales vigentes.")

    st.markdown("#### Salidas recientes")
    st.caption(
        "Estas ventas ya cerraron la posición teórica. La fecha es la de la salida, no la de hoy. "
        "El resultado es bruto, sin el costo de la vuelta."
    )
    if cerradas:
        mostrar_tabla(
            _tabla(cerradas, cerradas=True),
            estilos={"Señal": _estilo_senal, "Desde la señal": _estilo_variacion, "Con el RRG": _estilo_rrg},
            alto=420,
        )
    else:
        st.info("En las últimas ruedas no hubo una salida teórica.")

    if sin_datos:
        st.caption("Sin historia suficiente en Yahoo: " + ", ".join(sin_datos) + ".")

    st.markdown("#### Las mismas señales sobre la rotación")
    st.caption(
        "Es el gráfico de rotación sectorial del Panel, contra el SPY. "
        "El rombo es una Compra y la cruz es una Venta. "
        "El borde verde quiere decir que la señal coincide con el cuadrante "
        "(Compra en Líderes o Mejorando; Venta en Debilitándose o Rezagados). "
        "El borde rojo quiere decir que se contradicen. "
        "Un papel que no está en ese gráfico queda sin cuadrante."
    )
    colas = rotacion.get("colas") if isinstance(rotacion, dict) else None
    if colas is None or getattr(colas, "empty", True):
        st.info("No hay rotación para cruzar. Si Yahoo no trajo al SPY y a los ETFs de sector, el cuadrante queda vacío.")
    else:
        marcas = []
        vistos: set[str] = set()
        for fila in abiertas + cerradas:
            if fila["ticker"] in vistos or fila["ticker"] not in cuadrantes:
                continue
            vistos.add(fila["ticker"])
            marcas.append(
                {
                    "ticker": fila["ticker"],
                    "senal": fila["senal"],
                    "cuadrante": fila.get("cuadrante"),
                    "relacion": fila.get("rrg"),
                }
            )
        st.plotly_chart(
            _grafico_rotacion(colas, marcas=marcas),
            width="stretch",
            theme=None,
            key="rrg_senales",
        )
        if rotacion.get("frase"):
            st.caption(rotacion["frase"])

    sin_historia = universo.get("sin_historia") or []
    if sin_historia:
        st.markdown("**Sin señal, porque no hay historia en pesos**")
        st.caption(
            "Estos sectoriales están en el gráfico de rotación del Panel, "
            "pero ni Yahoo .BA ni data912 tienen su serie en pesos. No se les calcula Compra ni Venta."
        )
        mostrar_tabla(
            pd.DataFrame(
                [
                    {
                        "Ticker": ticker,
                        "Señal": "Sin señal (sin historia en pesos)",
                        "Cuadrante RRG": NOMBRE_CUADRANTE.get(cuadrantes.get(ticker), cuadrantes.get(ticker) or "Sin cuadrante"),
                    }
                    for ticker in sin_historia
                ]
            ),
            alto=320,
        )

    _bloque_backtest(backtest, elegido)
    with st.expander("Parámetros y limitaciones"):
        st.markdown(
            f"Medias {cfg['fast']}/{cfg['mid']}/{cfg['slow']}. "
            f"Volumen ≥ {str(cfg['vol_mult']).replace('.', ',')}× el promedio de {cfg['vol_avg']} ruedas. "
            f"Confirmación dentro de {cfg['confirm_window']} ruedas. "
            f"Stop {cfg['stop'].get('pct')}%. Salida a las {cfg['max_hold']} ruedas. "
            f"Señales vigentes: últimas {cfg['recent_days']} ruedas o posición todavía abierta."
        )
        st.markdown(LIMITACIONES)

    _pie()


def _bloque_backtest(backtest: dict, universo_id: str) -> None:
    st.markdown("#### Backtest neto de costos")
    st.warning(backtest.get("advertencia") or "Estas cifras salen del archivo de backtest.")
    st.caption(
        "La tabla no se recalcula con los precios de hoy. "
        "El 0,6% y el 1,2% son un supuesto de ida y vuelta, no la tarifa de un broker, y no incluyen impuestos. "
        "Para cambiar las cifras se edita data/estrategia_backtest.json. "
        "La v3 de ETFs entra en ese archivo, con id etfs, sin tocar esta pantalla."
    )
    estudios = backtest.get("estudios") or []
    propio = next((e for e in estudios if e.get("id") == universo_id), None)
    otros = [e for e in estudios if e.get("id") != universo_id]
    if propio and propio.get("filas"):
        st.markdown(f"**{propio.get('titulo') or propio.get('id')}**")
        if propio.get("nota"):
            st.caption(propio["nota"])
        mostrar_tabla(
            _tabla_backtest(propio["filas"]),
            estilos={"Media": _estilo_variacion, "Mediana": _estilo_variacion},
            alto=420,
        )
    else:
        st.info(
            "Este universo todavía no tiene cifras en el archivo. "
            "Finanzas AR las está recalculando. Cuando estén, se cargan sin cambiar la lógica."
        )
    if otros:
        with st.expander("Otras muestras que ya están en el archivo"):
            for estudio in otros:
                st.markdown(f"**{estudio.get('titulo') or estudio.get('id')}**")
                if estudio.get("nota"):
                    st.caption(estudio["nota"])
                if estudio.get("filas"):
                    mostrar_tabla(
                        _tabla_backtest(estudio["filas"]),
                        estilos={"Media": _estilo_variacion, "Mediana": _estilo_variacion},
                        alto=360,
                    )


def _pie() -> None:
    st.divider()
    st.markdown(
        f'<div class="zeta-aviso">{html.escape(AVISO_ESTRATEGIA)}</div>',
        unsafe_allow_html=True,
    )
