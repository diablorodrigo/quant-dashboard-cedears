"""Contraste entre fuentes. No pega a la red."""

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from zeta.contraste import (
    AMARILLO,
    ROJO,
    VERDE,
    cierre_previo,
    contrastar_cotizacion,
    diferencia_relativa,
    registrar_desvio,
    semaforo,
)
from zeta.fuentes import edad_cache, limpiar_cache, mediana, obtener_json


class Semaforo(unittest.TestCase):
    def test_bandas_de_precio(self):
        self.assertEqual(semaforo(100, 100.4)["estado"], VERDE)
        self.assertEqual(semaforo(100, 100.5)["estado"], AMARILLO)
        self.assertEqual(semaforo(100, 102)["estado"], AMARILLO)
        self.assertEqual(semaforo(100, 102.01)["estado"], ROJO)
        self.assertTrue(semaforo(100, 103)["bloquea_senal"])
        self.assertFalse(semaforo(100, 101)["bloquea_senal"])

    def test_el_dolar_tolera_hasta_uno_por_ciento(self):
        self.assertEqual(semaforo(1500, 1514, es_dolar=True)["estado"], VERDE)
        self.assertEqual(semaforo(1500, 1516, es_dolar=True)["estado"], AMARILLO)
        self.assertEqual(semaforo(1500, 1531, es_dolar=True)["estado"], ROJO)

    def test_un_dato_viejo_con_el_mercado_abierto_es_rojo(self):
        lectura = semaforo(100, 100, edad_minutos=31, mercado_abierto=True)
        self.assertEqual(lectura["estado"], ROJO)
        self.assertTrue(lectura["bloquea_senal"])
        self.assertIn("30 minutos", lectura["motivo"])

    def test_fuera_de_rueda_la_edad_no_pinta_de_rojo(self):
        lectura = semaforo(100, 100, edad_minutos=400, mercado_abierto=False)
        self.assertEqual(lectura["estado"], VERDE)
        self.assertFalse(lectura["bloquea_senal"])

    def test_sin_segunda_fuente_queda_en_amarillo_y_no_bloquea(self):
        lectura = semaforo(100, None)
        self.assertEqual(lectura["estado"], AMARILLO)
        self.assertFalse(lectura["bloquea_senal"])

    def test_sin_dato_principal_es_rojo(self):
        self.assertEqual(semaforo(None, 100)["estado"], ROJO)


class Cierre(unittest.TestCase):
    def test_reconstruye_el_cierre_anterior(self):
        self.assertAlmostEqual(cierre_previo(110, 10), 100)
        self.assertIsNone(cierre_previo(None, 1))

    def test_si_yahoo_no_tiene_la_rueda_se_contrasta_el_cierre(self):
        # El vivo ya subió 10%. El cierre anterior coincide con Yahoo: no es un desvío.
        lectura = contrastar_cotizacion(
            precio_vivo=110,
            variacion_pct=10,
            precio_yahoo=100,
            yahoo_es_hoy=False,
            edad_minutos=1,
            mercado_abierto=True,
        )
        self.assertEqual(lectura["estado"], VERDE)
        self.assertEqual(lectura["comparo"], "cierre_anterior")
        self.assertFalse(lectura["bloquea_senal"])

    def test_si_los_precios_de_ahora_coinciden_no_usa_el_cierre(self):
        # El cierre reconstruido se iría lejos, pero el precio vivo y Yahoo ya coinciden.
        lectura = contrastar_cotizacion(
            precio_vivo=100.1,
            variacion_pct=10,
            precio_yahoo=100,
            yahoo_es_hoy=False,
            edad_minutos=1,
            mercado_abierto=True,
        )
        self.assertEqual(lectura["estado"], VERDE)
        self.assertEqual(lectura["comparo"], "precio")
        self.assertFalse(lectura["bloquea_senal"])

    def test_el_mismo_dia_compara_el_precio(self):
        lectura = contrastar_cotizacion(
            precio_vivo=110,
            variacion_pct=0,
            precio_yahoo=100,
            yahoo_es_hoy=True,
            edad_minutos=1,
            mercado_abierto=True,
        )
        self.assertEqual(lectura["estado"], ROJO)
        self.assertTrue(lectura["bloquea_senal"])

    def test_la_diferencia_es_relativa_al_principal(self):
        self.assertAlmostEqual(diferencia_relativa(200, 210), 0.05)


class Mediana(unittest.TestCase):
    def test_no_publica_el_ccl_de_un_solo_ticker(self):
        self.assertIsNone(mediana([1650]))
        self.assertIsNone(mediana([1650, 1700]))

    def test_la_mediana_usa_varios_pares_y_deja_afuera_el_extremo(self):
        valor = mediana([2000, 1650, 1652, 1648, 1655, 1649])
        self.assertIsNotNone(valor)
        self.assertLess(abs(valor - 1650), 5)
        self.assertNotAlmostEqual(valor, 2000, delta=50)


class Log(unittest.TestCase):
    def test_el_verde_no_se_anota_y_el_rojo_si(self):
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "desvios-2026-10-28.csv"
            registrar_desvio(ruta, {"estado": VERDE, "clave": "AAPL", "momento": "x"})
            self.assertFalse(ruta.exists())
            registrar_desvio(
                ruta,
                {
                    "momento": datetime(2026, 10, 28, 11, 5).isoformat(),
                    "tipo": "precio",
                    "clave": "GGAL",
                    "valor_principal": 100,
                    "fuente_principal": "data912",
                    "valor_contraste": 104,
                    "fuente_contraste": "Yahoo .BA",
                    "diferencia_pct": 4,
                    "estado": ROJO,
                    "motivo": "Las fuentes difieren más del 2%.",
                },
            )
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn("GGAL", texto)
            self.assertIn("data912", texto)
            self.assertNotIn("AAPL", texto)


class Red(unittest.TestCase):
    def test_un_timeout_no_inventa_un_numero(self):
        class Rota:
            def get(self, *args, **kwargs):
                raise requests.Timeout("tardó")

        self.assertIsNone(obtener_json("https://data912.com/live/arg_cedears", sesion=Rota()))

    def test_la_cache_acumula_edad(self):
        limpiar_cache()
        from zeta.fuentes import con_cache

        con_cache("edad-test", 60, lambda: {"ok": True})
        edad = edad_cache("edad-test")
        self.assertIsNotNone(edad)
        self.assertLess(edad, 1)
        limpiar_cache()


if __name__ == "__main__":
    unittest.main()
