import warnings
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

# Configuración inicial de la página
st.set_page_config(
    page_title="Quant Dashboard - USD Engine",
    page_icon="📈",
    layout="wide"
)

# ---------------------------------------------------------------------------
# SISTEMA DE ACCESO Y SEGURIDAD (VÍA BÓVEDA SECRETA)
# ---------------------------------------------------------------------------
USUARIOS_PERMITIDOS = st.secrets["passwords"]


def mostrar_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("🔒 **Acceso Restringido:** Plataforma exclusiva para clientes.")

        usuario = st.text_input("Usuario")
        contrasena = st.text_input("Contraseña", type="password")

        if st.button("Ingresar al Dashboard", use_container_width=True):
            if usuario in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[usuario] == contrasena:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas o usuario no registrado.")
# ---------------------------------------------------------------------------
# ESTILOS VISUALES Y TEMAS
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración Visual")
    tema_grafico = st.radio("Tema del Gráfico:", ["Oscuro 🌙", "Claro ☀️"])

    if tema_grafico == "Oscuro 🌙":
        bg_color = "plotly_dark"
        ema_color = "#ffffff"
    else:
        bg_color = "plotly_white"
        ema_color = "#000000"


def pintar_senal(val):
    if isinstance(val, str):
        if 'COMPRA CONFIRMADA' in val:
            return 'background-color: rgba(46, 204, 113, 0.4); font-weight: bold; color: #1e8449;'
        elif 'COMPRA' in val:
            return 'background-color: rgba(46, 204, 113, 0.2); font-weight: bold;'
        elif 'FALSA RUPTURA' in val:
            return 'background-color: rgba(243, 156, 18, 0.3); font-weight: bold; color: #d35400;'
        elif 'VENTA' in val:
            return 'background-color: rgba(231, 76, 60, 0.2); font-weight: bold;'
        elif 'VETADO' in val:
            return 'background-color: rgba(241, 196, 15, 0.3); font-weight: bold; color: #d35400;'
    return ''


def pintar_porcentajes(val):
    if isinstance(val, str) and '%' in val:
        try:
            num = float(val.replace('%', ''))
            if num > 0:
                return 'color: #00b894; font-weight: bold;'
            elif num < 0:
                return 'color: #d63031; font-weight: bold;'
        except:
            pass
    return ''


def pintar_volumen(val):
    if isinstance(val, str) and '%' in val:
        try:
            num = float(val.replace('%', ''))
            if num > 120:
                return 'color: #3498db; font-weight: bold;'  # Azul fuerte
            elif num < 80:
                return 'color: #95a5a6;'  # Gris
        except:
            pass
    return ''


# ---------------------------------------------------------------------------
# 1) UNIVERSO DE ACTIVOS
# ---------------------------------------------------------------------------
WATCHLIST = {
    "AAPL": {"name": "Apple", "cedear": "AAPL.BA", "underlying": "AAPL", "ratio": 20},
    "MSFT": {"name": "Microsoft", "cedear": "MSFT.BA", "underlying": "MSFT", "ratio": 30},
    "AMZN": {"name": "Amazon", "cedear": "AMZN.BA", "underlying": "AMZN", "ratio": 144},
    "NVDA": {"name": "Nvidia", "cedear": "NVDA.BA", "underlying": "NVDA", "ratio": 24},
    "META": {"name": "Meta", "cedear": "META.BA", "underlying": "META", "ratio": 24},
    "TSLA": {"name": "Tesla", "cedear": "TSLA.BA", "underlying": "TSLA", "ratio": 15},
    "KO": {"name": "Coca-Cola", "cedear": "KO.BA", "underlying": "KO", "ratio": 5},
    "MELI": {"name": "Mercado Libre", "cedear": "MELI.BA", "underlying": "MELI", "ratio": 120},
    "VIST": {"name": "Vista Energy", "cedear": "VIST.BA", "underlying": "VIST", "ratio": 3},
    "GOOGL": {"name": "Google", "cedear": "GOOGL.BA", "underlying": "GOOGL", "ratio": 58},
    "JPM": {"name": "JP Morgan", "cedear": "JPM.BA", "underlying": "JPM", "ratio": 15},
    "F": {"name": "Ford", "cedear": "F.BA", "underlying": "F", "ratio": 1},
    "MCD": {"name": "MC Donals", "cedear": "MCD.BA", "underlying": "MCD", "ratio": 24},
    "PEP": {"name": "Pepsi", "cedear": "PEP.BA", "underlying": "PEP", "ratio": 18},
    "V": {"name": "Visa", "cedear": "V.BA", "underlying": "V", "ratio": 18},
    "MA": {"name": "Mastercard", "cedear": "MA.BA", "underlying": "MA", "ratio": 33},
    "AXP": {"name": "Amercian Express", "cedear": "AXP.BA", "underlying": "AXP", "ratio": 15},
    "XLF": {"name": "Sector Financial", "cedear": "XLF.BA", "underlying": "XLF", "ratio": 2},
    "GLD": {"name": "ETF GOLD", "cedear": "GLD.BA", "underlying": "GLD", "ratio": 50},
    "LLY": {"name": "Eli Lilly", "cedear": "LLY.BA", "underlying": "LLY", "ratio": 56},
    "WMT": {"name": "Walmart", "cedear": "WMT.BA", "underlying": "WMT", "ratio": 18},
    "EEM": {"name": "Emerging Market", "cedear": "EEM.BA", "underlying": "EEM", "ratio": 5},
    "IWM": {"name": "Russell 2000", "cedear": "IWM.BA", "underlying": "IWM", "ratio": 10},
    "CAT": {"name": "Caterpillar", "cedear": "CAT.BA", "underlying": "CAT", "ratio": 20},
    "BNY": {"name": "Bank of New York", "cedear": "BNY.BA", "underlying": "BNY", "ratio": 2},
    "XLE": {"name": "ETF Energy", "cedear": "XLE.BA", "underlying": "XLE", "ratio": 2},
    "XLP": {"name": "ETF Consumo Basico", "cedear": "XLP.BA", "underlying": "XLP", "ratio": 16},
    "XLU": {"name": "ETF Utilities", "cedear": "XLU.BA", "underlying": "XLU", "ratio": 15},
    "ARKK": {"name": "ARK Innovation", "cedear": "ARKK.BA", "underlying": "ARKK", "ratio": 10},
    "EWZ": {"name": "ETF Brasil", "cedear": "EWZ.BA", "underlying": "EWZ", "ratio": 2},
    "IBIT": {"name": "ETF Bitcoin", "cedear": "IBIT.BA", "underlying": "IBIT", "ratio": 10},
    "QQQ": {"name": "NASDAQ", "cedear": "QQQ.BA", "underlying": "QQQ", "ratio": 20},
    "DIA": {"name": "Dow Jones", "cedear": "DIA.BA", "underlying": "DIA", "ratio": 20},
    "USO": {"name": "United State OIL", "cedear": "USO.BA", "underlying": "USO", "ratio": 15},
    "XLV": {"name": "ETF Health Care", "cedear": "XLV.BA", "underlying": "XLV", "ratio": 29},
    "ABBV": {"name": "ABBVIE Inc", "cedear": "ABBV.BA", "underlying": "ABBV", "ratio": 10},
    "UNH": {"name": "U Health Group", "cedear": "UNH.BA", "underlying": "UNH", "ratio": 33},
    "AMGN": {"name": "Amgen Inc", "cedear": "AMGN.BA", "underlying": "AMGN", "ratio": 30},
    "PFE": {"name": "Pzizer", "cedear": "PFE.BA", "underlying": "PFE", "ratio": 4},
    "CVS": {"name": "CVS Health", "cedear": "CVS.BA", "underlying": "CVS", "ratio": 15},
    "MRNA": {"name": "Moderna", "cedear": "MRNA.BA", "underlying": "MRNA", "ratio": 19},
    "AAL": {"name": "Amercian Airlines", "cedear": "AAL.BA", "underlying": "AAL", "ratio": 2},
    "ACN": {"name": "Accenture", "cedear": "ACN.BA", "underlying": "ACN", "ratio": 75},
    "ADBE": {"name": "Adobe Inc", "cedear": "ADBE.BA", "underlying": "ADBE", "ratio": 44},
    "ADI": {"name": "Analog Devices", "cedear": "ADI.BA", "underlying": "ADI", "ratio": 15},
    "AMD": {"name": "AMD", "cedear": "AMD.BA", "underlying": "AMD", "ratio": 10},
    "INTC": {"name": "INTEL Corp", "cedear": "INTC.BA", "underlying": "INTC", "ratio": 5},
    "ARCO": {"name": "Arcos Dorados", "cedear": "ARCO.BA", "underlying": "ARCO", "ratio": 0.5},
    "ARM": {"name": "Arm Holdings", "cedear": "ARM.BA", "underlying": "ARM", "ratio": 27},
    "AVGO": {"name": "Broadcom", "cedear": "AVGO.BA", "underlying": "AVGO", "ratio": 39},
    "BBD": {"name": "Banco Bradesco", "cedear": "BBD.BA", "underlying": "BBD", "ratio": 1},
    "SPCX": {"name": "SPACEX", "cedear": "SPCX.BA", "underlying": "SPCX", "ratio": 50},
    "MU": {"name": "Micron Technology", "cedear": "MU.BA", "underlying": "MU", "ratio": 5},
    "NU": {"name": "Nubank", "cedear": "NU.BA", "underlying": "NU", "ratio": 2},
    "LMT": {"name": "Lockheed Martin", "cedear": "LMT.BA", "underlying": "LMT", "ratio": 20},
    "LRCX": {"name": "LAM Research", "cedear": "LRCX.BA", "underlying": "LRCX", "ratio": 56},
    "COPX": {"name": "Global Miners", "cedear": "COPX.BA", "underlying": "COPX", "ratio": 14},
    "SLV": {"name": "Silver ETF", "cedear": "SLV.BA", "underlying": "SLV", "ratio": 6},
    "ASML": {"name": "ASML Holding", "cedear": "ASML.BA", "underlying": "ASML", "ratio": 146},
    "BA": {"name": "Boeing Comp", "cedear": "BA.BA", "underlying": "BA", "ratio": 24},
    "BKR": {"name": "Backer Hughes", "cedear": "BKR.BA", "underlying": "BKR", "ratio": 7},
    "BMY": {"name": "Bristol M", "cedear": "BMY.BA", "underlying": "BMY", "ratio": 3},
    "BG": {"name": "Bunge Limited", "cedear": "BNG.BA", "underlying": "BG", "ratio": 5},
    "BRK-B": {"name": "Berkshire Hathaway", "cedear": "BRKB.BA", "underlying": "BRK-B", "ratio": 22},
    "BAC": {"name": "Bank of America", "cedear": "BA.C.BA", "underlying": "BAC", "ratio": 4},
    "CEG": {"name": "Constellation Energy", "cedear": "CEG.C.BA", "underlying": "CEG", "ratio": 45},
    "CL": {"name": "Colgate Palmolive", "cedear": "CL.BA", "underlying": "CL", "ratio": 3},
    "COIN": {"name": "Coinbase", "cedear": "COIN.BA", "underlying": "COIN", "ratio": 27},
    "COST": {"name": "Costco Wholsale", "cedear": "COST.BA", "underlying": "COST", "ratio": 48},
    "CRM": {"name": "SALESFORCE", "cedear": "CRM.BA", "underlying": "CRM", "ratio": 18},
    "CRWD": {"name": "CROWDSTRIKE", "cedear": "CRWD.BA", "underlying": "CRWD", "ratio": 79},
    "CSCO": {"name": "Cisco Systems", "cedear": "CSCO.BA", "underlying": "CSCO", "ratio": 5},
    "CVX": {"name": "Chevron Corp", "cedear": "CVX.BA", "underlying": "CVX", "ratio": 16},
    "DE": {"name": "DEERE Comp", "cedear": "DE.BA", "underlying": "DE", "ratio": 40},
    "DELL": {"name": "DELL", "cedear": "DELL.BA", "underlying": "DELL", "ratio": 74},
    "EMBJ": {"name": "Embraer", "cedear": "EMBJ.BA", "underlying": "EMBJ", "ratio": 1},
    "EBAY": {"name": "EBAY", "cedear": "EBAY.BA", "underlying": "EBAY", "ratio": 2},
    "EWJ": {"name": "ETF Japan", "cedear": "EWJ.BA", "underlying": "EWJ", "ratio": 2},
    "GEV": {"name": "GE VERNOVA", "cedear": "GEV.BA", "underlying": "GEV", "ratio": 180},
    "GM": {"name": "General Motors", "cedear": "GM.BA", "underlying": "GM", "ratio": 6},
    "GS": {"name": "Goldman Sachs", "cedear": "GS.BA", "underlying": "GS", "ratio": 13},
    "GT": {"name": "Goodyear Tire", "cedear": "GT.BA", "underlying": "GT", "ratio": 2},
    "HALL": {"name": "Halliburton", "cedear": "HAL.BA", "underlying": "HAL", "ratio": 2},
    "HD": {"name": "Home Depot", "cedear": "HD.BA", "underlying": "HD", "ratio": 32},
    "HON": {"name": "Honeywell", "cedear": "HON.BA", "underlying": "HON", "ratio": 8},
    "HPQ": {"name": "Hp Inc", "cedear": "HPQ.BA", "underlying": "HPQ", "ratio": 1},
    "HSY": {"name": "Hershey Company", "cedear": "HSY.BA", "underlying": "HSY", "ratio": 21},
    "HUT": {"name": "Hut 8 Mining", "cedear": "HUT.BA", "underlying": "HUT", "ratio": 5},
    "ITA": {"name": "Aeropace & Defense", "cedear": "ITA.BA", "underlying": "ITA", "ratio": 50},
    "IREN": {"name": "IREN", "cedear": "IREN.BA", "underlying": "IREN", "ratio": 12},
    "ITUB": {"name": "ITAU Unibanco", "cedear": "ITUB.BA", "underlying": "ITUB", "ratio": 1},
    "JNJ": {"name": "Johnson & Johnson", "cedear": "JNJ.BA", "underlying": "JNJ", "ratio": 15},
    "MDLZ": {"name": "Mondelez", "cedear": "MDLZ.BA", "underlying": "MDLZ", "ratio": 15},
    "MMM": {"name": "3 M", "cedear": "CRWD.BA", "underlying": "MMM", "ratio": 10},
    "MS": {"name": "Morgan Stanley", "cedear": "MS.BA", "underlying": "MS", "ratio": 1},
    "MSTR": {"name": "Microstrategy", "cedear": "MSTR.BA", "underlying": "MSTR", "ratio": 20},
    "NFLX": {"name": "Netflix", "cedear": "NFLX.BA", "underlying": "NFLX", "ratio": 48},
    "O": {"name": "Realty Income", "cedear": "O.BA", "underlying": "O", "ratio": 13},
    "ORCL": {"name": "Oracle Corp", "cedear": "ORCL.BA", "underlying": "ORCL", "ratio": 3},
    "OXY": {"name": "Occidental Petroleum", "cedear": "OXY.BA", "underlying": "OXY", "ratio": 5},
    "PAGS": {"name": "Pagseguro", "cedear": "PAGS.BA", "underlying": "PAGS", "ratio": 3},
    "PBR": {"name": "Petrobras", "cedear": "PBR.BA", "underlying": "PBR", "ratio": 1},
    "PG": {"name": "Procter & Gamble", "cedear": "PG.BA", "underlying": "PG", "ratio": 15},
    "PLTR": {"name": "Palantir Technologies", "cedear": "PLTR.BA", "underlying": "PLTR", "ratio": 3},
    "PYPL": {"name": "Paypal", "cedear": "PYPL.BA", "underlying": "PYPL", "ratio": 8},
    "QCOM": {"name": "Qualcom Inc", "cedear": "QCOM.BA", "underlying": "QCOM", "ratio": 11},
    "RACE": {"name": "Ferrari", "cedear": "RACE.BA", "underlying": "RACE", "ratio": 83},
    "RGTI": {"name": "Rigetti Computing", "cedear": "RGTI.BA", "underlying": "RGTI", "ratio": 2},
    "SBUX": {"name": "Starbucks", "cedear": "SBUX.BA", "underlying": "SBUX", "ratio": 12},
    "XOM": {"name": "Exxom Mobil", "cedear": "XOM.BA", "underlying": "XOM", "ratio": 10},
    "XLY": {"name": "Consumo Discrecional ETF", "cedear": "XLY.BA", "underlying": "XLY", "ratio": 43},
    "XLB": {"name": "Materials Select", "cedear": "XLB.BA", "underlying": "XLB", "ratio": 18},
    "XLC": {"name": "Communication Services", "cedear": "XLC.BA", "underlying": "XLC", "ratio": 79},
    "XLI": {"name": "Industrial Select", "cedear": "XLI.BA", "underlying": "XLI", "ratio": 28},
    "XLK": {"name": "Technology Select", "cedear": "XLK.BA", "underlying": "XLK", "ratio": 46},
    "VALE": {"name": "Vale Do Rio Doce", "cedear": "VALE.BA", "underlying": "VALE", "ratio": 2},
    "URA": {"name": "Global X Uranium", "cedear": "URA.BA", "underlying": "URA", "ratio": 5},
    "UL": {"name": "Unilever NV NY", "cedear": "UL.BA", "underlying": "UL", "ratio": 3},
    "UBER": {"name": "UBER Technologies", "cedear": "UBER.BA", "underlying": "UBER", "ratio": 2},
    "TXN": {"name": "Texas Instruments", "cedear": "TXN.BA", "underlying": "TXN", "ratio": 5},
    "UAL": {"name": "United Airlines", "cedear": "UAL.BA", "underlying": "UAL", "ratio": 5},
    "TWLO": {"name": "Twilio Inc", "cedear": "TWLO.BA", "underlying": "TWLO", "ratio": 36},
    "TSM": {"name": "Taiwan Semic. Manuf.", "cedear": "TSM.BA", "underlying": "TSM", "ratio": 9},
    "TM": {"name": "Toyota Motors", "cedear": "TM.BA", "underlying": "TM", "ratio": 15},
    "SYY": {"name": "Sysco Corporation", "cedear": "SYY.BA", "underlying": "SYY", "ratio": 8},
    "STLA": {"name": "Stellantis NV", "cedear": "STLA.BA", "underlying": "STLA", "ratio": 5},
    "SPOT": {"name": "Spotify Tech", "cedear": "SPOT.BA", "underlying": "SPOT", "ratio": 28},
    "SNDK": {"name": "Sandisk Corp", "cedear": "SNDK.BA", "underlying": "SNDK", "ratio": 170}
}


# ---------------------------------------------------------------------------
# 2) INDICADORES MATEMÁTICOS
# ---------------------------------------------------------------------------
def sma(series, window): return series.rolling(window).mean()


def ema(series, window): return series.ewm(span=window, adjust=False).mean()


def rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def bollinger(series, window=20, num_std=2):
    mid = sma(series, window)
    std = series.rolling(window).std()
    return mid + num_std * std, mid, mid - num_std * std


def atr(df, window=14):
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window).mean()


# ---------------------------------------------------------------------------
# 3) EXTRACCIÓN DE DATOS Y CCL BENCHMARK
# ---------------------------------------------------------------------------
@st.cache_data(ttl=900)
def fetch_history(ticker, period="2y"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if df is None or df.empty: return None
        df.index = df.index.tz_localize(None)
        return df
    except:
        return None


@st.cache_data(ttl=900)
def get_aapl_ccl():
    try:
        hist_c = yf.Ticker("AAPL.BA").history(period="5d")
        hist_u = yf.Ticker("AAPL").history(period="5d")
        if not hist_c.empty and not hist_u.empty:
            return (hist_c["Close"].iloc[-1] * 20) / hist_u["Close"].iloc[-1]
    except:
        pass
    return None


@st.cache_data(ttl=3600)
def get_earnings_status(ticker):
    try:
        cal = yf.Ticker(ticker).get_calendar()
        if cal is not None and not cal.empty and "Earnings Date" in cal.index:
            next_date = cal.loc["Earnings Date"].iloc[0]
            if isinstance(next_date, (pd.Timestamp, datetime)):
                diff = (next_date.date() - datetime.now().date()).days
                if 0 <= diff <= 5: return True, f"Reporte en {diff} días"
    except:
        pass
    return False, ""


@st.cache_data(ttl=14400)  # Se memoriza por 4 horas para máxima velocidad
def get_analyst_consensus(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info

        score = info.get("recommendationMean", None)  # 1.0 (Compra Fuerte) a 5.0 (Venta Fuerte)
        rec_key = info.get("recommendationKey", "N/D").replace("_", " ").title()
        target_price = info.get("targetMeanPrice", None)
        num_analysts = info.get("numberOfAnalystOpinions", None)

        return {
            "score": score,
            "recommendation": rec_key,
            "target_price": target_price,
            "num_analysts": num_analysts
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 4) MOTOR DE ANÁLISIS TÉCNICO Y GESTIÓN DE RIESGO
# ---------------------------------------------------------------------------
def analyze_asset(key, cfg, ccl_real):
    cedear_t, under_t, ratio = cfg["cedear"], cfg["underlying"], cfg["ratio"]

    hist_under = fetch_history(under_t, "2y")
    hist_cedear = fetch_history(cedear_t, "5d")

    if hist_under is None or len(hist_under) < 200: return None

    close_u = hist_under["Close"]
    vol_u = hist_under["Volume"]

    sma10, sma20, sma50, ema200 = sma(close_u, 10), sma(close_u, 20), sma(close_u, 50), ema(close_u, 200)
    rsi14 = rsi(close_u, 14)
    macd_line, macd_signal, _ = macd(close_u)
    boll_up, _, boll_low = bollinger(close_u)
    val_atr = atr(hist_under, 14)

    vol_sma20 = sma(vol_u, 20)
    vol_relativo = (vol_u.iloc[-1] / vol_sma20.iloc[-1]) * 100 if vol_sma20.iloc[-1] > 0 else 100

    precio_usd = close_u.iloc[-1]

    # 1. Filtro Gates Stage 2
    ema200_actual = ema200.iloc[-1]
    ema200_prev = ema200.iloc[-20] if len(ema200) > 20 else ema200.iloc[0]
    gates_stage_2 = (precio_usd > ema200_actual) and (ema200_actual > ema200_prev)

    # 2. Penalizaciones
    penalizaciones = []
    has_earnings, e_msg = get_earnings_status(under_t)
    if has_earnings: penalizaciones.append(f"Balance: {e_msg}")

    caida_hoy = hist_under["Open"].iloc[-1] - precio_usd
    atr_actual = val_atr.iloc[-1] if not np.isnan(val_atr.iloc[-1]) else 0
    if caida_hoy > (2 * atr_actual) and atr_actual > 0: penalizaciones.append("Caída >2x ATR")

    # 3. Lógica de Scoring Técnico (Con Memoria de Corto Plazo y Acción del Precio)
    def score_dia(idx):
        score = 0
        p = close_u.iloc[idx]

        # 1. ESTADO MACRO (La EMA 200)
        if p < ema200.iloc[idx]:
            score -= 2

            # 2. CONTEXTO DE LAS ÚLTIMAS RUEDAS (Momento)
        # Presión bajista de medias rápidas
        if sma10.iloc[idx] < sma20.iloc[idx]:
            # EXCEPCIÓN: Si el precio ya rompió hacia arriba ambas medias, anulamos el castigo
            if p > sma10.iloc[idx] and p > sma20.iloc[idx]:
                pass  # Se perdona el punto negativo
            else:
                score -= 1

        # MACD negativo
        if macd_line.iloc[idx] < macd_signal.iloc[idx]:
            score -= 1

        # 3. GATILLOS DE ENTRADA
        # Cruce Rápido al alza (SMA 10 cruza SMA 20)
        if sma10.iloc[idx - 1] <= sma20.iloc[idx - 1] and sma10.iloc[idx] > sma20.iloc[idx]: score += 2
        # Cruce Confirmación al alza (SMA 10 cruza SMA 50)
        if sma10.iloc[idx - 1] <= sma50.iloc[idx - 1] and sma10.iloc[idx] > sma50.iloc[idx]: score += 2

        # Extremos de Oscilador (RSI)
        r = rsi14.iloc[idx]
        if r <= 35:
            score += 2
        elif r >= 70:
            score -= 2

        # Extremos de Volatilidad (Bollinger)
        if p <= boll_low.iloc[idx]:
            score += 2
        elif p >= boll_up.iloc[idx]:
            score -= 2

        # 4. TRADUCCIÓN DE SEÑAL
        if score >= 2:
            senal = "COMPRA FUERTE"
        elif score == 1:
            senal = "COMPRA"
        elif score <= -2:
            senal = "VENTA"
        elif score <= -3:
            senal = "VENTA FUERTE"
        else:
            senal = "MANTENER"

        return score, senal

    score_prev, senal_prev = score_dia(-2)
    score_act, senal_act = score_dia(-1)

    alerta_giro = None
    if "VENTA" in senal_prev and "COMPRA" in senal_act:
        alerta_giro = "GIRO ALCISTA"
    elif "COMPRA" in senal_prev and "VENTA" in senal_act:
        alerta_giro = "GIRO BAJISTA"

    # ¡SUBIMOS ESTA LÍNEA ACÁ! Calculamos la variación del día antes de tomar decisiones
    chg_1d = (close_u.iloc[-1] / close_u.iloc[-2] - 1) * 100 if len(close_u) > 1 else 0

    # --------------------------------------------------------
    # INTERVENCIÓN SUPREMA DEL VOLUMEN (SMART MONEY)
    # --------------------------------------------------------
    if "COMPRA" in senal_act:
        if vol_relativo > 120:
            senal_act = "COMPRA CONFIRMADA"
        elif vol_relativo < 80:
            senal_act = "FALSA RUPTURA"

    # NUEVA REGLA: Veto a ventas por Ruptura Institucional (Breakout)
    if "VENTA" in senal_act:
        # Si el sistema da venta, pero el activo sube hoy con volumen altísimo, es un Breakout.
        if vol_relativo > 120 and chg_1d > 0:
            senal_act = "MANTENER (BREAKOUT)"

    if penalizaciones and "COMPRA" in senal_act: senal_act = "VETADO (RIESGO)"

    # Precios y CCL (chg_1d ya está calculado arriba, así que lo borramos de acá)
    precio_ars = hist_cedear["Close"].iloc[-1] if (hist_cedear is not None and not hist_cedear.empty) else np.nan
    ccl_imp = (precio_ars * ratio) / precio_usd if not np.isnan(precio_ars) else np.nan
    gap_ccl = (ccl_imp / ccl_real - 1) * 100 if (ccl_real and not np.isnan(ccl_imp)) else np.nan

    return {
        "ticker": key, "nombre": cfg["name"], "precio_usd": round(precio_usd, 2), "chg_1d_%": round(chg_1d, 2),
        "rsi14": rsi14.iloc[-1], "vol_relativo_%": round(vol_relativo, 1),
        "gates_stage_2": gates_stage_2, "penalizaciones": penalizaciones,
        "senal": senal_act, "alerta_giro": alerta_giro,
        "precio_ars": round(precio_ars, 2) if not np.isnan(precio_ars) else "N/D",
        "gap_vs_ccl_%": round(gap_ccl, 2) if not np.isnan(gap_ccl) else "N/D",
        "_hist": hist_under.iloc[-252:],
        "_ind": {
            "sma10": sma10.iloc[-252:], "sma20": sma20.iloc[-252:], "sma50": sma50.iloc[-252:],
            "ema200": ema200.iloc[-252:], "rsi14": rsi14.iloc[-252:], "macd": macd_line.iloc[-252:],
            "macd_signal": macd_signal.iloc[-252:], "boll_up": boll_up.iloc[-252:], "boll_low": boll_low.iloc[-252:],
            "vol_sma20": vol_sma20.iloc[-252:]
        }
    }


# ---------------------------------------------------------------------------
# 5) INTERFAZ NATIVA EN STREAMLIT
# ---------------------------------------------------------------------------
def main():
    st.title("📊 Dashboard Quant Institucional")

    # --- NUEVA LÍNEA DE FECHA Y HORA ---
    st.caption(
        f"⏱️ **Última actualización de precios y métricas:** {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')}")
    st.markdown("---")

    ccl_ref = get_aapl_ccl()
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Benchmark CCL (AAPL)", f"${ccl_ref:.2f}" if ccl_ref else "N/D")
    col_kpi2.metric("Motor Técnico", "100% Subyacente USD")
    col_kpi3.metric("Filtro Estructural", "Gates Stage 2 Activo")

    with st.spinner("Descargando métricas y evaluando riesgos..."):
        results = [analyze_asset(k, v, ccl_ref) for k, v in WATCHLIST.items()]
        results = [r for r in results if r is not None]

    df_res = pd.DataFrame(results)

    # ---------------- RANKINGS ----------------
    st.markdown("---")
    st.markdown("<h3 style='color: #4a69bd;'>🏆 Rankings del Día (USD)</h3>", unsafe_allow_html=True)

    col_g, col_p, col_rs_o, col_rs_u = st.columns(4)

    df_ganadores = df_res.sort_values(by="chg_1d_%", ascending=False).head(5)[["ticker", "chg_1d_%"]].copy()
    df_ganadores["chg_1d_%"] = df_ganadores["chg_1d_%"].apply(lambda x: f"{x}%")

    df_perdedores = df_res.sort_values(by="chg_1d_%", ascending=True).head(5)[["ticker", "chg_1d_%"]].copy()
    df_perdedores["chg_1d_%"] = df_perdedores["chg_1d_%"].apply(lambda x: f"{x}%")

    df_sobrevendidos = df_res.sort_values(by="rsi14", ascending=True).head(5)[["ticker", "rsi14"]].copy()
    df_sobrevendidos["rsi14"] = df_sobrevendidos["rsi14"].apply(lambda x: f"{x:.2f}")  # Forzado a 2 decimales

    df_sobrecomprados = df_res.sort_values(by="rsi14", ascending=False).head(5)[["ticker", "rsi14"]].copy()
    df_sobrecomprados["rsi14"] = df_sobrecomprados["rsi14"].apply(lambda x: f"{x:.2f}")  # Forzado a 2 decimales

    with col_g:
        st.markdown(
            "<div style='background-color: #dff9fb; padding: 5px; border-radius: 5px;'><b style='color: #27ae60;'>🔥 Top Subas</b></div><br>",
            unsafe_allow_html=True)
        st.dataframe(df_ganadores.style.map(pintar_porcentajes), hide_index=True)
    with col_p:
        st.markdown(
            "<div style='background-color: #ffcccc; padding: 5px; border-radius: 5px;'><b style='color: #c0392b;'>🩸 Top Bajas</b></div><br>",
            unsafe_allow_html=True)
        st.dataframe(df_perdedores.style.map(pintar_porcentajes), hide_index=True)
    with col_rs_o:
        st.markdown(
            "<div style='background-color: #e8f7f0; padding: 5px; border-radius: 5px;'><b style='color: #16a085;'>📉 Sobrevendidos (Rebote)</b></div><br>",
            unsafe_allow_html=True)
        st.dataframe(df_sobrevendidos, hide_index=True)
    with col_rs_u:
        st.markdown(
            "<div style='background-color: #fceae8; padding: 5px; border-radius: 5px;'><b style='color: #e74c3c;'>📈 Sobrecomprados (Riesgo)</b></div><br>",
            unsafe_allow_html=True)
        st.dataframe(df_sobrecomprados, hide_index=True)

    st.markdown("---")

    giros = [r for r in results if r["alerta_giro"]]
    if giros:
        st.markdown("<h3 style='color: #e1b12c;'>⚡ Alertas de Reversión Corto Plazo</h3>", unsafe_allow_html=True)
        for g in giros:
            if g["alerta_giro"] == "GIRO ALCISTA":
                st.success(f"🚀 **{g['ticker']} ({g['nombre']})** cruzó al alza (Compra).")
            else:
                st.error(f"⚠️ **{g['ticker']} ({g['nombre']})** cruzó a la baja (Venta).")

    st.markdown("<h3 style='color: #4a69bd;'>📋 Monitor General de Mercado</h3>", unsafe_allow_html=True)

    # Tabla principal con RSI formateado, Precio ARS restituido y Penalizaciones claras
    df_display = pd.DataFrame([{
        "Ticker": r["ticker"],
        "Precio USD": f"${r['precio_usd']}",
        "Var 1D": f"{r['chg_1d_%']}%",
        "RSI": f"{r['rsi14']:.2f}",  # Formato estricto para evitar decimales infinitos
        "Vol Relativo": f"{r['vol_relativo_%']}%",
        "Gates Stage 2": "✅ Sí" if r["gates_stage_2"] else "❌ No",
        "Señal": r["senal"],
        "Penalizaciones": " | ".join(r["penalizaciones"]) if len(r["penalizaciones"]) > 0 else "Ninguna",
        "Precio ARS": f"${r['precio_ars']}",
        "Gap vs CCL": f"{r['gap_vs_ccl_%']}%" if r["gap_vs_ccl_%"] != "N/D" else "N/D"
    } for r in results])

    st.dataframe(df_display.style.map(pintar_senal, subset=["Señal"])
                 .map(pintar_porcentajes, subset=["Var 1D", "Gap vs CCL"])
                 .map(pintar_volumen, subset=["Vol Relativo"]), hide_index=True)

    st.markdown("<h3 style='color: #4a69bd;'>🔍 Análisis Profundo por Activo</h3>", unsafe_allow_html=True)
    ticker_seleccionado = st.selectbox(
        "Seleccioná un activo para desplegar su estructura:", options=[r["ticker"] for r in results],
        format_func=lambda x: f"{x} - {WATCHLIST[x]['name']}"
    )

    data_sel = next(r for r in results if r["ticker"] == ticker_seleccionado)
    hist = data_sel["_hist"]
    ind = data_sel["_ind"]

    # ---------------------------------------------------------------------------
    # COMPARATIVA: NUESTRO MOTOR VS. CONSENSO WALL STREET
    # ---------------------------------------------------------------------------
    st.markdown("#### ⚖️ Nuestro Algoritmo Cuantitativo vs. Consenso Wall Street")

    col_motor, col_gauge = st.columns([1, 1.2])
    consensus = get_analyst_consensus(data_sel["ticker"])

    with col_motor:
        st.markdown(f"**Diagnóstico Técnico (Corto Plazo):**")
        st.subheader(f"📌 {data_sel['senal']}")
        st.write(f"- **Precio USD actual:** ${data_sel['precio_usd']}")
        st.write(f"- **RSI (14):** {float(data_sel['rsi14']):.2f}")
        st.write(f"- **Volumen Relativo:** {data_sel['vol_relativo_%']}%")
        st.write(f"- **Estructura EMA 200 (Stage 2):** {'Alineada' if data_sel['gates_stage_2'] else 'Deteriorada'}")

        # Nota interpretativa automática de divergencia
        if "COMPRA" in data_sel['senal'] and consensus and consensus.get("score") and consensus["score"] <= 2.2:
            st.success("🎯 **Convergencia Fuerte:** Tendencia cuantitativa y visión fundamental coinciden al alza.")
        elif "VENTA" in data_sel['senal'] and consensus and consensus.get("score") and consensus["score"] <= 2.2:
            st.warning(
                "⚠️ **Divergencia de Plazos:** Wall Street es optimista a 12 meses, pero el motor técnico marca deterioro inminente. Riesgo de corto plazo.")

    with col_gauge:
        if consensus and consensus.get("score") is not None:
            # yfinance usa 1=Compra Fuerte a 5=Venta Fuerte. Invertimos para el velocímetro:
            score_visual = 6.0 - consensus["score"]

            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(score_visual, 2),
                number={'valueformat': '.2f', 'suffix': ' / 5.00'},
                title={
                    'text': f"<b>Consenso Analistas ({consensus['recommendation']})</b><br><span style='font-size:0.8em;color:gray;'>Base: {consensus.get('num_analysts', 'N/D')} firmas</span>"},
                gauge={
                    'axis': {'range': [1, 5], 'tickvals': [1, 2, 3, 4, 5],
                             'ticktext': ['Venta Fuerte', 'Venta', 'Conservar', 'Comprar', 'Compra Fuerte']},
                    'bar': {'color': "#2c3e50" if tema_grafico == "Claro ☀️" else "#ecf0f1", 'thickness': 0.28},
                    'steps': [
                        {'range': [1, 1.8], 'color': '#e74c3c'},
                        {'range': [1.8, 2.6], 'color': '#e67e22'},
                        {'range': [2.6, 3.4], 'color': '#f1c40f'},
                        {'range': [3.4, 4.2], 'color': '#2ecc71'},
                        {'range': [4.2, 5.0], 'color': '#27ae60'}
                    ]
                }
            ))
            fig_gauge.update_layout(height=260, margin=dict(t=50, b=10, l=30, r=30), template=bg_color)
            st.plotly_chart(fig_gauge, width="stretch", key=f"gauge_{ticker_seleccionado}")

            if consensus.get("target_price"):
                target = consensus["target_price"]
                upside = ((target / data_sel['precio_usd']) - 1) * 100
                st.caption(
                    f"🎯 **Precio Objetivo a 12 meses:** ${target:.2f} ({'+' if upside >= 0 else ''}{upside:.1f}% vs actual)")
        else:
            st.info("Sin cobertura institucional de analistas para este activo.")

    st.markdown("---")

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.50, 0.15, 0.20, 0.15],
                        subplot_titles=(f"{data_sel['nombre']} ({data_sel['ticker']}) - Cotización USD",
                                        "Volumen Institucional", "RSI (14)", "MACD"))

    # Panel 1: Velas y Medias
    fig.add_trace(
        go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"],
                       name="Precio"), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["sma10"], name="SMA 10", line=dict(color="#00e5ff", width=1.5)), row=1,
                  col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["sma20"], name="SMA 20", line=dict(color="#ffd600", width=1.5)), row=1,
                  col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["sma50"], name="SMA 50", line=dict(color="#ff9100", width=1.5)), row=1,
                  col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["ema200"], name="EMA 200", line=dict(color=ema_color, width=2.5)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["boll_up"], name="Banda Sup", line=dict(color="gray", dash="dot")),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["boll_low"], name="Banda Inf", line=dict(color="gray", dash="dot")),
                  row=1, col=1)

    # Panel 2: Volumen
    colors = ['#26de81' if row['Close'] >= row['Open'] else '#fc5c65' for index, row in hist.iterrows()]
    fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volumen", marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["vol_sma20"], name="Promedio Vol 20d",
                             line=dict(color="#f39c12", width=1.5, dash="dash")), row=2, col=1)

    # Panel 3: RSI
    fig.add_trace(go.Scatter(x=hist.index, y=ind["rsi14"], name="RSI", line=dict(color="#b388ff", width=1.5)), row=3,
                  col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ff5252", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#69f0ae", row=3, col=1)

    # Panel 4: MACD
    fig.add_trace(go.Scatter(x=hist.index, y=ind["macd"], name="MACD", line=dict(color="#448aff", width=1.5)), row=4,
                  col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["macd_signal"], name="Signal", line=dict(color="#ffab40", width=1.5)),
                  row=4, col=1)

    fig.update_layout(height=950, xaxis_rangeslider_visible=False, template=bg_color,
                      margin=dict(t=30, b=20, l=10, r=10))
    st.plotly_chart(fig, width="stretch")


# (Acá termina el código de los paneles del gráfico MACD, RSI, etc.)
    fig.add_trace(go.Scatter(x=hist.index, y=ind["macd_signal"], name="Signal", line=dict(color="#ffab40", width=1.5)), row=4, col=1)

    fig.update_layout(height=950, xaxis_rangeslider_visible=False, template=bg_color, margin=dict(t=30, b=20, l=10, r=10))
 # <--- ¡Verificá que esta línea esté UNA SOLA VEZ!

    # ---------------------------------------------------------------------------
    # GLOSARIO Y METODOLOGÍA (Menú desplegable)
    # ---------------------------------------------------------------------------
    st.markdown("---")
    with st.expander("📚 Glosario de Señales y Metodología Quant (Clic para expandir)"):
        st.markdown("""
        **¿Cómo procesa el algoritmo las decisiones?**
        El sistema asigna un puntaje base evaluando la acción del precio (Cruce de Medias 10/20 y 10/50, RSI, MACD, Bandas de Bollinger) y el régimen de tendencia macro (EMA 200). Luego, pasa ese puntaje por un filtro de Volumen Institucional y Gestión de Riesgo (ATR/Balances).

        * 🟢 **COMPRA / COMPRA FUERTE:** Múltiples indicadores técnicos se alinean al alza dando un puntaje positivo.
        * 🔵 **COMPRA CONFIRMADA:** Señal de Compra + **Alta inyección de capital** (Volumen superior al 120% del promedio). Fuerte respaldo institucional.
        * 🟠 **FALSA RUPTURA:** Señal de Compra + **Bajo interés del mercado** (Volumen inferior al 80% del promedio). Alta probabilidad de trampa alcista (Bull Trap) al carecer de volumen que valide la suba.
        * 🔴 **VETADO (RIESGO):** Operación bloqueada por el motor de riesgo. El activo presenta un balance inminente (< 5 días) o acaba de sufrir una caída violenta (mayor a 2 veces su volatilidad promedio ATR).
        * ⚪ **MANTENER:** Postura neutral (Score 0). Las fuerzas de mercado se anulan entre sí. Si hay liquidez, no se entra. Si ya se posee el activo, se aguarda resolución.
        * 🔻 **VENTA / VENTA FUERTE:** Deterioro técnico múltiple y cruces a la baja. Señal de rotación de capital.
        """)

    # ---------------------------------------------------------------------------
    # DISCLAIMER LEGAL / AVISO PROFESIONAL
    # ---------------------------------------------------------------------------
    st.info(
        "⚠️ **Aviso Legal y de Riesgo:** Este tablero es una herramienta de análisis cuantitativo "
        "diseñada exclusivamente con fines informativos y educativos. Las señales emitidas (Compra/Venta) "
        "son resultados de algoritmos matemáticos y no constituyen una recomendación directa ni personalizada de inversión. "
        "El mercado financiero conlleva riesgos de pérdida de capital. Ante la duda, **consulte a su asesor financiero** "
        "o realice su propio análisis exhaustivo antes de ejecutar cualquier operación."
    )






if __name__ == "__main__":
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        mostrar_login()
    else:
        st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({"autenticado": False}))
        main()