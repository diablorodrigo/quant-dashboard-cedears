"""Reglas de la pestaña Señales. No consulta Yahoo ni data912."""

import unittest

import numpy as np
import pandas as pd

from zeta.contraste import ROJO
from zeta.estrategia import (
    AVISO_CONTEXTO,
    AVISO_ESTRATEGIA,
    aplicar_semaforo,
    backtest,
    cargar_backtest,
    cargar_config,
    consolidar_filas,
    cruce_al_alza,
    detectar_senales,
    estado_ticker,
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
        self.assertIn("propio análisis", AVISO_ESTRATEGIA)
        self.assertNotIn("COMPRA", AVISO_ESTRATEGIA)
        self.assertEqual(
            AVISO_CONTEXTO,
            "Es una guía de contexto, no una promesa. Las señales se basan en análisis cuantitativo.",
        )
        self.assertNotIn("azar", AVISO_CONTEXTO.lower())


class UniversoYRrg(unittest.TestCase):
    def test_el_universo_por_defecto_son_los_37_etfs(self):
        from zeta.estrategia import especies_de

        cfg = cargar_config()
        self.assertEqual(cfg["universo_default"], "etfs")
        tickers = tickers_de(cfg)
        self.assertEqual(len(tickers), 37)
        for nombre in ("SPY", "QQQ", "EEM", "EWZ", "XLK", "XLP", "XLB", "XLRE", "VEA", "IVE"):
            self.assertIn(nombre, tickers)
        especies = {e["ticker"]: e for e in especies_de(cfg)}
        self.assertEqual(especies["XLK"]["simbolo_yahoo"], "XLKD.BA")
        self.assertEqual(especies["XLK"]["simbolo_data912"], "XLKD")
        self.assertEqual(especies["XLK"]["moneda"], "USD MEP")
        self.assertEqual(especies["SPY"]["moneda"], "ARS")
        self.assertEqual(especies["SPY"]["simbolo_data912"], "SPY")
        self.assertEqual(next(u["sin_historia"] for u in cfg["universos"] if u["id"] == "etfs"), [])

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
        compra = next(f for f in filas if f["universo"].startswith("ETF 37") and f["entrada"] == "compra" and f["costo"] == "0,6%")
        confirmacion = next(f for f in filas if f["universo"].startswith("ETF 37") and f["entrada"] == "confirmacion" and f["costo"] == "0,6%")
        nuevos = next(f for f in filas if f["universo"].startswith("10 nuevos") and f["entrada"] == "compra" and f["costo"] == "0,6%")
        self.assertEqual(compra["n"], 78)
        self.assertEqual(compra["media"], 3.01)
        self.assertEqual(compra["acierto"], 66.7)
        self.assertEqual(confirmacion["n"], 36)
        self.assertEqual(confirmacion["media"], 0.87)
        self.assertEqual(nuevos["media"], 0.04)
        from pathlib import Path

        vista = Path("zeta/vista_senales.py").read_text(encoding="utf-8")
        self.assertNotIn("sin historia en pesos", vista)
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
                "XLP": "Compra",
                "XLB": "Compra",
                "EWZ": "Venta",
                "EEM": "Venta",
                "QQQ": "Venta",
                "CIBR": "Venta",
            },
        )
        vista = Path("zeta/vista_senales.py").read_text(encoding="utf-8")
        self.assertNotIn("senales_etf_v3", vista)
        self.assertNotIn("signals.json", vista)


class UnaFilaPorEtf(unittest.TestCase):
    def test_la_debil_que_se_confirma_queda_en_una_fila_fuerte(self):
        # El caso de XLP: la compra del 15/10 y la confirmación del 19/10
        # son la misma posición. La entrada no se reinicia.
        estado = {
            "ticker": "XLP",
            "fecha": "2026-10-27",
            "ultimo_cierre": 5.80,
            "etiqueta": "Compra",
            "senal_reciente": [
                {"tipo": "compra", "fecha": "2026-10-15", "idx": 100},
                {"tipo": "confirmacion", "fecha": "2026-10-19", "idx": 104, "dias_desde_compra": 4},
            ],
            "posiciones_abiertas": [
                {
                    "origen": "compra",
                    "fecha_senal": "2026-10-15",
                    "precio_entrada": 5.72,
                    "stop": 5.32,
                    "ruedas": 8,
                    "idx": 100,
                },
                {
                    "origen": "confirmacion",
                    "fecha_senal": "2026-10-19",
                    "precio_entrada": 5.76,
                    "stop": 5.36,
                    "ruedas": 6,
                    "idx": 104,
                    "idx_compra": 100,
                },
            ],
            "ventas_recientes": [],
            "eventos": [],
        }
        filas = filas_de_estado(estado, 5.80)
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila["ticker"], "XLP")
        self.assertEqual(fila["senal"], "Compra fuerte")
        self.assertEqual(fila["fuerza"], "fuerte")
        self.assertEqual(fila["fecha"], "2026-10-15")
        self.assertEqual(fila["fecha_confirmacion"], "2026-10-19")
        self.assertEqual(fila["precio_entrada"], 5.72)
        self.assertEqual(fila["stop"], 5.32)
        self.assertEqual(fila["ruedas"], 8)
        self.assertEqual(fila["desde_senal"], 1.40)
        self.assertIn("2026-10-15", fila["detalle"])
        self.assertIn("2026-10-19", fila["detalle"])
        self.assertIn("misma posición", fila["detalle"])
        self.assertEqual(relacion_rrg(fila["senal"], "Líder"), "coincide")

    def test_la_confirmacion_de_hoy_no_abre_otra_fila(self):
        estado = {
            "ticker": "XLP",
            "fecha": "2026-10-27",
            "ultimo_cierre": 5.80,
            "etiqueta": "Compra",
            "senal_reciente": [
                {"tipo": "confirmacion", "fecha": "2026-10-27", "idx": 108, "dias_desde_compra": 8},
            ],
            "posiciones_abiertas": [
                {
                    "origen": "compra",
                    "fecha_senal": "2026-10-15",
                    "precio_entrada": 5.72,
                    "stop": 5.32,
                    "ruedas": 8,
                    "idx": 100,
                }
            ],
            "ventas_recientes": [],
            "eventos": [],
        }
        filas = filas_de_estado(estado, 5.80)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["senal"], "Compra fuerte")
        self.assertEqual(filas[0]["fecha"], "2026-10-15")
        self.assertEqual(filas[0]["fecha_confirmacion"], "2026-10-27")
        self.assertEqual(filas[0]["precio_entrada"], 5.72)
        self.assertEqual(filas[0]["ruedas"], 8)
        self.assertEqual(filas[0]["estado_posicion"], "abierta")

    def test_etfs_sin_duplicar_siguen_con_una_fila_cada_uno(self):
        debil = {
            "ticker": "IJH",
            "fecha": "2026-10-27",
            "ultimo_cierre": 10120.0,
            "etiqueta": "Compra",
            "senal_reciente": [],
            "posiciones_abiertas": [
                {
                    "origen": "compra",
                    "fecha_senal": "2026-10-06",
                    "precio_entrada": 9835.0,
                    "stop": 9146.55,
                    "ruedas": 13,
                }
            ],
            "ventas_recientes": [],
            "eventos": [],
        }
        venta = {
            "ticker": "EWZ",
            "fecha": "2026-10-27",
            "ultimo_cierre": 28520.0,
            "etiqueta": "Venta",
            "senal_reciente": [],
            "posiciones_abiertas": [],
            "ventas_recientes": [
                {
                    "ticker": "EWZ",
                    "fecha": "2026-10-26",
                    "fecha_senal": "2026-10-05",
                    "origen": "compra",
                    "motivo": "stop",
                    "precio_salida": 26600.0,
                    "precio_entrada": 34720.0,
                    "stop": 32289.6,
                    "ret_pct": -23.39,
                    "ruedas": 15,
                    "idx": 40,
                }
            ],
            "eventos": [],
        }
        filas = filas_de_estado(debil, 10120.0) + filas_de_estado(venta, 28520.0)
        self.assertEqual([f["ticker"] for f in filas], ["IJH", "EWZ"])
        self.assertEqual(filas[0]["senal"], "Compra débil")
        self.assertIsNone(filas[0]["fecha_confirmacion"])
        self.assertEqual(filas[0]["fecha"], "2026-10-06")
        self.assertEqual(filas[0]["precio_entrada"], 9835.0)
        self.assertEqual(filas[0]["ruedas"], 13)
        self.assertEqual(filas[1]["senal"], "Venta")
        self.assertEqual(filas[1]["fecha"], "2026-10-26")
        self.assertIsNone(filas[1]["fecha_confirmacion"])
        self.assertEqual(len({f["ticker"] for f in filas}), len(filas))
        fuertes = sum(1 for f in filas if f["fuerza"] == "fuerte")
        debiles = sum(1 for f in filas if f["fuerza"] == "debil")
        self.assertEqual((fuertes, debiles), (0, 1))

    def test_dos_ventas_de_la_misma_cadena_son_una_sola(self):
        estado = {
            "ticker": "QQQ",
            "fecha": "2026-10-27",
            "ultimo_cierre": 100.0,
            "etiqueta": "Venta",
            "senal_reciente": [],
            "posiciones_abiertas": [],
            "ventas_recientes": [
                {
                    "ticker": "QQQ",
                    "fecha": "2026-10-20",
                    "fecha_senal": "2026-09-21",
                    "origen": "compra",
                    "motivo": "tiempo",
                    "precio_salida": 110.0,
                    "precio_entrada": 100.0,
                    "stop": 93.0,
                    "ret_pct": 10.0,
                    "ruedas": 20,
                    "idx": 10,
                },
                {
                    "ticker": "QQQ",
                    "fecha": "2026-10-24",
                    "fecha_senal": "2026-10-01",
                    "origen": "confirmacion",
                    "motivo": "tiempo",
                    "precio_salida": 115.0,
                    "precio_entrada": 105.0,
                    "stop": 97.0,
                    "ret_pct": 9.0,
                    "ruedas": 16,
                    "idx": 18,
                    "idx_compra": 10,
                },
            ],
            "eventos": [],
        }
        filas = filas_de_estado(estado, 100.0)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["senal"], "Venta")
        self.assertEqual(filas[0]["fecha"], "2026-10-20")
        self.assertEqual(filas[0]["precio_entrada"], 100.0)
        self.assertEqual(filas[0]["precio_salida"], 110.0)
        self.assertEqual(filas[0]["fecha_confirmacion"], "2026-10-01")
        self.assertIn("2026-09-21", filas[0]["detalle"])
        self.assertIn("2026-10-01", filas[0]["detalle"])

    def test_dos_compras_sueltas_dejan_la_mas_reciente(self):
        filas = consolidar_filas(
            [
                {
                    "ticker": "DIA",
                    "senal": "Compra débil",
                    "fuerza": "debil",
                    "origen": "compra",
                    "fecha": "2026-10-01",
                    "estado_posicion": "abierta",
                    "precio_entrada": 100.0,
                    "idx": 1,
                },
                {
                    "ticker": "DIA",
                    "senal": "Compra débil",
                    "fuerza": "debil",
                    "origen": "compra",
                    "fecha": "2026-10-20",
                    "estado_posicion": "abierta",
                    "precio_entrada": 110.0,
                    "idx": 2,
                },
            ]
        )
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["fecha"], "2026-10-20")
        self.assertEqual(filas[0]["senal"], "Compra débil")

    def test_etfs_distintos_no_se_pisan(self):
        filas = consolidar_filas(
            [
                {
                    "ticker": "IJH",
                    "senal": "Compra débil",
                    "fuerza": "debil",
                    "origen": "compra",
                    "fecha": "2026-10-06",
                    "estado_posicion": "abierta",
                    "precio_entrada": 9835.0,
                },
                {
                    "ticker": "XLP",
                    "senal": "Compra débil",
                    "fuerza": "debil",
                    "origen": "compra",
                    "fecha": "2026-10-15",
                    "estado_posicion": "abierta",
                    "precio_entrada": 5.72,
                },
                {
                    "ticker": "EWZ",
                    "senal": "Venta",
                    "fuerza": None,
                    "origen": "compra",
                    "fecha": "2026-10-26",
                    "estado_posicion": "cerrada",
                    "precio_entrada": 34720.0,
                },
            ]
        )
        self.assertEqual({f["ticker"]: f["senal"] for f in filas}, {
            "IJH": "Compra débil",
            "XLP": "Compra débil",
            "EWZ": "Venta",
        })

    def test_el_conteo_y_el_rombo_usan_la_etiqueta_avanzada(self):
        from zeta.vista_senales import _marcas_rrg

        estado = {
            "ticker": "XLP",
            "fecha": "2026-10-27",
            "ultimo_cierre": 5.80,
            "etiqueta": "Compra",
            "senal_reciente": [],
            "posiciones_abiertas": [
                {
                    "origen": "compra",
                    "fecha_senal": "2026-10-15",
                    "precio_entrada": 5.72,
                    "stop": 5.32,
                    "ruedas": 8,
                    "idx": 100,
                },
                {
                    "origen": "confirmacion",
                    "fecha_senal": "2026-10-19",
                    "precio_entrada": 5.76,
                    "stop": 5.36,
                    "ruedas": 6,
                    "idx": 104,
                    "idx_compra": 100,
                },
            ],
            "ventas_recientes": [],
            "eventos": [],
        }
        xlp = filas_de_estado(estado, 5.80)
        ijh = filas_de_estado(
            {
                "ticker": "IJH",
                "fecha": "2026-10-27",
                "ultimo_cierre": 10120.0,
                "etiqueta": "Compra",
                "senal_reciente": [],
                "posiciones_abiertas": [
                    {
                        "origen": "compra",
                        "fecha_senal": "2026-10-06",
                        "precio_entrada": 9835.0,
                        "stop": 9146.55,
                        "ruedas": 13,
                    }
                ],
                "ventas_recientes": [],
                "eventos": [],
            },
            10120.0,
        )
        abiertas = xlp + ijh
        self.assertEqual(sum(1 for f in abiertas if f["fuerza"] == "fuerte"), 1)
        self.assertEqual(sum(1 for f in abiertas if f["fuerza"] == "debil"), 1)
        self.assertEqual(len({f["ticker"] for f in abiertas}), 2)
        for fila in abiertas:
            fila["cuadrante"] = "Líderes"
            fila["rrg"] = relacion_rrg(fila["senal"], "Líder")
        marcas = _marcas_rrg(abiertas, {"XLP": "Líder", "IJH": "Líder"})
        por_ticker = {m["ticker"]: m for m in marcas}
        self.assertEqual(set(por_ticker), {"XLP", "IJH"})
        self.assertEqual(por_ticker["XLP"]["senal"], "Compra fuerte")
        self.assertEqual(por_ticker["IJH"]["senal"], "Compra débil")
        self.assertEqual(por_ticker["XLP"]["relacion"], "coincide")

    def test_en_el_universo_de_referencia_solo_vig_xlp_y_xlb_venian_duplicados(self):
        import json
        from pathlib import Path

        doc = json.loads(Path("tests/fixtures/senales_etf_v3.json").read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(estado["ticker"] for estado in doc["estado"]),
            sorted(tickers_de(cargar_config())),
        )
        duplicados = []
        filas = []
        for estado in doc["estado"]:
            abiertas = estado.get("posiciones_abiertas") or []
            ventas = estado.get("ventas_recientes") or []
            self.assertLessEqual(len(ventas), 1, estado["ticker"])
            if len(abiertas) > 1 or len(ventas) > 1:
                duplicados.append(estado["ticker"])
            if estado.get("etiqueta") != "Compra":
                continue
            hechas = filas_de_estado(estado, estado.get("ultimo_cierre"))
            self.assertLessEqual(len(hechas), 1, estado["ticker"])
            filas.extend(hechas)
        self.assertEqual(duplicados, ["XLP", "XLB", "VIG"])
        self.assertEqual(len({f["ticker"] for f in filas}), len(filas))
        por_ticker = {f["ticker"]: f for f in filas}
        for ticker, compra, confirmacion in (
            ("XLP", "2026-10-15", "2026-10-19"),
            ("XLB", "2026-10-16", "2026-10-26"),
            ("VIG", "2026-10-02", "2026-10-15"),
        ):
            fila = por_ticker[ticker]
            self.assertEqual(fila["senal"], "Compra fuerte")
            self.assertEqual(fila["fecha"], compra)
            self.assertEqual(fila["fecha_confirmacion"], confirmacion)
        # Los que ya tenían una sola señal no cambian de etiqueta.
        self.assertEqual(por_ticker["IJH"]["senal"], "Compra débil")
        self.assertEqual(por_ticker["IEMG"]["senal"], "Compra débil")
        self.assertIsNone(por_ticker["IJH"]["fecha_confirmacion"])
        ventas = {
            estado["ticker"]
            for estado in doc["estado"]
            if estado.get("etiqueta") == "Venta" and len(estado.get("ventas_recientes") or []) == 1
        }
        self.assertEqual(ventas, {"EWZ", "QQQ", "EEM", "CIBR"})

    def test_la_serie_no_duplica_ni_inventa_una_confirmacion(self):
        precios = np.r_[np.linspace(100, 80, 150), np.linspace(80, 130, 150)]
        volumen = np.full(300, 1000.0)
        volumen[155:160] = 5000
        df = _serie(precios, volumen)
        eventos = detectar_senales(df, CFG, "XLP")
        confirmacion = next(e for e in eventos if e["tipo"] == "confirmacion")
        compra = next(e for e in eventos if e["idx"] == confirmacion["idx"] - confirmacion["dias_desde_compra"])
        self.assertGreater(confirmacion["idx"], compra["idx"])

        # El motor del backtest sigue contando las dos entradas. La tabla, no.
        trades = backtest(df, [compra, confirmacion], CFG["stop"], CFG["max_hold"], cfg=CFG)
        self.assertEqual(sorted(t["tipo"] for t in trades), ["compra", "confirmacion"])

        if confirmacion["idx"] > compra["idx"] + 1:
            solo_debil = df.iloc[: compra["idx"] + 2]
            estado = estado_ticker("XLP", solo_debil, CFG)
            filas = [f for f in filas_de_estado(estado) if f["estado_posicion"] != "cerrada"]
            self.assertEqual([f["senal"] for f in filas], ["Compra débil"])
            self.assertEqual(filas[0]["fecha"], compra["fecha"])
            self.assertIsNone(filas[0]["fecha_confirmacion"])

        # Mientras la compra original sigue abierta, la confirmación no suma otra fila.
        # len <= compra_idx + max_hold deja esa entrada abierta (ver backtest).
        ultimo_abierto = compra["idx"] + int(CFG["max_hold"])
        if confirmacion["idx"] + 2 <= ultimo_abierto:
            con_fuerte = df.iloc[: min(confirmacion["idx"] + 4, ultimo_abierto)]
            estado = estado_ticker("XLP", con_fuerte, CFG)
            filas = [f for f in filas_de_estado(estado) if f["estado_posicion"] != "cerrada"]
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["senal"], "Compra fuerte")
            self.assertEqual(filas[0]["fecha"], compra["fecha"])
            self.assertEqual(filas[0]["fecha_confirmacion"], confirmacion["fecha"])
            self.assertEqual(filas[0]["ticker"], "XLP")
        else:
            con_fuerte = df.iloc[: confirmacion["idx"] + 4]
            estado = estado_ticker("XLP", con_fuerte, CFG)
            filas = filas_de_estado(estado)
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["ticker"], "XLP")


class Volumen(unittest.TestCase):
    def test_el_filtro_pide_una_vez_y_media_el_promedio_previo(self):
        volumen = pd.Series([100.0] * 25 + [160.0])
        ratio = ratio_volumen(volumen, 20, 3)
        self.assertGreaterEqual(float(ratio.iloc[-1]), 1.5)
        plano = ratio_volumen(pd.Series([100.0] * 30), 20, 3)
        self.assertLess(float(plano.iloc[-1]), 1.5)


if __name__ == "__main__":
    unittest.main()
