"""Marca, aviso CNV y estilos. La matrícula no se inventa."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

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
    fondo, tarjeta, texto, mute, borde = "#0e1412", "#16201c", "#e7eeea", "#9eb0a6", "#24312b"
    sidebar = "#121a17"
    return f"""
    <style>
      .stApp {{
        background: {fondo};
        color: {texto};
      }}
      [data-testid="stSidebar"] {{
        background: {sidebar};
      }}
      [data-testid="stHeader"] {{
        background: transparent;
      }}
      .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 5.5rem;
        max-width: 1180px;
      }}
      h1, h2, h3 {{
        letter-spacing: -0.02em;
        color: {texto};
      }}
      div[data-testid="stMetric"] {{
        background: {tarjeta};
        border: 1px solid {borde};
        border-radius: 14px;
        padding: 0.75rem 0.9rem 0.55rem;
      }}
      div[data-testid="stMetricLabel"] p {{
        color: {mute};
      }}
      .zeta-aviso {{
        background: {tarjeta};
        border: 1px solid {borde};
        border-left: 4px solid #5dbe8a;
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
        background: #25D366;
        color: #10301c !important;
        padding: 0.65rem 0.95rem;
        border-radius: 999px;
        text-decoration: none;
        font-weight: 700;
        box-shadow: 0 8px 20px rgba(18, 24, 22, 0.18);
      }}
      div[data-testid="stDataFrame"] {{
        border: 1px solid {borde};
        border-radius: 12px;
        overflow: hidden;
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
