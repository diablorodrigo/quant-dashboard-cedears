"""Fuentes públicas, sin clave: data912, Yahoo como contraste de precio,
ArgentinaDatos y el BCRA.

data912 es la fuente principal de cotizaciones en vivo. Cada lectura se
cachea al menos un minuto. Si una fuente no responde, se devuelve None:
no se completa con un número inventado.
"""

from __future__ import annotations

import logging
import statistics
import time
from typing import Any

import requests

from zeta.contraste import AMARILLO, registrar_desvio, semaforo

URL_CEDEARS = "https://data912.com/live/arg_cedears"
URL_ACCIONES = "https://data912.com/live/arg_stocks"
URL_MEP = "https://data912.com/live/mep"
URL_CCL = "https://data912.com/live/ccl"
URL_ARGENTINA = "https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}"
URL_RIESGO_ARGENTINA = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"
URL_BCRA_MAYORISTA = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/5"
URL_RIESGO_AMBITO = "https://mercados.ambito.com/riesgopais/variacion"

TTL_VIVO = 60
TTL_FALLO = 15
TIMEOUT = 12
TIMEOUT_LARGO = 20
AGENTE = "PanelZeta/2.0"

_CACHE: dict[str, tuple[float, Any, float]] = {}


def limpiar_cache() -> None:
    _CACHE.clear()


def edad_cache(clave: str) -> float | None:
    """Minutos desde la última lectura guardada de esa clave. None si no hay."""
    guardado = _CACHE.get(clave)
    if guardado is None:
        return None
    return (time.monotonic() - guardado[0]) / 60.0


def con_cache(clave: str, ttl: float, funcion):
    ahora = time.monotonic()
    guardado = _CACHE.get(clave)
    if guardado is not None:
        momento, valor, vigencia = guardado
        if ahora - momento < vigencia:
            return valor
    valor = funcion()
    _CACHE[clave] = (ahora, valor, ttl if valor is not None else min(TTL_FALLO, ttl))
    return valor


def obtener_json(
    url: str,
    *,
    timeout: float = TIMEOUT,
    sesion: requests.Session | None = None,
) -> Any | None:
    cliente = sesion or requests
    try:
        respuesta = cliente.get(url, timeout=timeout, headers={"User-Agent": AGENTE})
        respuesta.raise_for_status()
        return respuesta.json()
    except Exception as exc:
        logging.warning("No se pudo leer %s: %s", url, exc)
        return None


def _tabla(url: str, *, timeout: float = TIMEOUT, sesion=None) -> list[dict] | None:
    data = obtener_json(url, timeout=timeout, sesion=sesion)
    if not isinstance(data, list):
        return None
    return [fila for fila in data if isinstance(fila, dict)]


def _por_simbolo(filas: list[dict] | None, campo: str = "symbol") -> dict[str, dict] | None:
    if not filas:
        return None
    salida = {}
    for fila in filas:
        simbolo = fila.get(campo)
        if simbolo:
            salida[str(simbolo)] = fila
    return salida or None


def cotizaciones_cedears(sesion=None) -> dict[str, dict] | None:
    def leer():
        return _por_simbolo(_tabla(URL_CEDEARS, sesion=sesion))

    return con_cache("cedears", TTL_VIVO, leer)


def cotizaciones_acciones(sesion=None) -> dict[str, dict] | None:
    def leer():
        return _por_simbolo(_tabla(URL_ACCIONES, sesion=sesion))

    return con_cache("acciones", TTL_VIVO, leer)


def panel_mep(sesion=None) -> list[dict] | None:
    return con_cache("mep", TTL_VIVO, lambda: _tabla(URL_MEP, sesion=sesion))


def panel_ccl(sesion=None) -> list[dict] | None:
    return con_cache("ccl", TTL_VIVO, lambda: _tabla(URL_CCL, sesion=sesion))


def mediana(valores: list[float], *, recorte: float = 0.015, minimo: int = 3) -> float | None:
    """Mediana de varios números. Descarta los que se van más del recorte.

    Con menos de `minimo` lecturas devuelve None: un solo ticker no alcanza
    para publicar el CCL.
    """
    limpios = []
    for valor in valores:
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            continue
        if numero > 0:
            limpios.append(numero)
    if len(limpios) < minimo:
        return None
    centro = statistics.median(limpios)
    if centro <= 0:
        return None
    filtrados = [valor for valor in limpios if abs(valor / centro - 1) <= recorte]
    if len(filtrados) >= minimo:
        return float(statistics.median(filtrados))
    return float(centro)


def mep_data912(filas: list[dict] | None, n: int = 15) -> float | None:
    if not filas:
        return None
    liquidas = [
        fila for fila in filas
        if fila.get("panel") == "cedear" and fila.get("mark") and (fila.get("v_ars") or 0) > 0
    ]
    liquidas.sort(key=lambda fila: -(fila.get("v_ars") or 0))
    return mediana([fila["mark"] for fila in liquidas[:n]])


def ccl_data912(filas: list[dict] | None, n: int = 15) -> float | None:
    """Mediana del CCL que data912 calcula por ticker. No usa un solo papel."""
    if not filas:
        return None
    liquidas = [
        fila for fila in filas
        if fila.get("arg_panel") == "cedear" and fila.get("CCL_mark") and (fila.get("ars_volume") or 0) > 0
    ]
    liquidas.sort(key=lambda fila: -(fila.get("ars_volume") or 0))
    return mediana([fila["CCL_mark"] for fila in liquidas[:n]])


def subyacentes_ccl(filas: list[dict] | None) -> dict[str, str]:
    """Símbolo BYMA → símbolo en Estados Unidos, según el panel de CCL."""
    if not filas:
        return {}
    salida = {}
    for fila in filas:
        local = fila.get("ticker_ar")
        externo = fila.get("ticker_usa")
        if local and externo:
            salida[str(local)] = str(externo)
    return salida


def _ultima_casa(casa: str, sesion=None) -> dict | None:
    filas = _tabla(URL_ARGENTINA.format(casa=casa), timeout=TIMEOUT_LARGO, sesion=sesion)
    if not filas:
        return None
    return max(filas, key=lambda fila: str(fila.get("fecha") or ""))


def _punto_medio(fila: dict | None) -> float | None:
    if not fila:
        return None
    compra, venta = fila.get("compra"), fila.get("venta")
    try:
        if compra is not None and venta is not None:
            return (float(compra) + float(venta)) / 2
        if venta is not None:
            return float(venta)
    except (TypeError, ValueError):
        return None
    return None


def dolares_argentina(sesion=None) -> dict[str, dict | None]:
    def leer():
        return {
            "bolsa": _ultima_casa("bolsa", sesion),
            "contadoconliqui": _ultima_casa("contadoconliqui", sesion),
            "mayorista": _ultima_casa("mayorista", sesion),
            "oficial": _ultima_casa("oficial", sesion),
        }

    return con_cache("dolares_arg", TTL_VIVO, leer)


def riesgo_argentina(sesion=None) -> dict | None:
    def leer():
        data = obtener_json(URL_RIESGO_ARGENTINA, timeout=TIMEOUT_LARGO, sesion=sesion)
        if not isinstance(data, dict) or data.get("valor") is None:
            return None
        try:
            return {"valor": float(data["valor"]), "fecha": data.get("fecha")}
        except (TypeError, ValueError):
            return None

    return con_cache("riesgo_arg", TTL_VIVO, leer)


def riesgo_ambito(sesion=None) -> dict | None:
    def leer():
        data = obtener_json(URL_RIESGO_AMBITO, sesion=sesion)
        if not isinstance(data, dict) or data.get("ultimo") in (None, ""):
            return None
        texto = str(data["ultimo"]).strip().replace(".", "").replace(",", ".")
        try:
            return {"valor": float(texto), "fecha": data.get("fecha")}
        except ValueError:
            return None

    return con_cache("riesgo_ambito", TTL_VIVO, leer)


def oficial_bcra(sesion=None) -> dict | None:
    """Tipo de cambio mayorista de referencia (variable 5, comunicación de referencia)."""

    def leer():
        data = obtener_json(URL_BCRA_MAYORISTA, timeout=TIMEOUT_LARGO, sesion=sesion)
        try:
            detalle = data["results"][0]["detalle"][0]
            return {"valor": float(detalle["valor"]), "fecha": detalle.get("fecha")}
        except (TypeError, ValueError, KeyError, IndexError):
            return None

    return con_cache("bcra", TTL_VIVO, leer)


def _fila_log(tipo: str, clave: str, principal, fuente_a: str, contraste, fuente_b: str, lectura: dict, momento: str) -> dict:
    return {
        "momento": momento,
        "tipo": tipo,
        "clave": clave,
        "valor_principal": "" if principal is None else principal,
        "fuente_principal": fuente_a,
        "valor_contraste": "" if contraste is None else contraste,
        "fuente_contraste": fuente_b,
        "diferencia_pct": "" if lectura.get("diferencia") is None else lectura["diferencia"],
        "estado": lectura["estado"],
        "motivo": lectura.get("motivo") or "",
    }


def cuadro_cambiario(
    *,
    ccl_calculado: float | None,
    sesion=None,
    momento: str = "",
    log_ruta=None,
) -> dict:
    """MEP y CCL contra ArgentinaDatos, oficial contra el BCRA, riesgo país contra ArgentinaDatos."""
    mep_feed = mep_data912(panel_mep(sesion))
    ccl_feed = ccl_data912(panel_ccl(sesion))
    dolares = dolares_argentina(sesion) or {}
    bcra = oficial_bcra(sesion)
    ambito = riesgo_ambito(sesion)
    riesgo_ad = riesgo_argentina(sesion)

    mep_ad = _punto_medio(dolares.get("bolsa"))
    ccl_ad = _punto_medio(dolares.get("contadoconliqui"))
    mayorista_ad = None
    mayorista = dolares.get("mayorista") or {}
    if mayorista.get("venta") is not None:
        try:
            mayorista_ad = float(mayorista["venta"])
        except (TypeError, ValueError):
            mayorista_ad = None
    oficial_bcra_valor = None if not bcra else bcra.get("valor")
    riesgo_principal = None if not ambito else ambito.get("valor")
    riesgo_contraste = None if not riesgo_ad else riesgo_ad.get("valor")

    ccl_principal = ccl_calculado if ccl_calculado is not None else ccl_feed
    ccl_fuente = "pares verificados" if ccl_calculado is not None else "data912 (varios tickers)"

    piezas = {
        "mep": semaforo(mep_feed, mep_ad, es_dolar=True),
        "ccl": semaforo(ccl_principal, ccl_ad, es_dolar=True),
        "oficial": semaforo(oficial_bcra_valor, mayorista_ad, es_dolar=True),
        "riesgo": semaforo(riesgo_principal, riesgo_contraste, es_dolar=False),
    }
    valores = {
        "mep": (mep_feed, "data912", mep_ad, "ArgentinaDatos bolsa"),
        "ccl": (ccl_principal, ccl_fuente, ccl_ad, "ArgentinaDatos CCL"),
        "oficial": (oficial_bcra_valor, "BCRA mayorista de referencia", mayorista_ad, "ArgentinaDatos mayorista"),
        "riesgo": (riesgo_principal, "Ámbito", riesgo_contraste, "ArgentinaDatos"),
    }
    for clave, lectura in piezas.items():
        principal, fuente_a, contraste, fuente_b = valores[clave]
        lectura["principal"] = principal
        lectura["contraste"] = contraste
        lectura["fuente_principal"] = fuente_a
        lectura["fuente_contraste"] = fuente_b
        if lectura["estado"] == AMARILLO and lectura["motivo"] == "Sin segunda fuente para contrastar.":
            pass
        if log_ruta is not None:
            registrar_desvio(
                log_ruta,
                _fila_log(clave, clave, principal, fuente_a, contraste, fuente_b, lectura, momento),
            )
    piezas["ccl_feed"] = ccl_feed
    piezas["fechas"] = {
        "bcra": None if not bcra else bcra.get("fecha"),
        "riesgo_ambito": None if not ambito else ambito.get("fecha"),
        "riesgo_argentina": None if not riesgo_ad else riesgo_ad.get("fecha"),
        "mayorista": mayorista.get("fecha"),
        "bolsa": (dolares.get("bolsa") or {}).get("fecha"),
        "ccl": (dolares.get("contadoconliqui") or {}).get("fecha"),
    }
    return piezas
