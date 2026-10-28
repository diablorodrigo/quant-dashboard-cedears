"""Armado del universo. Los precios de la prueba son fijos: no consulta APIs."""

import unittest

import pandas as pd

from zeta.universo import (
    ESTADO_NO,
    ESTADO_OK,
    WATCHLIST,
    armar_universo,
    elegir_ratio,
    es_variante_dolar,
    guardar_universo,
    incorporar_faltantes,
    simbolo_byma,
    simbolos_pesos,
    usa_ratio,
    yahoo_cedear,
)


def _q(precio, volumen=1000, bid=None, ask=None):
    return {"c": precio, "v": volumen, "px_bid": bid if bid is not None else precio * 0.99, "px_ask": ask if ask is not None else precio * 1.01, "pct_change": 0}


class Simbolos(unittest.TestCase):
    def test_bac_en_dolares_no_es_el_cedear_en_pesos(self):
        precios = {"BA": 11460.0, "BAC": 7.19, "BA.C": 21040.0, "BB": 5195.0, "BBD": 4630.0, "MU": 321100.0, "MUD": 206.0}
        self.assertTrue(es_variante_dolar("BAC", precios))
        self.assertTrue(es_variante_dolar("MUD", precios))
        self.assertFalse(es_variante_dolar("BA.C", precios))
        self.assertFalse(es_variante_dolar("BBD", precios))
        self.assertIn("BA.C", simbolos_pesos({k: _q(v) for k, v in precios.items()}))
        self.assertNotIn("BAC", simbolos_pesos({k: _q(v) for k, v in precios.items()}))

    def test_el_ticker_de_yahoo_cambia_el_punto_por_un_guion(self):
        self.assertEqual(simbolo_byma("BA-C.BA"), "BA.C")
        self.assertEqual(yahoo_cedear("BA.C"), "BA-C.BA")
        self.assertEqual(yahoo_cedear("BNG"), "BNG.BA")


class Ratios(unittest.TestCase):
    def test_un_ratio_ambiguo_no_se_inventa(self):
        self.assertIsNone(elegir_ratio(10.4))
        self.assertEqual(elegir_ratio(4.02), 4)
        self.assertEqual(elegir_ratio(0.5), 0.5)

    def test_el_manual_se_verifica_y_el_nuevo_solo_si_es_unico_y_liquido(self):
        ccl = 1650.0
        # AAPL: 28660 * 20 / 347 ≈ 1651. BA.C: 21040 * 4 / 50.9 ≈ 1653.
        cotizaciones = {
            "AAPL": _q(28660),
            "BA.C": _q(21040),
            "BNG": _q(33540),
            "IBM": _q(5155, volumen=1000),
            "RARO": _q(1000, volumen=0),
        }
        manual = {
            "AAPL": {"name": "Apple", "cedear": "AAPL.BA", "underlying": "AAPL", "ratio": 20, "rubro": "Tecnología"},
            "BAC": {"name": "Bank of America", "cedear": "BA-C.BA", "underlying": "BAC", "ratio": 4, "rubro": "Finanzas"},
            "BG": {"name": "Bunge", "cedear": "BNG.BA", "underlying": "BG", "ratio": 5, "rubro": "Consumo"},
        }
        # IBM implícito: 25.09 * 1650 / 5155 ≈ 8.03 → ratio 8.
        precios = {"AAPL": 347.0, "BAC": 50.9, "BG": 101.66, "IBM": 25.09}
        universo = armar_universo(
            cotizaciones,
            manual,
            precios,
            ccl,
            sectores_yahoo={"AAPL": "Tecnología", "BAC": "Finanzas", "BG": "Consumo", "IBM": "Tecnología"},
            nombres_yahoo={"IBM": "International Business Machines"},
        )
        self.assertEqual(universo["BAC"]["estado"], ESTADO_OK)
        self.assertEqual(universo["BAC"]["cedear"], "BA-C.BA")
        self.assertEqual(universo["BG"]["cedear"], "BNG.BA")
        self.assertTrue(usa_ratio(universo["AAPL"]))
        self.assertEqual(universo["IBM"]["estado"], ESTADO_OK)
        self.assertEqual(universo["IBM"]["ratio"], 8)
        self.assertEqual(universo["IBM"]["name"], "International Business Machines")
        self.assertEqual(universo["RARO"]["estado"], ESTADO_NO)
        self.assertIsNone(universo["RARO"]["ratio"])
        self.assertFalse(usa_ratio(universo["RARO"]))

    def test_un_ticker_nuevo_del_feed_entra_sin_ratio(self):
        base = {"AAPL": {"name": "Apple", "cedear": "AAPL.BA", "byma": "AAPL", "estado": ESTADO_OK, "ratio": 20, "rubro": "Tecnología", "underlying": "AAPL", "sector_estado": ESTADO_OK, "origen": "manual", "motivo": ""}}
        salida = incorporar_faltantes(base, ["AAPL", "ZZZZ"])
        self.assertEqual(salida["ZZZZ"]["estado"], ESTADO_NO)
        self.assertIsNone(salida["ZZZZ"]["ratio"])
        self.assertIn("AAPL", salida)

    def test_el_csv_redondo_no_pierde_el_estado(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from zeta.universo import cargar_universo

        universo = {
            "IBM": {
                "name": "IBM",
                "cedear": "IBM.BA",
                "underlying": "IBM",
                "ratio": 8,
                "rubro": "Tecnología",
                "estado": ESTADO_OK,
                "sector_estado": ESTADO_OK,
                "byma": "IBM",
                "origen": "consistencia",
                "motivo": "ok",
            }
        }
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "u.csv"
            guardar_universo(universo, ruta)
            cargado = cargar_universo(ruta)
        self.assertEqual(cargado["IBM"]["ratio"], 8)
        self.assertEqual(cargado["IBM"]["estado"], ESTADO_OK)


class ListaPublicada(unittest.TestCase):
    def test_el_universo_publicado_separa_verificados(self):
        from zeta.universo import cargar_universo

        universo = cargar_universo()
        verificados = [cfg for cfg in universo.values() if cfg["estado"] == ESTADO_OK]
        sin_verificar = [cfg for cfg in universo.values() if cfg["estado"] != ESTADO_OK]
        self.assertGreaterEqual(len(universo), 400)
        self.assertGreaterEqual(len(verificados), 200)
        self.assertGreaterEqual(len(sin_verificar), 50)
        self.assertTrue(all(cfg["ratio"] not in (None, "") for cfg in verificados))
        self.assertTrue(all(cfg["ratio"] is None for cfg in sin_verificar))
        self.assertEqual(universo["BAC"]["cedear"], "BA-C.BA")
        self.assertEqual(universo["BAC"]["estado"], ESTADO_OK)
        self.assertEqual(universo["BG"]["cedear"], "BNG.BA")
        self.assertEqual(universo["BG"]["estado"], ESTADO_OK)
        self.assertNotIn("COMPRA", " ".join(cfg["name"] for cfg in universo.values()))
        self.assertNotIn("VENTA", " ".join(cfg["name"] for cfg in universo.values()))
        from zeta.universo import cargar_acciones

        acciones = cargar_acciones()
        self.assertEqual(acciones["GGAL"]["panel"], "lider")
        self.assertEqual(acciones["GGAL"]["sector_estado"], ESTADO_OK)
        self.assertGreaterEqual(len(acciones), 90)


class Acciones(unittest.TestCase):
    def test_variacion_e_indice(self):
        from zeta.acciones_ar import indice_equitativo, variacion_ruedas

        serie = pd.Series([100, 110, 121], index=pd.bdate_range("2026-01-01", periods=3))
        self.assertAlmostEqual(variacion_ruedas(serie, 2), 0.21)
        self.assertIsNone(variacion_ruedas(serie, 5))
        precios = pd.DataFrame({"A": [100, 110], "B": [100, 90]})
        nivel = indice_equitativo(precios)
        self.assertAlmostEqual(float(nivel.iloc[0]), 1.0)
        self.assertAlmostEqual(float(nivel.iloc[-1]), 1.0, places=6)

    def test_el_contraste_rojo_no_entra_al_mapa(self):
        from zeta.acciones_ar import filas_acciones

        filas = filas_acciones(
            {"GGAL": {"c": 100, "pct_change": 0, "v": 10}},
            {"GGAL": {"name": "Galicia", "rubro": "Finanzas", "panel": "lider", "sector_estado": ESTADO_OK}},
            {"GGAL": 120},
            yahoo_es_hoy={"GGAL": True},
            edad_minutos=1,
            mercado_abierto=True,
        )
        self.assertEqual(filas[0]["contraste"], "rojo")
        self.assertFalse(filas[0]["entra_mapa"])


class Ensamble(unittest.TestCase):
    def test_el_rojo_no_calcula_la_senal(self):
        from zeta.datos import ensamblar_panel

        hoy = pd.Timestamp("2026-10-28")
        indice = pd.bdate_range(end=hoy, periods=40)
        usd = pd.DataFrame(
            {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": [100 + i * 0.2 for i in range(40)], "Volume": 1_000_000},
            index=indice,
        )
        ars = pd.DataFrame(
            {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1_000},
            index=indice,
        )
        cfg = {
            "name": "Apple",
            "cedear": "AAPL.BA",
            "underlying": "AAPL",
            "ratio": 20,
            "rubro": "Tecnología",
            "estado": ESTADO_OK,
            "sector_estado": ESTADO_OK,
            "byma": "AAPL",
            "origen": "manual",
            "motivo": "",
        }
        panel = ensamblar_panel(
            {"AAPL": cfg},
            {"AAPL": usd},
            {"AAPL.BA": ars},
            [],
            [],
            {"AAPL": {"c": 130, "pct_change": 0, "v": 10}},
            None,
            mercado_abierto=True,
            hoy=hoy,
            edad_minutos=1,
            ccl_feed=1650,
            momento=hoy,
        )
        self.assertTrue(panel["filas"].empty)
        self.assertEqual(panel["sin_senal"].iloc[0]["lectura"], "Sin señal")
        self.assertNotIn("COMPRA", panel["sin_senal"].iloc[0]["lectura"])
        self.assertNotIn("VENTA", panel["sin_senal"].iloc[0]["lectura"])


class ListaCargada(unittest.TestCase):
    def test_el_csv_a_mano_conserva_los_simbolos_revisados(self):
        self.assertEqual(WATCHLIST["BAC"]["cedear"], "BA-C.BA")
        self.assertEqual(WATCHLIST["BG"]["cedear"], "BNG.BA")
        self.assertEqual(WATCHLIST["MMM"]["cedear"], "MMM.BA")
        self.assertNotIn("Aeropace", WATCHLIST["ITA"]["name"])
        self.assertNotIn("Healths", WATCHLIST["HIMS"]["name"])
        self.assertIn("UnitedHealth", WATCHLIST["UNH"]["name"])
        self.assertGreaterEqual(len(WATCHLIST), 139)


if __name__ == "__main__":
    unittest.main()
