"""Pruebas de la lógica que no depende de Yahoo ni de Streamlit."""

import unittest
from datetime import date

import pandas as pd

from zeta.carteras import composicion, metricas_historicas, pesos_variable
from zeta.senales import (
    ALCISTA_CON_VOLUMEN,
    ALCISTA_SIN_VOLUMEN,
    DISTRIBUCION,
    EN_OBSERVACION_RIESGO,
    EN_OBSERVACION_RUPTURA,
    NEUTRAL,
    SESGO_ALCISTA,
    SESGO_ALCISTA_MARCADO,
    SESGO_BAJISTA,
    SESGO_BAJISTA_MARCADO,
    aplicar_riesgo,
    aplicar_volumen,
    balance_en_ventana,
    dias_hasta_balance,
    etiqueta_por_puntaje,
    giro,
)
from zeta.tiempo import clave_cierre
from zeta.universo import WATCHLIST


class Senales(unittest.TestCase):
    def test_bajista_marcado_es_alcanzable(self):
        self.assertEqual(etiqueta_por_puntaje(-4), SESGO_BAJISTA_MARCADO)
        self.assertEqual(etiqueta_por_puntaje(-3), SESGO_BAJISTA_MARCADO)
        self.assertEqual(etiqueta_por_puntaje(-2), SESGO_BAJISTA)
        self.assertEqual(etiqueta_por_puntaje(-1), NEUTRAL)
        self.assertEqual(etiqueta_por_puntaje(0), NEUTRAL)
        self.assertEqual(etiqueta_por_puntaje(1), SESGO_ALCISTA)
        self.assertEqual(etiqueta_por_puntaje(2), SESGO_ALCISTA)
        self.assertEqual(etiqueta_por_puntaje(3), SESGO_ALCISTA_MARCADO)

    def test_volumen_y_riesgo(self):
        self.assertEqual(aplicar_volumen(SESGO_ALCISTA, 130, 1), ALCISTA_CON_VOLUMEN)
        self.assertEqual(aplicar_volumen(SESGO_ALCISTA_MARCADO, 130, -1), DISTRIBUCION)
        self.assertEqual(aplicar_volumen(SESGO_ALCISTA, 70, 1), ALCISTA_SIN_VOLUMEN)
        self.assertEqual(aplicar_volumen(SESGO_BAJISTA, 140, 1), EN_OBSERVACION_RUPTURA)
        self.assertEqual(aplicar_riesgo(ALCISTA_CON_VOLUMEN, True), EN_OBSERVACION_RIESGO)
        self.assertEqual(aplicar_riesgo(ALCISTA_SIN_VOLUMEN, True), ALCISTA_SIN_VOLUMEN)
        self.assertEqual(giro(SESGO_BAJISTA, SESGO_ALCISTA, 0.4), "Cambio a sesgo alcista")
        self.assertIsNone(giro(SESGO_BAJISTA, SESGO_ALCISTA, -0.2))

    def test_calendario_dict_de_yfinance(self):
        calendario = {"Earnings Date": [date(2026, 11, 2)], "Earnings Average": 1.9}
        self.assertEqual(dias_hasta_balance(calendario, date(2026, 10, 19)), 14)
        self.assertFalse(balance_en_ventana(14))
        self.assertEqual(dias_hasta_balance({"Earnings Date": [date(2026, 10, 22)]}, date(2026, 10, 19)), 3)
        self.assertTrue(balance_en_ventana(3))
        self.assertEqual(dias_hasta_balance({}, date(2026, 10, 19)), None)
        self.assertEqual(dias_hasta_balance(pd.DataFrame(), date(2026, 10, 19)), None)


class Tiempo(unittest.TestCase):
    def test_corte_en_hora_argentina(self):
        zona = "America/Argentina/Buenos_Aires"
        lunes_manana = pd.Timestamp("2026-10-19 10:00", tz=zona)
        lunes_noche = pd.Timestamp("2026-10-19 18:05", tz=zona)
        domingo = pd.Timestamp("2026-10-18 20:00", tz=zona)
        self.assertEqual(clave_cierre(lunes_manana), "2026-10-16")
        self.assertEqual(clave_cierre(lunes_noche), "2026-10-19")
        self.assertEqual(clave_cierre(domingo), "2026-10-16")


class Universo(unittest.TestCase):
    def test_mapeos_corregidos(self):
        self.assertEqual(WATCHLIST["MMM"]["cedear"], "MMM.BA")
        self.assertEqual(WATCHLIST["BAC"]["cedear"], "BA-C.BA")
        self.assertEqual(WATCHLIST["CEG"]["cedear"], "CEG.BA")
        self.assertEqual(WATCHLIST["HAL"]["underlying"], "HAL")
        self.assertEqual(WATCHLIST["BG"]["cedear"], "BNG.BA")
        self.assertEqual(WATCHLIST["SPCX"]["cedear"], "SPCX.BA")
        self.assertEqual(WATCHLIST["MS"]["ratio"], 41)
        self.assertEqual(WATCHLIST["EWJ"]["ratio"], 14)
        self.assertEqual(WATCHLIST["XLC"]["ratio"], 19)
        self.assertNotIn("HALL", WATCHLIST)
        self.assertNotIn("CRWD.BA", [cfg["cedear"] for k, cfg in WATCHLIST.items() if k != "CRWD"])


class Carteras(unittest.TestCase):
    def test_la_torta_cierra_en_cien(self):
        for clave, fija in (("conservador", 65.0), ("agresivo", 30.0)):
            tabla = composicion(clave)
            self.assertAlmostEqual(tabla["Porcentaje"].sum(), 100.0, places=1)
            self.assertEqual(float(tabla.loc[tabla["Activo"] == "Renta fija", "Porcentaje"].iloc[0]), fija)

    def test_metricas_traen_periodo(self):
        idx = pd.bdate_range("2024-01-01", periods=80)
        pasos = range(len(idx))
        precios = pd.DataFrame(
            {
                "AAA": [100 * (1.001 ** i) for i in pasos],
                "BBB": [50 * (1.0005 ** i) for i in pasos],
            },
            index=idx,
        )
        stats = metricas_historicas(precios, {"AAA": 60.0, "BBB": 40.0, "CCC": 10.0})
        self.assertEqual(stats["faltantes"], ["CCC"])
        self.assertGreater(stats["sesiones"], 40)
        self.assertLess(stats["inicio"], stats["fin"])
        self.assertTrue(pd.notna(stats["rendimiento"]))
        self.assertLess(stats["caida_maxima"], 0.01)


if __name__ == "__main__":
    unittest.main()
