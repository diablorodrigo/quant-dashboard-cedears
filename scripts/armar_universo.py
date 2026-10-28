"""Reconstruye data/cedears_universo.csv y data/acciones_ar.csv con datos del día.

Usa data912 y Yahoo. No inventa un ratio: si el precio no lo confirma, el
activo queda sin verificar. Se corre a mano cuando se quiere refrescar la lista.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yfinance as yf

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from zeta.acciones_ar import PANEL_LIDER  # noqa: E402
from zeta.fuentes import ccl_data912, cotizaciones_acciones, cotizaciones_cedears, limpiar_cache, panel_ccl, subyacentes_ccl  # noqa: E402
from zeta.universo import (  # noqa: E402
    ESTADO_NO,
    ESTADO_OK,
    armar_universo,
    cargar_manual,
    contar,
    guardar_universo,
    rubro_desde_yahoo,
    simbolo_byma,
)


def _info(simbolo: str) -> tuple[str, dict]:
    try:
        data = yf.Ticker(simbolo).info or {}
        return simbolo, {
            "nombre": data.get("shortName") or data.get("longName"),
            "sector": data.get("sector"),
            "tipo": data.get("quoteType"),
        }
    except Exception as exc:  # noqa: BLE001
        return simbolo, {"error": str(exc)}


def _guardar_acciones(acciones: dict[str, dict], info: dict[str, dict]) -> None:
    import csv

    destino = RAIZ / "data" / "acciones_ar.csv"
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=["ticker", "nombre", "rubro", "panel", "sector_estado"])
        writer.writeheader()
        for simbolo in sorted(acciones):
            ficha = info.get(simbolo + ".BA") or info.get(simbolo) or {}
            rubro = rubro_desde_yahoo(ficha.get("sector"), ficha.get("tipo"))
            writer.writerow(
                {
                    "ticker": simbolo,
                    "nombre": ficha.get("nombre") or simbolo,
                    "rubro": rubro or "Sin clasificar",
                    "panel": "lider" if simbolo in PANEL_LIDER else "general",
                    "sector_estado": ESTADO_OK if rubro else ESTADO_NO,
                }
            )


def main() -> None:
    limpiar_cache()
    cedears = cotizaciones_cedears() or {}
    acciones = cotizaciones_acciones() or {}
    ccl_filas = panel_ccl()
    ccl = ccl_data912(ccl_filas)
    if not cedears or not ccl:
        raise SystemExit("data912 no devolvió CEDEARs o CCL. No se reescribe el universo.")
    print(f"CEDEARs en el feed: {len(cedears)}. CCL de referencia: {ccl:.2f}")

    manual = cargar_manual()
    for cfg in manual.values():
        byma = simbolo_byma(cfg["cedear"])
        if byma not in cedears and byma in acciones:
            cedears[byma] = acciones[byma]

    precios_path = Path("/tmp/usd_prices.json")
    sectores_path = Path("/tmp/sectores.json")
    if precios_path.exists() and sectores_path.exists():
        precios = {k: float(v) for k, v in json.loads(precios_path.read_text())["precios"].items()}
        crudo = json.loads(sectores_path.read_text())["info"]
    else:
        from zeta.universo import simbolos_pesos

        simbolos = sorted(
            {cfg["underlying"] for cfg in manual.values() if cfg.get("underlying")}
            | set(subyacentes_ccl(ccl_filas).values())
            | {simbolo.replace(".", "-") for simbolo in simbolos_pesos(cedears)}
        )
        print(f"Descargando {len(simbolos)} subyacentes de Yahoo…")
        precios = {}
        for inicio in range(0, len(simbolos), 60):
            grupo = simbolos[inicio : inicio + 60]
            data = yf.download(grupo, period="5d", auto_adjust=True, group_by="ticker", progress=False, threads=True)
            for ticker in grupo:
                try:
                    cierre = data[ticker]["Close"].dropna() if isinstance(data.columns, pd.MultiIndex) else data["Close"].dropna()
                except Exception:
                    continue
                if not cierre.empty:
                    precios[ticker] = float(cierre.iloc[-1])
        print(f"Precios USD: {len(precios)}. Fichas de sector…")
        crudo = {}
        with ThreadPoolExecutor(6) as pool:
            futuros = [pool.submit(_info, simbolo) for simbolo in precios]
            for futuro in as_completed(futuros):
                simbolo, ficha = futuro.result()
                crudo[simbolo] = ficha
    sectores = {}
    nombres = {}
    for simbolo, ficha in crudo.items():
        rubro = rubro_desde_yahoo(ficha.get("sector"), ficha.get("tipo"))
        if rubro:
            sectores[simbolo] = rubro
        if ficha.get("nombre"):
            nombres[simbolo] = ficha["nombre"]

    universo = armar_universo(
        cedears,
        manual,
        precios,
        ccl,
        subyacentes=subyacentes_ccl(ccl_filas),
        sectores_yahoo=sectores,
        nombres_yahoo=nombres,
    )
    guardar_universo(universo)
    resumen = contar(universo)
    print("Universo", resumen)

    simbolos_ar = [simbolo + ".BA" for simbolo in acciones]
    info_ar: dict[str, dict] = {}
    with ThreadPoolExecutor(6) as pool:
        futuros = [pool.submit(_info, simbolo) for simbolo in simbolos_ar]
        for futuro in as_completed(futuros):
            simbolo, ficha = futuro.result()
            info_ar[simbolo] = ficha
    _guardar_acciones(acciones, info_ar)
    verificados = sum(1 for ficha in info_ar.values() if rubro_desde_yahoo(ficha.get("sector"), ficha.get("tipo")))
    print(f"Acciones {len(acciones)}. Rubro verificado en {verificados}.")


if __name__ == "__main__":
    main()
