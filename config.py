"""
Configuración del trading scanner de equities.
"""
import os

# ── Activos a escanear ────────────────────────────────────────────────────────
SYMBOLS = ["SPMO", "QQQ", "VGT", "XLE", "XLF", "SPYM", "AVUV", "INTC"]

# ── Timeframes ────────────────────────────────────────────────────────────────
# Usados en el scan automático
TIMEFRAMES = ["H1", "D1"]

# ── Setup: parámetros ─────────────────────────────────────────────────────────
MIN_CONFLUENCES    = 4       # mínimo de condiciones para disparar alerta
FIB_LOW_LEVEL      = 0.382   # 38.2% de retroceso
FIB_HIGH_LEVEL     = 0.618   # 61.8% de retroceso
EMA_PERIODS        = [4, 9, 18]
MIN_PULLBACK_BARS  = 3       # mínimo de velas de retroceso
SWING_LOOKBACK     = 5       # velas a cada lado para detectar swing
BARS_LIMIT         = 120     # velas a buscar en la API

# ── Credenciales (desde variables de entorno / GitHub Secrets) ────────────────
ALPACA_API_KEY    = os.environ.get("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
