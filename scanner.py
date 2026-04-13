"""
Trading Scanner — Equities

Detecta setups de impulso + retroceso Fibonacci en H1 y D1.
Envía alertas por Telegram cuando se dan ≥4 confluencias.

Uso manual:
  python scanner.py                          # escanea todos los activos
  python scanner.py --symbol AAPL            # escanea AAPL en H1 y D1
  python scanner.py --symbol AAPL --timeframe H1
  python scanner.py --symbol AAPL --timeframe D1
"""
import argparse
import logging
import sys
from datetime import datetime, time as dtime
from typing import Optional

import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

import pandas as pd

from config import (
    SYMBOLS, TIMEFRAMES, BARS_LIMIT,
    ALPACA_API_KEY, ALPACA_API_SECRET,
    MIN_CONFLUENCES,
)
from indicators import analyze_setup
from alerts import format_alert, send_telegram_alert

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
NY_TZ = pytz.timezone("America/New_York")
MARKET_OPEN  = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)

_TF_MAP = {
    "H1": TimeFrame(1, TimeFrameUnit.Hour),
    "D1": TimeFrame(1, TimeFrameUnit.Day),
}

_TF_LABEL = {
    "H1": "1H",
    "D1": "D",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    """True si el mercado NYSE está abierto ahora."""
    now = datetime.now(NY_TZ)
    if now.weekday() >= 5:          # sábado (5) o domingo (6)
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def get_alpaca_client() -> StockHistoricalDataClient:
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        log.error("Faltan ALPACA_API_KEY / ALPACA_API_SECRET")
        sys.exit(1)
    return StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_API_SECRET)


def fetch_bars(client: StockHistoricalDataClient, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Descarga las últimas BARS_LIMIT velas para el símbolo y timeframe dados."""
    tf = _TF_MAP.get(timeframe)
    if tf is None:
        log.error(f"Timeframe '{timeframe}' no soportado. Usar H1 o D1.")
        return None

    try:
        req  = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=BARS_LIMIT)
        data = client.get_stock_bars(req)

        # Acceder a los objetos Bar directamente (más robusto que data.df)
        bars_data = data.data  # dict[symbol -> list[Bar]]
        key = symbol if symbol in bars_data else (list(bars_data)[0] if bars_data else None)
        if not key or not bars_data[key]:
            log.warning(f"{symbol} — sin datos en la respuesta de Alpaca")
            return None

        records = [
            {
                "timestamp": b.timestamp,
                "open":      float(b.open),
                "high":      float(b.high),
                "low":       float(b.low),
                "close":     float(b.close),
                "volume":    float(b.volume),
            }
            for b in bars_data[key]
        ]
        df = pd.DataFrame(records).set_index("timestamp")
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        return df[["open", "high", "low", "close", "volume"]]

    except Exception as e:
        log.warning(f"No se pudieron obtener datos para {symbol} ({timeframe}): {e}")
        return None


# ── Escaneo de un símbolo / timeframe ────────────────────────────────────────

def scan_one(client: StockHistoricalDataClient, symbol: str, timeframe: str) -> None:
    """Analiza bullish y bearish para un símbolo + timeframe y manda alertas si aplica."""
    log.info(f"Escaneando {symbol} [{timeframe}]...")

    df = fetch_bars(client, symbol, timeframe)
    if df is None or len(df) < 30:
        log.warning(f"{symbol} [{timeframe}] — datos insuficientes, saltando.")
        return

    tf_label = _TF_LABEL.get(timeframe, timeframe)

    for direction in ("bullish", "bearish"):
        try:
            result = analyze_setup(df, direction)
        except Exception as e:
            log.error(f"{symbol} [{timeframe}] {direction} — error en análisis: {e}")
            continue

        confluences = result.get("confluences", 0)
        valid       = result.get("valid", False)

        log.info(
            f"  {symbol} {tf_label} {direction}: "
            f"{confluences}/6 confluencias — {'✅ ALERTA' if valid else '❌ no setup'}"
        )

        if valid:
            message = format_alert(symbol, tf_label, result)
            log.info(f"\n{message}\n")
            send_telegram_alert(message)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Trading Scanner — detecta setups Fibonacci en equities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python scanner.py\n"
            "  python scanner.py --symbol AAPL\n"
            "  python scanner.py --symbol AAPL --timeframe H1\n"
            "  python scanner.py --force   # ignora chequeo de horario"
        ),
    )
    p.add_argument("--symbol",    type=str, help="Símbolo a escanear (ej: AAPL)")
    p.add_argument("--timeframe", type=str, default=None,
                   choices=["H1", "D1"],
                   help="Timeframe: H1 (1 hora) o D1 (diario). Default: ambos")
    p.add_argument("--force", action="store_true",
                   help="Ejecutar aunque el mercado esté cerrado")
    return p.parse_args()


def main() -> None:
    args   = parse_args()
    now_ny = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M ET")

    log.info("=" * 55)
    log.info(f"🔍 Trading Scanner — {now_ny}")
    log.info("=" * 55)

    # Determinar símbolos y timeframes
    symbols    = [args.symbol.upper()] if args.symbol else SYMBOLS
    timeframes = [args.timeframe] if args.timeframe else TIMEFRAMES

    # Verificar horario de mercado (solo en modo automático)
    manual_mode = bool(args.symbol or args.timeframe)
    if not manual_mode and not args.force:
        if not is_market_open():
            log.info("⏸  Mercado cerrado — no hay nada que escanear.")
            sys.exit(0)
    elif args.force:
        log.info("⚡ --force activo: ignorando chequeo de horario")

    client = get_alpaca_client()

    for symbol in symbols:
        for tf in timeframes:
            scan_one(client, symbol, tf)

    log.info("=" * 55)
    log.info("✔  Scan completado")


if __name__ == "__main__":
    main()
