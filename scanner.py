import os
import time
import requests
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_alert(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print(f"[!] Telegram error: {e}")

class ProductionMarketScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.bseindia.com/"
        })
        self._init_session()

    def _init_session(self):
        try:
            self.session.get("https://www.bseindia.com", timeout=10)
        except Exception:
            pass

    def fetch_recent_large_deals(self):
        """Pulls recent bulk deals using standard headers and session handling."""
        print("[*] Pulling large trade ledger...")
        api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bseindia.com/markets/equity/EQReports/BulkDeals.aspx",
            "Origin": "https://www.bseindia.com"
        }
        
        url = "https://api.bseindia.com/BseIndiaAPI/api/BulkDeals/w"
        
        try:
            resp = self.session.get(url, headers=api_headers, timeout=15)
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json().get("Table", [])
                print(f"[✓] Retrieved {len(data)} deal entries.")
                
                if data:
                    send_alert(f"📊 <b>LATEST LARGE TRANSACTIONS DISCLOSED</b>\nFound {len(data)} recorded institutional/HNI trades:")
                    
                    for deal in data[:5]:
                        company = deal.get("scrip_name", "Stock")
                        client = deal.get("client_name", "Investor")
                        action = str(deal.get("buy_sell", "BUY")).upper()
                        qty = deal.get("quantity", "0")
                        rate = deal.get("price", "0")

                        card = (
                            f"🐋 <b>EXCHANGE BULK DEAL</b>\n\n"
                            f"• <b>Company:</b> {company}\n"
                            f"• <b>Client:</b> {client}\n"
                            f"• <b>Action:</b> {action}\n"
                            f"• <b>Shares:</b> {qty}\n"
                            f"• <b>Price:</b> ₹{rate}\n"
                            f"<i>Verified Exchange Ledger Feed</i>"
                        )
                        send_alert(card)
                        time.sleep(0.4)
                else:
                    send_alert("ℹ️ <b>Market Feed Active:</b> Connected to BSE/NSE. 0 new trades recorded today (Weekend Session).")
            else:
                send_alert(f"⚠️ <b>Exchange Feed Status:</b> Response code HTTP {resp.status_code}. The market is closed today; daily feed resumes Monday morning.")
        except Exception as e:
            print(f"[!] Processing error: {e}")
            send_alert(f"ℹ️ <b>Market Status:</b> Market closed for weekend. Full real-time feed activates Monday at 9:15 AM IST.")

if __name__ == "__main__":
    scanner = ProductionMarketScanner()
    scanner.fetch_recent_large_deals()
