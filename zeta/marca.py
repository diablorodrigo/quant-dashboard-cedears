"""Marca, aviso CNV y estilos. La matrícula no se inventa."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from zeta.paleta import TEMAS, paleta

RAIZ = Path(__file__).resolve().parent.parent
LOGO = RAIZ / "assets" / "logo-zeta-finance.png"
LOGO_HEADER = RAIZ / "assets" / "logo-header.png"
FAVICON = RAIZ / "assets" / "favicon.png"

SITIO = "https://www.zetafinance.com.ar"
WHATSAPP = "https://wa.me/5493496462977"

# Reemplazá los guiones por la matrícula, o definí el secreto `matricula`.
MATRICULA_CNV = "___"

AVISO = (
    "El contenido es informativo: son ideas de análisis, no constituyen recomendación de inversión."
)


def matricula() -> str:
    try:
        if "matricula" in st.secrets:
            valor = str(st.secrets["matricula"]).strip()
            if valor:
                return valor
    except Exception:
        pass
    return MATRICULA_CNV


def linea_identidad() -> str:
    return f"Cristian Bernaldez — Asesor registrado CNV, Matrícula N° {matricula()}"


def _css() -> str:
    p = paleta()
    fondo, tarjeta, texto, mute, borde = p["fondo"], p["tarjeta"], p["texto"], p["mute"], p["borde"]
    return f"""
    <style>
      .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
      [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {{
        background: {fondo} !important;
        color: {texto} !important;
      }}
      [data-testid="stSidebar"], [data-testid="stSidebarContent"],
      [data-testid="stSidebarHeader"] {{
        background: {p["sidebar"]} !important;
        color: {texto} !important;
      }}
      [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] span,
      [data-testid="stSidebar"] label,
      [data-testid="stMarkdownContainer"] p,
      [data-testid="stMarkdownContainer"] li,
      [data-testid="stMarkdownContainer"] h1,
      [data-testid="stMarkdownContainer"] h2,
      [data-testid="stMarkdownContainer"] h3,
      [data-testid="stWidgetLabel"] p,
      [data-testid="stRadio"] label,
      label[data-testid="stWidgetLabel"] {{
        color: {texto} !important;
      }}
      [data-testid="stCaptionContainer"] p,
      [data-testid="stCaptionContainer"] span {{
        color: {mute} !important;
      }}
      .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 5.5rem;
        max-width: 1180px;
      }}
      h1, h2, h3 {{
        letter-spacing: -0.02em;
        color: {texto} !important;
      }}
      div[data-testid="stMetric"] {{
        background: {tarjeta} !important;
        border: 1px solid {borde};
        border-radius: 14px;
        padding: 0.75rem 0.9rem 0.55rem;
      }}
      div[data-testid="stMetricLabel"] p,
      div[data-testid="stMetricValue"] {{
        color: {texto} !important;
      }}
      div[data-testid="stMetricLabel"] p {{
        color: {mute} !important;
      }}
      .zeta-aviso {{
        background: {tarjeta};
        border: 1px solid {borde};
        border-left: 4px solid {p["aviso_borde"]};
        border-radius: 12px;
        padding: 0.75rem 0.95rem;
        margin: 0.2rem 0 0.8rem;
        color: {texto};
        line-height: 1.45;
        font-size: 0.92rem;
      }}
      .zeta-aviso strong {{
        color: {texto};
      }}
      .zeta-datos {{
        background: {tarjeta};
        border: 1px solid {borde};
        border-left: 4px solid {p["acento"]};
        border-radius: 12px;
        padding: 0.75rem 0.95rem;
        margin: 0.15rem 0 0.35rem;
        color: {texto};
        font-size: 1.02rem;
        font-weight: 650;
        line-height: 1.45;
      }}
      .zeta-global {{
        background: {tarjeta};
        border: 1px solid {borde};
        border-radius: 14px;
        padding: 0.95rem 1.05rem 0.8rem;
        margin: 0.35rem 0 0.85rem;
        color: {texto};
      }}
      .zeta-global-top {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 1rem;
        flex-wrap: wrap;
      }}
      .zeta-kicker {{
        color: {mute};
        font-family: {p["fuente_mono"]};
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
      }}
      .zeta-sesgo {{
        display: inline-block;
        border-radius: 999px;
        padding: 0.28rem 0.85rem;
        font-weight: 700;
        font-size: 1.15rem;
        line-height: 1.3;
      }}
      .zeta-score {{
        text-align: right;
      }}
      .zeta-score-num {{
        font-size: 2rem;
        font-weight: 700;
        line-height: 1;
        color: {texto};
      }}
      .zeta-score-label {{
        color: {mute};
        font-size: 0.82rem;
        margin-top: 0.15rem;
      }}
      .zeta-frase, .zeta-intro {{
        margin: 0.7rem 0 0.2rem;
        line-height: 1.45;
      }}
      .zeta-grupo {{
        margin: 0.85rem 0 0.15rem;
        font-weight: 700;
      }}
      .zeta-comp {{
        display: flex;
        gap: 0.75rem;
        align-items: baseline;
        border-top: 1px solid {borde};
        padding: 0.48rem 0;
        line-height: 1.4;
      }}
      .zeta-comp-titulo {{
        min-width: 7.2rem;
        font-weight: 700;
      }}
      .zeta-comp-puntos {{
        min-width: 1.8rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
      }}
      .zeta-legal {{
        color: {mute};
        font-size: 0.9rem;
        line-height: 1.4;
        margin: 0.75rem 0 0.1rem;
      }}
      .zeta-sub {{
        color: {mute};
        font-size: 0.92rem;
        margin-top: -0.35rem;
        margin-bottom: 0.6rem;
      }}
      .zeta-wa {{
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 1000;
        background: {p["whatsapp"]};
        color: {p["whatsapp_texto"]} !important;
        padding: 0.65rem 0.95rem;
        border-radius: 999px;
        text-decoration: none;
        font-weight: 700;
        box-shadow: 0 8px 20px {p["sombra"]};
      }}
      .zeta-tabla-marco {{
        max-height: 520px;
        overflow: auto;
        border: 1px solid {borde};
        border-radius: 12px;
        background: {p["tabla_fondo"]};
      }}
      table.zeta-tabla {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
        background: {p["tabla_fondo"]};
        color: {p["tabla_texto"]};
      }}
      table.zeta-tabla th {{
        position: sticky;
        top: 0;
        z-index: 1;
        background: {p["tabla_encabezado"]};
        color: {p["tabla_texto"]};
        text-align: left;
        padding: 0.45rem 0.6rem;
        border-bottom: 1px solid {p["tabla_linea"]};
        font-weight: 650;
      }}
      table.zeta-tabla td {{
        padding: 0.38rem 0.6rem;
        border-bottom: 1px solid {p["tabla_linea"]};
        background: {p["tabla_fondo"]};
        color: {p["tabla_texto"]};
        vertical-align: top;
      }}
      hr, [data-testid="stDivider"] {{
        border-color: {borde} !important;
      }}
      [data-testid="stExpander"] details {{
        background: {tarjeta} !important;
        border: 1px solid {borde} !important;
        color: {texto} !important;
      }}
      [data-testid="stAlert"] {{
        background: {tarjeta} !important;
        color: {texto} !important;
        border: 1px solid {borde} !important;
      }}
      [data-baseweb="tab-list"] {{
        background: transparent !important;
      }}
      [data-baseweb="tab"] {{
        color: {mute} !important;
      }}
      [data-baseweb="tab"][aria-selected="true"] {{
        color: {texto} !important;
      }}
      [data-baseweb="tab-highlight"] {{
        background-color: {p["acento"]} !important;
      }}
      div[data-baseweb="select"] > div,
      [data-testid="stTextInput"] input,
      [data-testid="stNumberInput"] input {{
        background: {tarjeta} !important;
        color: {texto} !important;
        border-color: {borde} !important;
      }}
      div[data-baseweb="popover"] ul,
      div[data-baseweb="menu"] {{
        background: {tarjeta} !important;
      }}
      div[data-baseweb="popover"] li,
      div[data-baseweb="menu"] li {{
        color: {texto} !important;
      }}
      button[data-testid="stBaseButton-secondary"],
      button[data-testid="stBaseButton-tertiary"] {{
        background: {tarjeta} !important;
        color: {texto} !important;
        border: 1px solid {borde} !important;
      }}
      button[data-testid="stBaseButton-primary"] {{
        background: {p["acento"]} !important;
        color: {p["acento_texto"]} !important;
        border: 1px solid {p["acento"]} !important;
      }}
      a {{
        color: {p["acento"]};
      }}
      @media (max-width: 800px) {{
        .block-container {{
          padding-left: 0.8rem;
          padding-right: 0.8rem;
        }}
        div[data-testid="stHorizontalBlock"] {{
          flex-wrap: wrap;
          gap: 0.5rem;
        }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
          min-width: 100% !important;
          flex: 1 1 100% !important;
        }}
      }}
    </style>
    <a class="zeta-wa" href="{WHATSAPP}" target="_blank" rel="noopener">WhatsApp</a>
    """


def selector_tema() -> None:
    """El cliente cambia Oscuro / Claro. La clave queda en la sesión."""
    st.radio("Tema", list(TEMAS), horizontal=True, key="tema")


def aplicar_estilos() -> None:
    st.markdown(_css(), unsafe_allow_html=True)


def aviso() -> None:
    st.markdown(
        f"""
        <div class="zeta-aviso">
          <strong>{linea_identidad()}</strong> · Zeta Finance<br>
          {AVISO}
        </div>
        """,
        unsafe_allow_html=True,
    )


def usuarios() -> dict:
    try:
        tabla = st.secrets["passwords"]
    except Exception:
        st.error(
            "Falta la bóveda de acceso. Creá `.streamlit/secrets.toml` con la tabla "
            "`[passwords]`, como en `.streamlit/secrets.toml.example`."
        )
        st.stop()
    return {str(usuario): str(clave) for usuario, clave in dict(tabla).items()}


def vista_login() -> None:
    columna = st.columns([1, 1.3, 1])[1]
    with columna:
        if LOGO.exists():
            st.image(str(LOGO), width=96)
        st.markdown("## Zeta Finance · Panel de análisis")
        st.markdown(
            "<p class='zeta-sub'>Lectura de CEDEARs para clientes. Acceso con usuario y contraseña.</p>",
            unsafe_allow_html=True,
        )
        aviso()
        selector_tema()
        with st.form("login"):
            usuario = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("Ingresar", width="stretch", type="primary")
        if entrar:
            permitidos = usuarios()
            if usuario in permitidos and permitidos[usuario] == contrasena:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario no registrado.")
        st.link_button("zetafinance.com.ar", SITIO)
