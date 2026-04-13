"""
Envío de alertas por Telegram.
"""
import logging
import requests
from typing import Dict, Any

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

_TG_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Mapeo de condiciones a texto legible
_COND_LABELS = {
    "impulso":             "Impulso previo identificado",
    "retroceso":           "Retroceso ≥3 velas sin nuevo extremo",
    "fibonacci":           "Precio en zona Fibonacci 38.2%–61.8%",
    "emas_alineadas":      "EMAs 4/9/18 alineadas",
    "soporte_resistencia": "S/R coincidente con zona de retroceso",
    "vela_reversion":      "Patrón de vela de reversión",
}


def _check_mark(value: bool) -> str:
    return "✅" if value else "❌"


def format_alert(symbol: str, timeframe: str, result: Dict[str, Any]) -> str:
    """Formatea el mensaje de alerta para Telegram (HTML)."""
    direction   = result["direction"]
    arrow       = "📈" if direction == "bullish" else "📉"
    dir_label   = "ALCISTA" if direction == "bullish" else "BAJISTA"
    cond        = result["conditions"]
    confluences = result["confluences"]

    # Condiciones cumplidas
    cond_lines = []
    for key, label in _COND_LABELS.items():
        met = cond.get(key, False)
        suffix = ""
        if key == "vela_reversion" and met:
            suffix = f" — {cond.get('patron_vela', '')}"
        cond_lines.append(f"  {_check_mark(met)} {label}{suffix}")

    # EMAs
    emas = result.get("emas_values", {})
    ema_str = " | ".join(f"EMA{p}: {v}" for p, v in sorted(emas.items()))

    msg = (
        f"{arrow} <b>SETUP {dir_label} — {symbol} ({timeframe})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Confluencias:</b> {confluences}/6\n\n"
        f"<b>Condiciones detectadas:</b>\n"
        + "\n".join(cond_lines) + "\n\n"
        f"<b>Operativa sugerida:</b>\n"
        f"  🟢 Zona entrada : <code>${result['entry_low']:.4f} – ${result['entry_high']:.4f}</code>\n"
        f"  🔴 Stop loss    : <code>${result['stop_loss']:.4f}</code>\n\n"
        f"<b>EMAs actuales:</b>\n"
        f"  <code>{ema_str}</code>\n\n"
        f"💰 Precio actual : <code>${result['current_price']:.4f}</code>"
    )
    return msg


def send_telegram_alert(message: str) -> bool:
    """Envía un mensaje al chat de Telegram configurado. Retorna True si exitoso."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram no configurado (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID vacíos)")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       message,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("Alerta enviada a Telegram")
            return True
        log.error(f"Telegram respondió {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        log.error(f"Error enviando alerta a Telegram: {e}")
        return False
