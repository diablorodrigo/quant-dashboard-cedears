"""Dos paletas de Zeta Finance. Los gráficos y el CSS leen de acá.

Oscuro es el default. Claro es el modo día. Ningún color de la interfaz
vive fuera de estos diccionarios.
"""

from __future__ import annotations

TEMA_DEFAULT = "Oscuro"

TEMAS: dict[str, dict] = {
    "Oscuro": {
        "fondo": "#0e1412",
        "tarjeta": "#16201c",
        "sidebar": "#121a17",
        "texto": "#e7eeea",
        "mute": "#9eb0a6",
        "borde": "#24312b",
        "acento": "#5dbe8a",
        "acento_texto": "#0e1412",
        "aviso_borde": "#5dbe8a",
        "whatsapp": "#25D366",
        "whatsapp_texto": "#10301c",
        "sombra": "rgba(8, 12, 10, 0.45)",
        "tabla_fondo": "#16201c",
        "tabla_texto": "#e7eeea",
        "tabla_encabezado": "#1c2a24",
        "tabla_linea": "#24312b",
        "fondo_grafico": "#0c1210",
        "texto_grafico": "#e7eeea",
        "mute_grafico": "#8ea39a",
        "titulo_eje": "#c5d4cc",
        "grilla": "rgba(158, 176, 166, 0.10)",
        "cruce": "rgba(197, 212, 204, 0.40)",
        "aro": "#f4f7f5",
        "etiqueta": "#f4f7f5",
        "texto_sobre_serie": "#f4f7f5",
        "fuente": "IBM Plex Sans, sans-serif",
        "fuente_mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        "plantilla": "plotly_dark",
        "lider": "#5dbe8a",
        "mejorando": "#6aaed4",
        "debilitando": "#d4a15a",
        "rezagado": "#e07a72",
        "tint_lider": "rgba(93, 190, 138, 0.13)",
        "tint_mejorando": "rgba(106, 174, 212, 0.12)",
        "tint_debilitando": "rgba(212, 161, 90, 0.12)",
        "tint_rezagado": "rgba(224, 122, 114, 0.12)",
        "esquina_lider": "rgba(93, 190, 138, 0.90)",
        "esquina_mejorando": "rgba(106, 174, 212, 0.90)",
        "esquina_debilitando": "rgba(212, 161, 90, 0.90)",
        "esquina_rezagado": "rgba(224, 122, 114, 0.90)",
        "sma10": "#6aaed4",
        "sma20": "#d4a15a",
        "sma50": "#c4b48a",
        "ema200": "#8fbfa8",
        "bollinger": "#8ea39a",
        "rsi": "#9eb0c4",
        "macd": "#6aaed4",
        "macd_senal": "#d4a15a",
        "vela_alta": "#5dbe8a",
        "vela_baja": "#e07a72",
        "torta": ("#5dbe8a", "#6aaed4", "#d4a15a", "#8fbfa8", "#e07a72", "#c4b48a", "#9eb0c4", "#7d9a8a"),
        "pasos_gauge": ("#4a2c2a", "#4a3a24", "#3a3a24", "#1c3a30", "#145238"),
        "barra_gauge": "#5dbe8a",
        "lectura_observacion_bg": "rgba(212, 161, 90, 0.28)",
        "lectura_alcista_fuerte_bg": "rgba(93, 190, 138, 0.32)",
        "lectura_alcista_bg": "rgba(93, 190, 138, 0.16)",
        "lectura_bajista_fuerte_bg": "rgba(224, 122, 114, 0.32)",
        "lectura_bajista_bg": "rgba(224, 122, 114, 0.16)",
        "variacion_pos": "#7dcea0",
        "variacion_neg": "#e07a72",
        "volumen_alto": "#6aaed4",
        "volumen_bajo": "#9eb0a6",
    },
    "Claro": {
        "fondo": "#f4f7f5",
        "tarjeta": "#ffffff",
        "sidebar": "#e7eeea",
        "texto": "#1c2430",
        "mute": "#5c6b66",
        "borde": "#d5e0da",
        "acento": "#1e3a34",
        "acento_texto": "#f4f7f5",
        "aviso_borde": "#1e3a34",
        "whatsapp": "#25D366",
        "whatsapp_texto": "#10301c",
        "sombra": "rgba(18, 24, 22, 0.12)",
        "tabla_fondo": "#ffffff",
        "tabla_texto": "#1c2430",
        "tabla_encabezado": "#e7eeea",
        "tabla_linea": "#d5e0da",
        "fondo_grafico": "#f7faf8",
        "texto_grafico": "#1c2430",
        "mute_grafico": "#5c6b66",
        "titulo_eje": "#1e3a34",
        "grilla": "rgba(30, 58, 52, 0.10)",
        "cruce": "rgba(30, 58, 52, 0.45)",
        "aro": "#1e3a34",
        "etiqueta": "#1c2430",
        "texto_sobre_serie": "#f7faf8",
        "fuente": "IBM Plex Sans, sans-serif",
        "fuente_mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        "plantilla": "plotly_white",
        "lider": "#1f7a4d",
        "mejorando": "#1d6a8a",
        "debilitando": "#9a6a28",
        "rezagado": "#a33b32",
        "tint_lider": "rgba(31, 122, 77, 0.14)",
        "tint_mejorando": "rgba(29, 106, 138, 0.14)",
        "tint_debilitando": "rgba(154, 106, 40, 0.16)",
        "tint_rezagado": "rgba(163, 59, 50, 0.12)",
        "esquina_lider": "#1f7a4d",
        "esquina_mejorando": "#1d6a8a",
        "esquina_debilitando": "#9a6a28",
        "esquina_rezagado": "#a33b32",
        "sma10": "#1d6a8a",
        "sma20": "#9a6a28",
        "sma50": "#6e5840",
        "ema200": "#1e3a34",
        "bollinger": "#5c6b66",
        "rsi": "#3e5568",
        "macd": "#1d6a8a",
        "macd_senal": "#9a6a28",
        "vela_alta": "#1f7a4d",
        "vela_baja": "#a33b32",
        "torta": ("#1e3a34", "#2f6f4e", "#1d6a8a", "#8d6b4a", "#5c9478", "#a33b32", "#6e5840", "#3e5568"),
        "pasos_gauge": ("#e7c7c3", "#f0ddc4", "#efe6c8", "#d5e8dc", "#b7d7c4"),
        "barra_gauge": "#1e3a34",
        "lectura_observacion_bg": "rgba(154, 106, 40, 0.20)",
        "lectura_alcista_fuerte_bg": "rgba(31, 122, 77, 0.28)",
        "lectura_alcista_bg": "rgba(31, 122, 77, 0.14)",
        "lectura_bajista_fuerte_bg": "rgba(163, 59, 50, 0.24)",
        "lectura_bajista_bg": "rgba(163, 59, 50, 0.12)",
        "variacion_pos": "#1f7a4d",
        "variacion_neg": "#a33b32",
        "volumen_alto": "#1d6a8a",
        "volumen_bajo": "#5c6b66",
    },
}


def _cerrar_lecturas(colores: dict) -> dict:
    texto = colores["texto"]
    pesos = {
        "lectura_observacion": ("lectura_observacion_bg", "650"),
        "lectura_alcista": ("lectura_alcista_bg", "650"),
        "lectura_alcista_fuerte": ("lectura_alcista_fuerte_bg", "700"),
        "lectura_bajista": ("lectura_bajista_bg", "650"),
        "lectura_bajista_fuerte": ("lectura_bajista_fuerte_bg", "700"),
    }
    for nombre, (fondo, peso) in pesos.items():
        colores[nombre] = f"background-color: {colores[fondo]}; color: {texto}; font-weight: {peso};"
    return colores


for _nombre in TEMAS:
    TEMAS[_nombre] = _cerrar_lecturas(TEMAS[_nombre])


def tema_activo() -> str:
    """El tema elegido en esta sesión. Oscuro si todavía no hay elección."""
    try:
        import streamlit as st

        valor = st.session_state.get("tema", TEMA_DEFAULT)
    except Exception:
        valor = TEMA_DEFAULT
    if valor not in TEMAS:
        return TEMA_DEFAULT
    return str(valor)


def paleta() -> dict:
    return TEMAS[tema_activo()]
