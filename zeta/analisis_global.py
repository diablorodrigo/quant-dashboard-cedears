"""Sesgo global de un activo: la lectura técnica más el fundamental.

Recupera la cuenta de la pestaña Señal Global del panel original.
El técnico aporta +3, 0 o −3 según la lectura ya cerrada. El fundamental
mira valuación, consenso y margen, y se corta en ±2. El sesgo global
es alcista desde +3 y bajista desde −3. En el medio queda neutral.
"""

from __future__ import annotations

import math

from zeta.senales import (
    ALCISTA_CON_VOLUMEN,
    ALCISTA_SIN_VOLUMEN,
    SESGO_ALCISTA,
    SESGO_ALCISTA_MARCADO,
    SESGO_BAJISTA,
    SESGO_BAJISTA_MARCADO,
)

AVISO_GLOBAL = (
    "El contenido es informativo: son ideas de análisis, no constituyen recomendación de inversión."
)
TOPE_FUNDAMENTAL = 2
UMBRAL_SESGO = 3


def _finito(valor) -> bool:
    if valor is None:
        return False
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False


def _num(valor) -> float | None:
    if not _finito(valor):
        return None
    return float(valor)


def _signo(puntos: int) -> str:
    if puntos > 0:
        return f"+{puntos}"
    if puntos < 0:
        return f"−{abs(puntos)}"
    return "0"


def puntaje_tecnico(lectura: str) -> int:
    """El mismo peso que tenía la señal técnica en la Señal Global original."""
    if lectura in (
        SESGO_ALCISTA,
        SESGO_ALCISTA_MARCADO,
        ALCISTA_CON_VOLUMEN,
        ALCISTA_SIN_VOLUMEN,
    ):
        return 3
    if lectura in (SESGO_BAJISTA, SESGO_BAJISTA_MARCADO):
        return -3
    return 0


def _texto_tendencia(historia_corta: bool, precio_sobre_ema: bool | None, stage2: bool) -> str:
    if historia_corta or precio_sobre_ema is None:
        return "No hay suficientes ruedas para la EMA de 200. La tendencia no entra en la lectura."
    if precio_sobre_ema and stage2:
        return "El precio está sobre la EMA de 200 y esa media sube. La tendencia de largo acompaña."
    if precio_sobre_ema:
        return "El precio está sobre la EMA de 200, pero esa media no viene subiendo."
    return "El precio está debajo de la EMA de 200. La tendencia de largo no acompaña."


def _texto_medias(
    historia_corta: bool,
    medias_ordenadas: bool | None,
    precio_sobre_medias: bool | None,
) -> str:
    if historia_corta or medias_ordenadas is None:
        return "Sin cruce usable de las medias de 10 y de 20."
    if medias_ordenadas and precio_sobre_medias:
        return "La media de 10 está sobre la de 20 y el precio está arriba de ambas."
    if not medias_ordenadas and precio_sobre_medias:
        return "La media de 10 sigue bajo la de 20, pero el precio ya recuperó ambas."
    if not medias_ordenadas:
        return "La media de 10 está bajo la de 20 y el precio no recuperó ambas."
    return "La media de 10 está sobre la de 20."


def _texto_macd(estado: str | None) -> str:
    if estado == "arriba":
        return "El MACD está arriba de su señal."
    if estado == "girando":
        return "El MACD está bajo la señal, pero la curva ya gira al alza."
    if estado == "abajo":
        return "El MACD está bajo su señal y no gira al alza."
    return "Sin MACD para esta serie."


def _texto_rsi(rsi: float | None) -> str:
    if rsi is None:
        return "Sin RSI de 14 ruedas."
    if rsi <= 35:
        return f"RSI {rsi:.0f}. Está en zona de extremo bajo (35 o menos)."
    if rsi >= 70:
        return f"RSI {rsi:.0f}. Está en zona de extremo alto (70 o más)."
    return f"RSI {rsi:.0f}. Queda entre 35 y 70, sin extremo."


def _valuacion(per: float | None) -> tuple[int, str]:
    if per is None or per <= 0:
        return 0, "Sin PER en Yahoo. La valuación no suma ni resta."
    if per > 30:
        return -1, f"PER {per:.1f}. Resta 1: está por encima de 30."
    return 0, f"PER {per:.1f}. No resta: el criterio solo descuenta un PER por encima de 30."


def _consenso(upside: float | None, media: float | None, nombre: str | None) -> tuple[int, str]:
    firma = f" El consenso de las firmas es {nombre}." if nombre else ""
    if upside is not None:
        pct = upside * 100
        if upside > 0.15:
            return 1, f"El precio objetivo está {pct:.0f}% arriba del precio. Suma 1.{firma}"
        if upside < 0:
            return -1, f"El precio objetivo está {abs(pct):.0f}% debajo del precio. Resta 1.{firma}"
        return 0, (
            f"El precio objetivo está {pct:.0f}% arriba, por debajo del 15% que suma un punto.{firma}"
        )
    if media is not None:
        if media <= 2:
            return 1, f"No hay precio objetivo. El consenso de las firmas está del lado positivo. Suma 1.{firma}"
        if media >= 4:
            return -1, f"No hay precio objetivo. El consenso de las firmas está del lado cauto. Resta 1.{firma}"
        return 0, f"No hay precio objetivo. El consenso de las firmas queda en el medio. No suma ni resta.{firma}"
    return 0, "Sin precio objetivo ni consenso de analistas. No suma ni resta."


def _margen(margen: float | None, roe: float | None) -> tuple[int, str]:
    if margen is not None:
        pct = margen * 100
        if margen > 0.15:
            return 1, f"Margen neto {pct:.1f}%. Suma 1: está por encima de 15%."
        if margen < 0:
            return -1, f"Margen neto {pct:.1f}%. Resta 1: es negativo."
        return 0, f"Margen neto {pct:.1f}%. No suma: el umbral para sumar es 15%."
    if roe is not None:
        pct = roe * 100
        if roe > 0.15:
            return 1, f"Sin margen neto. El ROE es {pct:.1f}% y suma 1: está por encima de 15%."
        if roe < 0:
            return -1, f"Sin margen neto. El ROE es {pct:.1f}% y resta 1: es negativo."
        return 0, f"Sin margen neto. El ROE es {pct:.1f}% y no llega al 15% que suma un punto."
    return 0, "Sin margen neto ni ROE en Yahoo. No suma ni resta."


def _sesgo(combinado: int) -> str:
    if combinado >= UMBRAL_SESGO:
        return "Alcista"
    if combinado <= -UMBRAL_SESGO:
        return "Bajista"
    return "Neutral"


def _frase(tecnico: int, fundamental: int, combinado: int, sesgo: str) -> str:
    lado = "alcista" if sesgo == "Alcista" else "bajista" if sesgo == "Bajista" else "neutral"
    return (
        f"La lectura técnica aporta {_signo(tecnico)} y el fundamental {_signo(fundamental)}. "
        f"El puntaje combinado es {_signo(combinado)}: el sesgo global es {lado}."
    )


def armar_analisis_global(
    *,
    lectura: str,
    rsi: float | None = None,
    stage2: bool = False,
    precio_sobre_ema: bool | None = None,
    medias_ordenadas: bool | None = None,
    precio_sobre_medias: bool | None = None,
    macd_estado: str | None = None,
    per: float | None = None,
    precio: float | None = None,
    objetivo: float | None = None,
    consenso_media: float | None = None,
    consenso_nombre: str | None = None,
    margen: float | None = None,
    roe: float | None = None,
    historia_corta: bool = False,
) -> dict:
    """Arma el bloque. Los números no dependen de la hora en que se abre la página."""
    tecnico = puntaje_tecnico(lectura)
    per_n = _num(per)
    precio_n = _num(precio)
    objetivo_n = _num(objetivo)
    media_n = _num(consenso_media)
    margen_n = _num(margen)
    roe_n = _num(roe)
    rsi_n = _num(rsi)
    upside = None
    if precio_n and objetivo_n and precio_n > 0:
        upside = objetivo_n / precio_n - 1

    v_puntos, v_texto = _valuacion(per_n)
    c_puntos, c_texto = _consenso(upside, media_n, consenso_nombre)
    m_puntos, m_texto = _margen(margen_n, roe_n)
    bruto = v_puntos + c_puntos + m_puntos
    fundamental = max(-TOPE_FUNDAMENTAL, min(TOPE_FUNDAMENTAL, bruto))
    combinado = tecnico + fundamental
    sesgo = _sesgo(combinado)

    if historia_corta:
        intro = "Historia corta: el técnico aporta 0 porque no hay medias de largo plazo."
    elif tecnico == 0 and lectura and lectura != "Neutral":
        intro = f"La lectura «{lectura}» deja el aporte técnico en 0."
    else:
        intro = f"La lectura técnica de corto plazo es «{lectura}»."

    return {
        "sesgo": sesgo,
        "combinado": combinado,
        "tecnico": tecnico,
        "fundamental": fundamental,
        "fundamental_bruto": bruto,
        "recortado": fundamental != bruto,
        "intro": intro,
        "frase": _frase(tecnico, fundamental, combinado, sesgo),
        "tecnicos": [
            {"titulo": "Tendencia", "texto": _texto_tendencia(historia_corta, precio_sobre_ema, stage2)},
            {"titulo": "Medias", "texto": _texto_medias(historia_corta, medias_ordenadas, precio_sobre_medias)},
            {"titulo": "MACD", "texto": _texto_macd(macd_estado)},
            {"titulo": "RSI", "texto": _texto_rsi(rsi_n)},
        ],
        "fundamentales": [
            {"titulo": "Valuación", "puntos": v_puntos, "texto": v_texto},
            {"titulo": "Consenso", "puntos": c_puntos, "texto": c_texto},
            {"titulo": "Márgenes", "puntos": m_puntos, "texto": m_texto},
        ],
        "aviso": AVISO_GLOBAL,
    }
