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
from zeta.rotacion import (
    SECTORES,
    _bloque,
    _flecha,
    cola_reciente,
    cuadrante,
    curvas_rrg,
    frase_rotacion,
    simbolos_extra,
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


class Rotacion(unittest.TestCase):
    def test_cuadrantes_en_castellano(self):
        self.assertEqual(cuadrante(110, 110), "Líder")
        self.assertEqual(cuadrante(100, 100), "Líder")
        self.assertEqual(cuadrante(110, 99.9), "Debilitándose")
        self.assertEqual(cuadrante(99.9, 110), "Mejorando")
        self.assertEqual(cuadrante(90, 90), "Rezagado")

    def test_la_cola_entra_en_cuatro_a_seis_marcas(self):
        idx = pd.bdate_range("2025-01-01", periods=40)
        curva = pd.DataFrame({"fuerza": range(40), "momentum": range(40)}, index=idx)
        cola = cola_reciente(curva)
        self.assertGreaterEqual(len(cola), 4)
        self.assertLessEqual(len(cola), 6)
        self.assertEqual(cola.index[-1], idx[-1])

    def test_la_flecha_sigue_al_exceso(self):
        self.assertEqual(_flecha(0.02, 0.0), "▲")
        self.assertEqual(_flecha(-0.02, 0.0), "▼")
        self.assertEqual(_flecha(0.001, 0.0), "→")
        idx = pd.bdate_range("2025-06-01", periods=40)
        spy = pd.Series(100.0, index=idx)
        activo = pd.Series(100.0, index=idx)
        activo.iloc[-10:-5] = 101.0
        activo.iloc[-5:] = 110.0
        exceso, flecha = _bloque(activo, spy, 5)
        self.assertGreater(exceso, 0.05)
        self.assertEqual(flecha, "▲")

    def test_la_frase_nombra_quien_entra_y_quien_sale(self):
        sectores = pd.DataFrame(
            [
                {"Nombre": "Tecnología", "Cuadrante": "Líder", "Ritmo": "▲"},
                {"Nombre": "Energía", "Cuadrante": "Debilitándose", "Ritmo": "▼"},
            ]
        )
        frase = frase_rotacion(sectores)
        self.assertIn("Tecnología", frase)
        self.assertIn("Energía", frase)
        self.assertTrue(frase.startswith("Está rotando a favor de"))
        self.assertIn("está saliendo de", frase)
        self.assertIn("No hay datos", frase_rotacion(pd.DataFrame()))

    def test_cada_cedear_mapeado_esta_en_el_panel(self):
        self.assertEqual(simbolos_extra(), ["XLRE", "ARGT"])
        for datos in SECTORES.values():
            for ticker in datos["cedears"]:
                self.assertIn(ticker, WATCHLIST)

    def test_una_serie_que_acelera_queda_lider_y_una_que_cae_rezagada(self):
        n = 260
        idx = pd.bdate_range("2024-01-02", periods=n)
        spy = pd.Series(100.0, index=idx)
        lider = [100 * (1.0003 ** i) for i in range(n)]
        piso = lider[-25]
        for i in range(25):
            lider[-25 + i] = piso * (1.004 ** i)
        curva = curvas_rrg(pd.Series(lider, index=idx), spy)
        fuerza = float(curva["fuerza"].iloc[-1])
        momentum = float(curva["momentum"].iloc[-1])
        self.assertGreater(fuerza, 100)
        self.assertGreater(momentum, 100)
        self.assertEqual(cuadrante(fuerza, momentum), "Líder")

        flojo = [100 * (1.0003 ** i) for i in range(n)]
        techo = flojo[-40]
        for i in range(40):
            flojo[-40 + i] = techo * (0.997 ** i)
        curva_b = curvas_rrg(pd.Series(flojo, index=idx), spy)
        fuerza_b = float(curva_b["fuerza"].iloc[-1])
        momentum_b = float(curva_b["momentum"].iloc[-1])
        self.assertLess(fuerza_b, 100)
        self.assertLess(momentum_b, 100)
        self.assertEqual(cuadrante(fuerza_b, momentum_b), "Rezagado")


if __name__ == "__main__":
    unittest.main()
