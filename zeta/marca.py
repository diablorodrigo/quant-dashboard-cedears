"""Marca, aviso CNV y estilos."""

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
INSTAGRAM = "https://www.instagram.com/cristianbernaldez.ok/"
INSTAGRAM_TEXTO = "@cristianbernaldez.ok"

ENLACES = (
    ("zetafinance.com.ar", SITIO, ":material/language:"),
    ("WhatsApp", WHATSAPP, ":material/chat:"),
    (INSTAGRAM_TEXTO, INSTAGRAM, ":material/photo_camera:"),
)

# Número público de la matrícula. Un secreto `matricula` lo puede reemplazar.
MATRICULA_CNV = "2103"

AVISO = (
    "El contenido es informativo: son ideas de análisis, no constituyen recomendación de inversión."
)


def matricula() -> str:
    try:
        if "matricula" in st.secrets:
            valor = str(st.secrets["matricula"]).strip()
            if valor and valor != "___":
                return valor
    except Exception:
        pass
    return MATRICULA_CNV


def linea_identidad() -> str:
    return f"Cristian Bernaldez — Asesor registrado CNV, Matrícula CNV N° {matricula()}"


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
      .zeta-flotantes {{
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0.45rem;
      }}
      .zeta-flotantes a {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.65rem 0.95rem;
        border-radius: 999px;
        text-decoration: none;
        font-weight: 700;
        box-shadow: 0 8px 20px {p["sombra"]};
      }}
      .zeta-flotantes svg {{
        width: 16px;
        height: 16px;
        flex: 0 0 auto;
      }}
      .zeta-wa {{
        background: {p["whatsapp"]};
        color: {p["whatsapp_texto"]} !important;
      }}
      .zeta-ig {{
        background: {tarjeta};
        color: {texto} !important;
        border: 1px solid {borde};
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
    <div class="zeta-flotantes">
      <a class="zeta-ig" href="{INSTAGRAM}" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="4" y="4" width="16" height="16" rx="5"></rect>
          <circle cx="12" cy="12" r="3.5"></circle>
          <circle cx="17.2" cy="6.8" r="0.8" fill="currentColor" stroke="none"></circle>
        </svg>
        {INSTAGRAM_TEXTO}
      </a>
      <a class="zeta-wa" href="{WHATSAPP}" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
          <path d="M12.04 3.2A8.7 8.7 0 0 0 4.7 16.3L3.6 20.4l4.2-1.1a8.7 8.7 0 0 0 4.24 1.08h.01a8.7 8.7 0 0 0 0-17.4zm5.06 12.3c-.21.6-1.23 1.1-1.7 1.17-.43.06-.98.09-1.58-.1-.36-.11-.83-.27-1.43-.53-2.52-1.09-4.16-3.63-4.29-3.8-.12-.17-1.04-1.38-1.04-2.63s.66-1.86.89-2.12c.23-.26.51-.32.68-.32h.49c.16 0 .37-.06.58.44.21.52.73 1.8.8 1.93.06.13.1.28.02.45-.08.17-.12.28-.24.43-.12.15-.25.33-.36.44-.12.12-.24.25-.1.49.13.23.6.99 1.29 1.6.89.79 1.64 1.04 1.87 1.16.23.11.37.1.5-.06.14-.17.58-.67.73-.9.16-.23.31-.19.52-.11.21.08 1.34.63 1.57.75.23.11.38.17.44.26.06.1.06.55-.15 1.15z"/>
        </svg>
        WhatsApp
      </a>
    </div>
    """


def mostrar_enlaces(*, barra: bool = False, en_fila: bool = False) -> None:
    """Web, WhatsApp e Instagram, con ícono y texto. Los colores salen del tema."""
    if en_fila and not barra:
        columnas = st.columns(len(ENLACES))
        for columna, (etiqueta, url, icono) in zip(columnas, ENLACES):
            with columna:
                st.link_button(etiqueta, url, icon=icono, width="stretch")
        return
    destino = st.sidebar if barra else st
    for etiqueta, url, icono in ENLACES:
        destino.link_button(etiqueta, url, icon=icono, width="stretch")


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
        mostrar_enlaces()
