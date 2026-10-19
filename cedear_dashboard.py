"""Zeta Finance · Panel de análisis de CEDEARs.

Punto de entrada. En Streamlit Community Cloud hay que ejecutarlo con
``streamlit run cedear_dashboard.py``. El acceso sigue leyendo
``st.secrets["passwords"]``.
"""

import streamlit as st

from zeta.marca import FAVICON, aplicar_estilos, vista_login
from zeta.vistas import (
    barra_lateral,
    encabezado,
    pie,
    vista_activo,
    vista_carteras,
    vista_metodologia,
    vista_monitor,
    vista_radar,
    vista_resumen,
)

st.set_page_config(
    page_title="Zeta Finance · Panel de análisis",
    page_icon=str(FAVICON) if FAVICON.exists() else "📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "tema" not in st.session_state:
    st.session_state["tema"] = "Claro"

aplicar_estilos()

if not st.session_state["autenticado"]:
    vista_login()
    st.stop()

barra_lateral()
encabezado()
st.navigation(
    [
        st.Page(vista_resumen, title="Resumen", icon=":material/dashboard:", default=True),
        st.Page(vista_monitor, title="Monitor", icon=":material/monitoring:"),
        st.Page(vista_activo, title="Análisis por activo", icon=":material/query_stats:"),
        st.Page(vista_radar, title="Radar", icon=":material/radar:"),
        st.Page(vista_carteras, title="Carteras modelo", icon=":material/pie_chart:"),
        st.Page(vista_metodologia, title="Metodología", icon=":material/menu_book:"),
    ]
).run()
pie()
