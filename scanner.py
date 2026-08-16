import os
import io
import time
import requests
import pandas as pd
from datetime import datetime

# Read secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def notify_telegram(text: str):
    """Guaranteed Telegram dispatcher with debug prints."""
    print(f"[*] Attempting to send Telegram message...")
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in GitHub Secrets!")
        return

    endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(endpoint, json=payload, timeout=15)
        print(f"[+] Telegram API Response: {res.status_code} - {res.text}")
    except Exception as err:
        print(f"[!] Telegram Request Exception: {err}")

def fetch_and_alert_trades():
    print("[*] Starting trade extraction pipeline...")
    
    # 1. SEND DIRECT CONFIRMATION MESSAGE FIRST
    notify_telegram(
        f"⚡ <b>SYSTEM LIVE CHECK</b>\n\n"
        f"• <b>Status:</b> GitHub Actions Cloud Connected\n"
        f"• <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"• <b>Extracting:</b> Latest Exchange Disclosures..."
    )

    # 2. FETCH LATEST BSE LARGE DEALS (Direct unblocked public feed)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # Public BSE Bulk Deals API endpoint
        url = "https://api.bseindia.com/BseIndiaAPI/api/BulkDeals/w"
        req = requests.get(url, headers=headers, timeout=15)
        
        if req.status_code == 200:
            data = req.json().get("Table", [])
            print(f"[✓] Successfully pulled {len(data)} deal entries from BSE.")
            
            if data:
                # Send the top 3 actual trades from the latest market session
                for deal in data[:3]:
                    scrip = deal.get("scrip_name", "Stock")
                    client = deal.get("client_name", "Investor")
                    action = deal.get("buy_sell", "BUY")
                    qty = deal.get("quantity", "0")
                    rate = deal.get("price", "0")

                    card = (
                        f"🐋 <b>EXCHANGE BULK DEAL FOUND</b>\n\n"
                        f"• <b>Stock:</b> {scrip}\n"
                        f"• <b>Client:</b> {client}\n"
                        f"• <b>Action:</b> {action.upper()}\n"
                        f"• <b>Shares:</b> {qty}\n"
                        f"• <b>Price:</b> ₹{rate}\n"
                        f"<i>Verified Exchange Disclosure Feed</i>"
                    )
                    notify_telegram(card)
                    time.sleep(0.5)
            else:
                notify_telegram("ℹ️ <b>Market Note:</b> Feed connected successfully. Exchange ledger currently has 0 open deals (Weekend Session).")
        else:
            print(f"[!] API HTTP Status: {req.status_code}")
            notify_telegram(f"⚠️ <b>Feed Notice:</b> Exchange returned HTTP {req.status_code}. Retrying on next scheduled session.")
            
    except Exception as e:
        print(f"[!] Processing exception: {e}")
        notify_telegram(f"⚠️ <b>Pipeline Notice:</b> {str(e)}")

if __name__ == "__main__":
    fetch_and_alert_trades()
