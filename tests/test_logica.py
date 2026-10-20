"""Pruebas de la lógica que no depende de Yahoo ni de Streamlit."""

import unittest
from datetime import date

import pandas as pd

from zeta.analisis_global import armar_analisis_global, puntaje_tecnico
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
    _caja_etiqueta,
    _flecha,
    cola_reciente,
    cuadrante,
    curvas_rrg,
    frase_rotacion,
    simbolos_extra,
    ubicar_etiquetas,
)
from zeta.paleta import TEMA_DEFAULT, TEMAS
from zeta.rrg import rango_ejes
from zeta.tiempo import clave_cierre, linea_datos, mercado_cedears_abierto
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


class AnalisisGlobal(unittest.TestCase):
    def test_el_tecnico_aporta_tres_cero_o_menos_tres(self):
        self.assertEqual(puntaje_tecnico(SESGO_ALCISTA), 3)
        self.assertEqual(puntaje_tecnico(SESGO_ALCISTA_MARCADO), 3)
        self.assertEqual(puntaje_tecnico(ALCISTA_CON_VOLUMEN), 3)
        self.assertEqual(puntaje_tecnico(ALCISTA_SIN_VOLUMEN), 3)
        self.assertEqual(puntaje_tecnico(SESGO_BAJISTA), -3)
        self.assertEqual(puntaje_tecnico(SESGO_BAJISTA_MARCADO), -3)
        self.assertEqual(puntaje_tecnico(NEUTRAL), 0)
        self.assertEqual(puntaje_tecnico(EN_OBSERVACION_RIESGO), 0)
        self.assertEqual(puntaje_tecnico(DISTRIBUCION), 0)

    def test_alcista_cuando_el_tecnico_no_queda_anulado(self):
        analisis = armar_analisis_global(
            lectura=SESGO_ALCISTA,
            rsi=48,
            stage2=True,
            precio_sobre_ema=True,
            medias_ordenadas=True,
            precio_sobre_medias=True,
            macd_estado="arriba",
            per=22,
            precio=100,
            objetivo=130,
            margen=0.24,
        )
        self.assertEqual(analisis["tecnico"], 3)
        self.assertEqual(analisis["fundamental"], 2)
        self.assertEqual(analisis["combinado"], 5)
        self.assertEqual(analisis["sesgo"], "Alcista")
        self.assertIn("Tendencia", [item["titulo"] for item in analisis["tecnicos"]])
        self.assertIn("no constituyen recomendación de inversión", analisis["aviso"])

    def test_un_fundamental_negativo_deja_el_global_en_neutral(self):
        analisis = armar_analisis_global(
            lectura=SESGO_ALCISTA_MARCADO,
            per=40,
            precio=100,
            objetivo=90,
            margen=-0.02,
        )
        self.assertEqual(analisis["fundamental_bruto"], -3)
        self.assertTrue(analisis["recortado"])
        self.assertEqual(analisis["fundamental"], -2)
        self.assertEqual(analisis["combinado"], 1)
        self.assertEqual(analisis["sesgo"], "Neutral")

    def test_bajista_y_componentes_sin_datos(self):
        analisis = armar_analisis_global(lectura=SESGO_BAJISTA, rsi=74, precio_sobre_ema=False, macd_estado="abajo")
        self.assertEqual(analisis["combinado"], -3)
        self.assertEqual(analisis["sesgo"], "Bajista")
        self.assertEqual(analisis["fundamental"], 0)
        textos = " ".join(item["texto"] for item in analisis["tecnicos"] + analisis["fundamentales"])
        self.assertIn("debajo de la EMA de 200", textos)
        self.assertIn("extremo alto", textos)
        self.assertIn("Sin PER", textos)
        self.assertIn("Sin precio objetivo", textos)
        self.assertIn("Sin margen neto", textos)


class Radar(unittest.TestCase):
    def test_el_rango_abre_el_centro_y_no_sigue_al_extremo(self):
        valores = pd.Series([0.1] * 40 + [-0.2] * 40 + [0.4] * 18 + [9.5, -8.0])
        lo, hi = rango_ejes(valores)
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)
        self.assertLess(hi, 3)
        self.assertGreater(lo, -3)
        self.assertLess(hi - lo, float(valores.max() - valores.min()))

    def test_un_grupo_chico_sigue_incluyendo_el_cero(self):
        lo, hi = rango_ejes(pd.Series([1.2, 1.4, 1.6]))
        self.assertLessEqual(lo, 0)
        self.assertGreaterEqual(hi, 1.6)

    def test_serie_vacia(self):
        self.assertEqual(rango_ejes(pd.Series(dtype=float)), (-1.0, 1.0))


class Tiempo(unittest.TestCase):
    def test_corte_en_hora_argentina(self):
        zona = "America/Argentina/Buenos_Aires"
        lunes_manana = pd.Timestamp("2026-10-19 10:00", tz=zona)
        lunes_noche = pd.Timestamp("2026-10-19 18:05", tz=zona)
        domingo = pd.Timestamp("2026-10-18 20:00", tz=zona)
        self.assertEqual(clave_cierre(lunes_manana), "2026-10-16")
        self.assertEqual(clave_cierre(lunes_noche), "2026-10-19")
        self.assertEqual(clave_cierre(domingo), "2026-10-16")

    def test_el_sello_usa_la_descarga_y_no_cambia_con_la_hora_de_apertura(self):
        zona = "America/Argentina/Buenos_Aires"
        descarga = pd.Timestamp("2026-10-19 21:40", tz=zona)
        consulta = pd.Timestamp("2026-10-20 09:15", tz=zona)
        texto = linea_datos(descarga, pd.Timestamp("2026-10-17"), consulta, pd.Timestamp("2026-10-16"))
        self.assertIn("Datos actualizados: 19/10/2026 21:40 (hora Argentina)", texto)
        self.assertIn("Mercado de CEDEARs cerrado", texto)
        self.assertIn("Precios de Yahoo con demora de unos 15 minutos", texto)
        self.assertIn("Última rueda en la serie: 17/10/2026", texto)
        self.assertIn("Precios en pesos al 16/10/2026", texto)
        self.assertNotIn("09:15", texto)
        self.assertNotIn("20/10/2026", texto)

    def test_la_rueda_local_abre_a_las_once_y_cierra_a_las_diecisiete(self):
        zona = "America/Argentina/Buenos_Aires"
        self.assertTrue(mercado_cedears_abierto(pd.Timestamp("2026-10-19 11:00", tz=zona)))
        self.assertTrue(mercado_cedears_abierto(pd.Timestamp("2026-10-19 16:59", tz=zona)))
        self.assertFalse(mercado_cedears_abierto(pd.Timestamp("2026-10-19 10:59", tz=zona)))
        self.assertFalse(mercado_cedears_abierto(pd.Timestamp("2026-10-19 17:00", tz=zona)))
        self.assertFalse(mercado_cedears_abierto(pd.Timestamp("2026-10-18 12:00", tz=zona)))


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


class Paleta(unittest.TestCase):
    def test_los_dos_temas_cubren_lo_mismo(self):
        self.assertEqual(TEMA_DEFAULT, "Oscuro")
        self.assertEqual(set(TEMAS), {"Oscuro", "Claro"})
        self.assertEqual(set(TEMAS["Oscuro"]), set(TEMAS["Claro"]))
        for nombre, colores in TEMAS.items():
            for clave, valor in colores.items():
                self.assertTrue(valor, f"{nombre}.{clave}")
            self.assertIn(colores["texto"], colores["lectura_alcista"])
            self.assertNotEqual(colores["fondo_grafico"], TEMAS["Claro" if nombre == "Oscuro" else "Oscuro"]["fondo_grafico"])


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

    def test_las_etiquetas_no_se_pisan(self):
        puntos = [
            ("XLE", 2.9, 0.9),
            ("XLV", 2.8, 1.6),
            ("XLK", 2.7, -1.2),
            ("XLP", 1.4, 2.2),
            ("XLF", 0.4, 1.0),
            ("XLC", -0.6, 1.4),
            ("XLB", -1.2, 0.5),
            ("XLY", -1.6, 2.2),
            ("XLI", -1.9, 0.6),
            ("XLRE", -3.5, 1.8),
            ("XLU", -6.4, 3.1),
        ]
        x0, x1, y0, y1 = -8.0, 8.0, -4.5, 4.5
        puestos = ubicar_etiquetas(puntos, x0, x1, y0, y1)
        ancho, alto = _caja_etiqueta(x0, x1, y0, y1)
        self.assertEqual(set(puestos), {ticker for ticker, _, _ in puntos})
        for ticker, x, y in puntos:
            lx, ly = puestos[ticker]
            self.assertGreaterEqual(lx, x0)
            self.assertLessEqual(lx, x1)
            self.assertGreaterEqual(ly, y0)
            self.assertLessEqual(ly, y1)
            self.assertGreater((((lx - x) / ancho) ** 2 + ((ly - y) / alto) ** 2) ** 0.5, 0.45)
        claves = list(puestos)
        for i, ti in enumerate(claves):
            for tj in claves[i + 1 :]:
                dx = abs(puestos[ti][0] - puestos[tj][0]) / ancho
                dy = abs(puestos[ti][1] - puestos[tj][1]) / alto
                self.assertGreater((dx ** 2 + dy ** 2) ** 0.5, 0.95, f"{ti} y {tj}")


if __name__ == "__main__":
    unittest.main()
