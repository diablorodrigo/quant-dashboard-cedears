"""Universo de CEDEARs.

La lista a mano vive en ``data/cedears_manual.csv`` (nombre, símbolo de
Yahoo, subyacente, ratio y rubro). El universo que muestra el panel sale
de data912 más ese CSV: cada ticker, ratio y rubro queda verificado o
marcado como ``sin verificar``. Un ratio que no se puede verificar no se
inventa y no entra en el CCL ni en el gap.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_MANUAL = RAIZ / "data" / "cedears_manual.csv"
RUTA_UNIVERSO = RAIZ / "data" / "cedears_universo.csv"
RUTA_ACCIONES = RAIZ / "data" / "acciones_ar.csv"

ESTADO_OK = "verificado"
ESTADO_NO = "sin verificar"
TOLERANCIA_MANUAL = 0.04
TOLERANCIA_NUEVO = 0.02
SEPARACION_NUEVO = 0.06
SPREAD_MAX = 0.05

MAPA_RUBRO = {
    "Technology": "Tecnología",
    "Financial Services": "Finanzas",
    "Energy": "Energía",
    "Healthcare": "Salud",
    "Consumer Cyclical": "Consumo",
    "Consumer Defensive": "Consumo",
    "Industrials": "Industria",
    "Basic Materials": "Materiales",
    "Utilities": "Servicios públicos",
    "Real Estate": "Inmuebles",
    "Communication Services": "Comunicaciones",
}

SUFIJOS_ESPECIE = (".CD", ".CC", ".C", ".D", "C", "D")


def _numero(texto: str | None) -> float | None:
    if texto is None:
        return None
    limpio = str(texto).strip()
    if not limpio:
        return None
    try:
        valor = float(limpio.replace(",", "."))
    except ValueError:
        return None
    if valor.is_integer():
        return int(valor)
    return valor


def _leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def simbolo_byma(cedear: str) -> str:
    """Pasa el símbolo de Yahoo (``BA-C.BA``) al símbolo BYMA (``BA.C``)."""
    texto = str(cedear or "").strip()
    if texto.endswith(".BA"):
        texto = texto[:-3]
    return texto.replace("-", ".")


def yahoo_cedear(simbolo: str) -> str:
    """Pasa el símbolo BYMA al ticker de Yahoo en Buenos Aires."""
    return str(simbolo).replace(".", "-") + ".BA"


def cargar_manual(ruta: Path | None = None) -> dict[str, dict]:
    filas = _leer_csv(ruta or RUTA_MANUAL)
    salida: dict[str, dict] = {}
    for fila in filas:
        ticker = (fila.get("ticker") or "").strip()
        if not ticker:
            continue
        salida[ticker] = {
            "name": (fila.get("nombre") or ticker).strip(),
            "cedear": (fila.get("cedear") or "").strip(),
            "underlying": (fila.get("underlying") or "").strip(),
            "ratio": _numero(fila.get("ratio")),
            "rubro": (fila.get("rubro") or "Otros").strip(),
        }
    return salida


def cargar_universo(ruta: Path | None = None) -> dict[str, dict]:
    filas = _leer_csv(ruta or RUTA_UNIVERSO)
    salida: dict[str, dict] = {}
    for fila in filas:
        ticker = (fila.get("ticker") or "").strip()
        if not ticker:
            continue
        salida[ticker] = {
            "name": (fila.get("nombre") or ticker).strip(),
            "cedear": (fila.get("cedear") or "").strip(),
            "underlying": (fila.get("underlying") or "").strip(),
            "ratio": _numero(fila.get("ratio")),
            "rubro": (fila.get("rubro") or "Sin verificar").strip(),
            "estado": (fila.get("estado") or ESTADO_NO).strip(),
            "sector_estado": (fila.get("sector_estado") or ESTADO_NO).strip(),
            "byma": (fila.get("byma") or simbolo_byma(fila.get("cedear") or "")).strip(),
            "origen": (fila.get("origen") or "").strip(),
            "motivo": (fila.get("motivo") or "").strip(),
        }
    return salida


def cargar_acciones(ruta: Path | None = None) -> dict[str, dict]:
    filas = _leer_csv(ruta or RUTA_ACCIONES)
    salida: dict[str, dict] = {}
    for fila in filas:
        ticker = (fila.get("ticker") or "").strip()
        if not ticker:
            continue
        salida[ticker] = {
            "name": (fila.get("nombre") or ticker).strip(),
            "rubro": (fila.get("rubro") or "Sin clasificar").strip(),
            "panel": (fila.get("panel") or "general").strip(),
            "sector_estado": (fila.get("sector_estado") or ESTADO_NO).strip(),
        }
    return salida


WATCHLIST = cargar_manual()


def grilla_ratios() -> list[float]:
    """Ratios que usa BYMA: cuartos hasta 2 y enteros hasta 200. Nada intermedio."""
    valores = [numero / 4 for numero in range(1, 9)]
    valores.extend(float(numero) for numero in range(1, 201))
    return sorted(set(valores))


GRILLA = grilla_ratios()


def elegir_ratio(implicito: float | None, *, tolerancia: float = TOLERANCIA_NUEVO, separacion: float = SEPARACION_NUEVO) -> float | None:
    """Devuelve el ratio de la grilla solo si el precio lo señala sin ambigüedad."""
    if implicito is None or implicito <= 0:
        return None
    ordenados = sorted(GRILLA, key=lambda ratio: abs(implicito / ratio - 1))
    mejor, segundo = ordenados[0], ordenados[1]
    distancia = abs(implicito / mejor - 1)
    siguiente = abs(implicito / segundo - 1)
    if distancia <= tolerancia and siguiente >= separacion:
        if float(mejor).is_integer():
            return int(mejor)
        return mejor
    return None


def rubro_desde_yahoo(sector: str | None, tipo: str | None = None) -> str | None:
    if tipo and str(tipo).upper() == "ETF":
        return "ETFs"
    if not sector:
        return None
    return MAPA_RUBRO.get(str(sector))


def es_variante_dolar(simbolo: str, precios: dict[str, float]) -> bool:
    """True si el símbolo es la especie en dólares o cable de otro papel.

    ``BBD`` no se descarta: cotiza en la misma escala que ``BB`` y es otro
    activo. ``MUD`` sí: vale una fracción de ``MU``.
    """
    for sufijo in SUFIJOS_ESPECIE:
        if simbolo.endswith(sufijo) and len(simbolo) > len(sufijo):
            base = simbolo[: -len(sufijo)]
            precio_base = precios.get(base)
            precio = precios.get(simbolo)
            if precio_base and precio:
                if precio < precio_base * 0.15:
                    return True
                return False
    precio = precios.get(simbolo) or 0
    if simbolo.endswith(("D", "C", ".D", ".C", ".CD", ".CC")) and 0 < precio < 80:
        return True
    return False


def simbolos_pesos(cotizaciones: dict[str, dict]) -> list[str]:
    precios = {simbolo: float(fila.get("c") or 0) for simbolo, fila in cotizaciones.items()}
    return [simbolo for simbolo in cotizaciones if not es_variante_dolar(simbolo, precios)]


def _spread(fila: dict) -> float | None:
    try:
        bid = float(fila.get("px_bid") or 0)
        ask = float(fila.get("px_ask") or 0)
    except (TypeError, ValueError):
        return None
    if bid <= 0 or ask <= 0:
        return None
    medio = (bid + ask) / 2
    if medio <= 0:
        return None
    return (ask - bid) / medio


def _ccl_implicito(precio_ars: float, precio_usd: float, ratio: float) -> float | None:
    if precio_ars <= 0 or precio_usd <= 0 or ratio <= 0:
        return None
    return (precio_ars * ratio) / precio_usd


def usa_ratio(cfg: dict) -> bool:
    return cfg.get("estado") == ESTADO_OK and cfg.get("ratio") not in (None, "")


def usa_sector(cfg: dict) -> bool:
    return cfg.get("sector_estado") == ESTADO_OK and cfg.get("rubro") not in (None, "", "Sin verificar", "Sin clasificar")


def _registro(
    ticker: str,
    *,
    nombre: str,
    cedear: str,
    underlying: str,
    ratio,
    rubro: str,
    estado: str,
    sector_estado: str,
    byma: str,
    origen: str,
    motivo: str,
) -> dict:
    return {
        "name": nombre,
        "cedear": cedear,
        "underlying": underlying,
        "ratio": ratio,
        "rubro": rubro or "Sin verificar",
        "estado": estado,
        "sector_estado": sector_estado,
        "byma": byma,
        "origen": origen,
        "motivo": motivo,
    }


def armar_universo(
    cotizaciones: dict[str, dict],
    manual: dict[str, dict],
    precios_usd: dict[str, float],
    ccl_referencia: float | None,
    subyacentes: dict[str, str] | None = None,
    sectores_yahoo: dict[str, str] | None = None,
    nombres_yahoo: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Une el feed de data912 con el CSV a mano y verifica ratio y rubro.

    ``sectores_yahoo`` y ``nombres_yahoo`` están keyed por el subyacente.
    Si Yahoo no trae el rubro, el activo queda sin verificar en ese campo.
    """
    subyacentes = subyacentes or {}
    sectores_yahoo = sectores_yahoo or {}
    nombres_yahoo = nombres_yahoo or {}
    pesos = set(simbolos_pesos(cotizaciones)) if cotizaciones else set()
    salida: dict[str, dict] = {}
    byma_usados: set[str] = set()

    for ticker, cfg in manual.items():
        byma = simbolo_byma(cfg.get("cedear") or ticker)
        byma_usados.add(byma)
        fila = cotizaciones.get(byma) or {}
        precio_ars = float(fila["c"]) if fila.get("c") else None
        underlying = cfg.get("underlying") or ""
        precio_usd = precios_usd.get(underlying)
        rubro_yahoo = sectores_yahoo.get(underlying)
        rubro_manual = cfg.get("rubro") or "Sin verificar"
        if rubro_yahoo and rubro_yahoo == rubro_manual:
            sector_estado = ESTADO_OK
        elif rubro_yahoo and rubro_yahoo != rubro_manual:
            sector_estado = ESTADO_NO
        else:
            sector_estado = ESTADO_NO
        ratio = cfg.get("ratio")
        estado = ESTADO_NO
        motivo = "Sin precio en las dos patas para verificar el ratio."
        if ccl_referencia and precio_ars and precio_usd and ratio:
            implicito = _ccl_implicito(precio_ars, float(precio_usd), float(ratio))
            if implicito:
                desvio = abs(implicito / ccl_referencia - 1)
                if desvio <= TOLERANCIA_MANUAL:
                    estado = ESTADO_OK
                    motivo = f"El ratio {ratio} implica un CCL a {desvio * 100:.2f}% de la referencia."
                else:
                    motivo = (
                        f"El ratio {ratio} implica un CCL a {desvio * 100:.2f}% de la referencia. "
                        "Queda sin verificar."
                    )
        elif not (ccl_referencia and precio_ars and precio_usd):
            motivo = "Sin precio en las dos patas para verificar el ratio."
        salida[ticker] = _registro(
            ticker,
            nombre=cfg.get("name") or ticker,
            cedear=cfg.get("cedear") or yahoo_cedear(byma),
            underlying=underlying,
            ratio=ratio,
            rubro=rubro_manual,
            estado=estado,
            sector_estado=sector_estado,
            byma=byma,
            origen="manual",
            motivo=motivo,
        )

    if not ccl_referencia:
        for simbolo in sorted(pesos):
            if simbolo in byma_usados or simbolo in salida:
                continue
            salida[simbolo] = _registro(
                simbolo,
                nombre=simbolo,
                cedear=yahoo_cedear(simbolo),
                underlying=subyacentes.get(simbolo) or simbolo.replace(".", "-"),
                ratio=None,
                rubro="Sin verificar",
                estado=ESTADO_NO,
                sector_estado=ESTADO_NO,
                byma=simbolo,
                origen="feed",
                motivo="Sin CCL de referencia no se verifica el ratio.",
            )
        return salida

    for simbolo in sorted(pesos):
        if simbolo in byma_usados or simbolo in salida:
            continue
        fila = cotizaciones.get(simbolo) or {}
        precio_ars = float(fila["c"]) if fila.get("c") else None
        underlying = subyacentes.get(simbolo) or simbolo.replace(".", "-")
        precio_usd = precios_usd.get(underlying) or precios_usd.get(simbolo)
        nombre = nombres_yahoo.get(underlying) or simbolo
        rubro = sectores_yahoo.get(underlying)
        sector_estado = ESTADO_OK if rubro else ESTADO_NO
        ratio = None
        estado = ESTADO_NO
        motivo = "Sin precio del subyacente para verificar el ratio."
        if precio_ars and precio_usd:
            implicito = (float(precio_usd) * ccl_referencia) / precio_ars
            candidato = elegir_ratio(implicito)
            volumen = float(fila.get("v") or 0)
            spread = _spread(fila)
            liquido = volumen > 0 and spread is not None and spread < SPREAD_MAX
            if candidato is None:
                motivo = "El precio no coincide con un único ratio de la grilla."
            elif not liquido:
                motivo = "El ratio cierra, pero no hubo volumen o el spread es ancho: queda sin verificar."
            else:
                ratio = candidato
                estado = ESTADO_OK
                desvio = abs(implicito / float(candidato) - 1)
                motivo = f"Ratio {candidato} único, a {desvio * 100:.2f}% del precio, con volumen."
        salida[simbolo] = _registro(
            simbolo,
            nombre=nombre,
            cedear=yahoo_cedear(simbolo),
            underlying=underlying,
            ratio=ratio if estado == ESTADO_OK else None,
            rubro=rubro or "Sin verificar",
            estado=estado,
            sector_estado=sector_estado if estado == ESTADO_OK else ESTADO_NO,
            byma=simbolo,
            origen="consistencia" if estado == ESTADO_OK else "feed",
            motivo=motivo,
        )
    return salida


def incorporar_faltantes(universo: dict[str, dict], simbolos: list[str]) -> dict[str, dict]:
    """Suma tickers nuevos del feed como sin verificar, sin inventarles un ratio."""
    salida = dict(universo)
    presentes = {cfg.get("byma") or simbolo_byma(cfg.get("cedear") or "") for cfg in universo.values()}
    presentes.update(universo)
    for simbolo in simbolos:
        if simbolo in presentes:
            continue
        salida[simbolo] = _registro(
            simbolo,
            nombre=simbolo,
            cedear=yahoo_cedear(simbolo),
            underlying="",
            ratio=None,
            rubro="Sin verificar",
            estado=ESTADO_NO,
            sector_estado=ESTADO_NO,
            byma=simbolo,
            origen="feed",
            motivo="Apareció en data912 y todavía no tiene ratio verificado.",
        )
    return salida


def guardar_universo(universo: dict[str, dict], ruta: Path | None = None) -> None:
    destino = ruta or RUTA_UNIVERSO
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = ["ticker", "nombre", "cedear", "underlying", "ratio", "rubro", "estado", "sector_estado", "byma", "origen", "motivo"]
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=campos)
        writer.writeheader()
        for ticker, cfg in universo.items():
            writer.writerow(
                {
                    "ticker": ticker,
                    "nombre": cfg.get("name") or "",
                    "cedear": cfg.get("cedear") or "",
                    "underlying": cfg.get("underlying") or "",
                    "ratio": "" if cfg.get("ratio") is None else cfg.get("ratio"),
                    "rubro": cfg.get("rubro") or "",
                    "estado": cfg.get("estado") or ESTADO_NO,
                    "sector_estado": cfg.get("sector_estado") or ESTADO_NO,
                    "byma": cfg.get("byma") or "",
                    "origen": cfg.get("origen") or "",
                    "motivo": cfg.get("motivo") or "",
                }
            )


def contar(universo: dict[str, dict]) -> dict[str, int]:
    verificados = sum(1 for cfg in universo.values() if cfg.get("estado") == ESTADO_OK)
    sector = sum(1 for cfg in universo.values() if cfg.get("sector_estado") == ESTADO_OK)
    return {
        "total": len(universo),
        "verificados": verificados,
        "sin_verificar": len(universo) - verificados,
        "sector_verificado": sector,
    }
