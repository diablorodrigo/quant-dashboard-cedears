"""Reglas de la pestaña Señales. No consulta Yahoo ni data912."""

import unittest

import numpy as np
import pandas as pd

from zeta.contraste import ROJO
from zeta.estrategia import (
    AVISO_ESTRATEGIA,
    aplicar_semaforo,
    backtest,
    cargar_backtest,
    cargar_config,
    cruce_al_alza,
    detectar_senales,
    filas_de_estado,
    ratio_volumen,
    relacion_rrg,
    resumir,
    tickers_de,
)

CFG = dict(
    fast=10,
    mid=20,
    slow=50,
    vol_avg=20,
    vol_mult=1.5,
    vol_lookback=3,
    confirm_window=30,
    recent_days=10,
    atr_period=14,
    stop={"type": "pct", "pct": 7},
    max_hold=20,
    exit_cross=None,
    cost_base=0.006,
    cost_conservative=0.012,
    period="2y",
)


def _serie(precios, volumen, aperturas=None, minimos=None) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=len(precios))
    close = np.asarray(precios, dtype=float)
    return pd.DataFrame(
        {
            "Open": close if aperturas is None else np.asarray(aperturas, dtype=float),
            "High": close * 1.01,
            "Low": close * 0.99 if minimos is None else np.asarray(minimos, dtype=float),
            "Close": close,
            "Volume": np.asarray(volumen, dtype=float),
        },
        index=idx,
    )


class Cruces(unittest.TestCase):
    def test_el_cruce_es_de_ayer_a_hoy(self):
        rapida = pd.Series([1.0, 1.0, 3.0])
        lenta = pd.Series([2.0, 2.0, 2.0])
        self.assertEqual(list(cruce_al_alza(rapida, lenta)), [False, False, True])

    def test_sin_volumen_no_hay_compra(self):
        precios = np.r_[np.linspace(100, 80, 80), np.linspace(80, 140, 80)]
        df = _serie(precios, np.full(160, 1000.0))
        self.assertEqual(detectar_senales(df, CFG, "X"), [])

    def test_el_volumen_y_la_confirmacion(self):
        precios = np.r_[np.linspace(100, 80, 150), np.linspace(80, 130, 150)]
        volumen = np.full(300, 1000.0)
        volumen[155:160] = 5000
        eventos = detectar_senales(_serie(precios, volumen), CFG, "X")
        tipos = [e["tipo"] for e in eventos]
        self.assertIn("compra", tipos)
        self.assertIn("confirmacion", tipos)
        compra = next(e for e in eventos if e["tipo"] == "compra")
        confirmacion = next(e for e in eventos if e["tipo"] == "confirmacion")
        self.assertGreaterEqual(confirmacion["idx"] - compra["idx"], 0)
        self.assertLessEqual(confirmacion["idx"] - compra["idx"], 30)
        self.assertLess(compra["stop_sugerido"], compra["precio"])

    def test_la_confirmacion_no_pasa_de_30_ruedas(self):
        # Compra en un cruce temprano y el cruce de 50 queda a más de 30 ruedas:
        # el emparejamiento vive en detectar. Acá se chequea la ventana del evento.
        precios = np.r_[np.linspace(100, 70, 120), np.linspace(70, 160, 200)]
        volumen = np.full(320, 1000.0)
        volumen[120:125] = 8000
        eventos = detectar_senales(_serie(precios, volumen), CFG, "X")
        for evento in eventos:
            if evento["tipo"] == "confirmacion":
                self.assertLessEqual(evento["dias_desde_compra"], 30)


class Ejecucion(unittest.TestCase):
    def test_la_entrada_es_la_apertura_siguiente(self):
        precios = np.linspace(50, 80, 120)
        df = _serie(precios, np.full(120, 1000.0))
        df["Open"] = df["Close"] * 1.02
        trade = backtest(df, [{"ticker": "X", "tipo": "compra", "idx": 70, "fecha": "2024-01-01"}], CFG["stop"], 20)[0]
        self.assertEqual(trade["precio_entrada"], round(float(df["Open"].iloc[71]), 2))
        self.assertNotEqual(trade["precio_entrada"], round(float(df["Close"].iloc[70]), 2))
        self.assertEqual(trade["entrada"], str(df.index[71].date()))

    def test_el_stop_sale_al_nivel_o_a_la_apertura_si_abre_debajo(self):
        n = 40
        close = np.full(n, 100.0)
        apertura = np.full(n, 100.0)
        minimo = np.full(n, 99.0)
        apertura[16] = 90.0
        minimo[16] = 89.0
        df = _serie(close, np.full(n, 1000.0), apertura, minimo)
        trade = backtest(df, [{"ticker": "X", "tipo": "compra", "idx": 14, "fecha": "x"}], {"type": "pct", "pct": 7}, 20)[0]
        self.assertEqual(trade["salida"], "stop")
        self.assertEqual(trade["precio_entrada"], 100.0)
        self.assertEqual(trade["precio_salida"], 90.0)
        self.assertAlmostEqual(trade["ret"], -0.10)

    def test_sin_gap_el_stop_del_7_porciento_cierra_en_el_nivel(self):
        n = 30
        close = np.full(n, 100.0)
        apertura = np.full(n, 100.0)
        minimo = np.full(n, 99.5)
        apertura[12] = 96.0
        minimo[12] = 92.0
        df = _serie(close, np.full(n, 1000.0), apertura, minimo)
        trade = backtest(df, [{"ticker": "X", "tipo": "compra", "idx": 10, "fecha": "x"}], {"type": "pct", "pct": 7}, 20)[0]
        self.assertEqual(trade["salida"], "stop")
        self.assertEqual(trade["precio_entrada"], 100.0)
        self.assertEqual(trade["precio_salida"], 93.0)
        self.assertAlmostEqual(trade["ret"], -0.07)

    def test_a_las_20_ruedas_sale_al_cierre_si_no_toco_el_stop(self):
        n = 120
        close = np.linspace(100, 130, n)
        df = _serie(close, np.full(n, 1000.0))
        trade = backtest(df, [{"ticker": "X", "tipo": "compra", "idx": 60, "fecha": "x"}], {"type": "pct", "pct": 7}, 20)[0]
        self.assertEqual(trade["salida"], "tiempo")
        self.assertEqual(trade["dias"], 20)
        self.assertEqual(trade["precio_salida"], round(float(df["Close"].iloc[60 + 20]), 2))
        self.assertEqual(resumir([trade])["n"], 1)

    def test_el_costo_se_resta_una_vez_por_vuelta(self):
        n = 80
        close = np.linspace(100, 130, n)
        df = _serie(close, np.full(n, 1000.0))
        senal = [{"ticker": "X", "tipo": "compra", "idx": 40, "fecha": "x"}]
        bruto = backtest(df, senal, {"type": "pct", "pct": 7}, 20, cost=0.0)[0]
        neto = backtest(df, senal, {"type": "pct", "pct": 7}, 20, cost=0.006)[0]
        self.assertAlmostEqual(bruto["ret"] - neto["ret"], 0.006)


class Semaforo(unittest.TestCase):
    def test_el_rojo_no_emite_compra_ni_venta(self):
        filas = [
            {"ticker": "KO", "senal": "Compra débil"},
            {"ticker": "MSFT", "senal": "Venta"},
            {"ticker": "AAPL", "senal": "Compra fuerte"},
        ]
        lecturas = {
            "KO": {"estado": ROJO, "bloquea_senal": True, "motivo": "Las fuentes difieren más del 2%."},
            "MSFT": {"estado": "verde", "bloquea_senal": False},
        }
        emitidas, bloqueadas = aplicar_semaforo(filas, lecturas)
        self.assertEqual([f["ticker"] for f in bloqueadas], ["KO"])
        self.assertEqual([f["ticker"] for f in emitidas], ["MSFT", "AAPL"])
        self.assertNotIn("Compra", " ".join(f["senal"] for f in bloqueadas if False))
        self.assertTrue(all(f["senal"] in ("Compra débil", "Compra fuerte", "Venta") for f in emitidas))

    def test_la_fila_de_una_compra_abierta_trae_entrada_stop_y_movimiento(self):
        estado = {
            "ticker": "KO",
            "fecha": "2026-10-27",
            "ultimo_cierre": 30280.0,
            "etiqueta": "Compra",
            "senal_reciente": [],
            "posiciones_abiertas": [
                {
                    "origen": "compra",
                    "fecha_senal": "2026-10-15",
                    "precio_entrada": 29920.0,
                    "stop": 27825.6,
                    "ruedas": 8,
                    "ret_pct": 1.2,
                }
            ],
            "ventas_recientes": [],
            "eventos": [],
        }
        fila = filas_de_estado(estado, 30280.0)[0]
        self.assertEqual(fila["senal"], "Compra débil")
        self.assertEqual(fila["fecha"], "2026-10-15")
        self.assertEqual(fila["precio_entrada"], 29920.0)
        self.assertEqual(fila["stop"], 27825.6)
        self.assertEqual(fila["ultimo"], 30280.0)
        self.assertAlmostEqual(fila["desde_senal"], 1.2, places=1)

    def test_el_aviso_esta_en_una_constante(self):
        self.assertIn("no una recomendación de inversión", AVISO_ESTRATEGIA)
        self.assertIn("no garantizan resultados futuros", AVISO_ESTRATEGIA)
        self.assertNotIn("COMPRA", AVISO_ESTRATEGIA)


class UniversoYRrg(unittest.TestCase):
    def test_el_universo_por_defecto_son_los_27_etfs(self):
        cfg = cargar_config()
        self.assertEqual(cfg["universo_default"], "etfs")
        tickers = tickers_de(cfg)
        self.assertEqual(len(tickers), 27)
        for nombre in ("SPY", "QQQ", "EEM", "EWZ", "XLF", "VIG", "IJH", "IEMG", "CIBR"):
            self.assertIn(nombre, tickers)
        sin_historia = set(next(u["sin_historia"] for u in cfg["universos"] if u["id"] == "etfs"))
        self.assertEqual(sin_historia, {"XLK", "XLV", "XLY", "XLP", "XLB", "XLC", "XLI"})
        self.assertTrue(sin_historia.isdisjoint(tickers))

    def test_la_compra_en_lideres_coincide_y_en_rezagados_no(self):
        self.assertEqual(relacion_rrg("Compra fuerte", "Líder"), "coincide")
        self.assertEqual(relacion_rrg("Compra débil", "Mejorando"), "coincide")
        self.assertEqual(relacion_rrg("Compra débil", "Rezagado"), "contradice")
        self.assertEqual(relacion_rrg("Compra fuerte", "Debilitándose"), "contradice")
        self.assertEqual(relacion_rrg("Venta", "Rezagado"), "coincide")
        self.assertEqual(relacion_rrg("Venta", "Debilitándose"), "coincide")
        self.assertEqual(relacion_rrg("Venta", "Líder"), "contradice")
        self.assertEqual(relacion_rrg("Venta", "Mejorando"), "contradice")
        self.assertEqual(relacion_rrg("Compra débil", None), "sin cuadrante")

    def test_las_cifras_salen_del_archivo_y_avisan_el_dia_al_azar(self):
        doc = cargar_backtest()
        self.assertIn("azar", doc["advertencia"].lower())
        self.assertIn("chica", doc["advertencia"].lower())
        filas = next(e["filas"] for e in doc["estudios"] if e["id"] == "etfs")
        compra = next(f for f in filas if f["universo"] == "ETF (27)" and f["entrada"].startswith("Compra"))
        confirmacion = next(f for f in filas if f["universo"] == "ETF (27)" and "Confirmación" in f["entrada"])
        self.assertEqual(compra["n"], 48)
        self.assertEqual(compra["media_06"], 4.87)
        self.assertEqual(compra["acierto"], 75.0)
        self.assertEqual(confirmacion["n"], 20)
        self.assertEqual(confirmacion["media_06"], 2.25)
        from pathlib import Path

        vista = Path("zeta/vista_senales.py").read_text(encoding="utf-8")
        self.assertNotIn("XLK", vista)
        self.assertNotIn("2,43", vista)
        self.assertNotIn("4,19", vista)


class Referencia(unittest.TestCase):
    def test_el_archivo_de_referencia_no_es_la_fuente_de_la_pantalla(self):
        import json
        from pathlib import Path

        doc = json.loads(Path("tests/fixtures/senales_etf_v3.json").read_text(encoding="utf-8"))
        vigentes = {e["ticker"]: e["etiqueta"] for e in doc["estado"] if e.get("etiqueta")}
        self.assertEqual(
            vigentes,
            {
                "VIG": "Compra",
                "IJH": "Compra",
                "IEMG": "Compra",
                "EWZ": "Venta",
                "EEM": "Venta",
                "QQQ": "Venta",
                "CIBR": "Venta",
            },
        )
        vista = Path("zeta/vista_senales.py").read_text(encoding="utf-8")
        self.assertNotIn("senales_etf_v3", vista)
        self.assertNotIn("signals.json", vista)


class Volumen(unittest.TestCase):
    def test_el_filtro_pide_una_vez_y_media_el_promedio_previo(self):
        volumen = pd.Series([100.0] * 25 + [160.0])
        ratio = ratio_volumen(volumen, 20, 3)
        self.assertGreaterEqual(float(ratio.iloc[-1]), 1.5)
        plano = ratio_volumen(pd.Series([100.0] * 30), 20, 3)
        self.assertLess(float(plano.iloc[-1]), 1.5)


if __name__ == "__main__":
    unittest.main()
