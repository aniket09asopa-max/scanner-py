import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/"
}

def send_alert(message: str):
    """Dispatches formatted message directly to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[!] Preview:\n{message}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("[+] Alert successfully sent to Telegram!")
    except Exception as e:
        print(f"[!] Error: {e}")

class FridayTradesViewer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._init_session()

    def _init_session(self):
        try:
            self.session.get("https://www.nseindia.com", timeout=12)
            self.session.get("https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", timeout=12)
        except Exception as e:
            print(f"[!] Session setup note: {e}")

    # 1. SEND LATEST PROMOTER / INSIDER DISCLOSURES FROM LAST SESSION
    def send_recent_pit_filings(self):
        print("\n[*] Fetching Recent Insider & Promoter Trades...")
        from_dt = (datetime.now() - timedelta(days=5)).strftime("%d-%m-%Y")
        to_dt = datetime.now().strftime("%d-%m-%Y")
        url = f"https://www.nseindia.com/api/corporates-pit?from_date={from_dt}&to_date={to_dt}"

        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200:
                return

            records = resp.json().get("data", [])
            print(f"[✓] Found {len(records)} recent insider filings.")

            # Send the top 5 most recent trades to Telegram
            count = 0
            for row in records:
                if count >= 5:
                    break

                symbol = row.get("symbol", "")
                acq_name = row.get("acqName", "Undisclosed")
                category = row.get("personCategory", "Insider")
                action = row.get("acqMode", "Purchase")
                sec_val = row.get("secVal", "0")
                sec_acq = row.get("secAcq", "0")
                sec_type = row.get("secType", "Equity")

                if symbol:
                    msg = (
                        f"👑 <b>RECENT PROMOTER / INSIDER TRADE</b>\n\n"
                        f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                        f"• <b>Entity:</b> {acq_name}\n"
                        f"• <b>Category:</b> {category}\n"
                        f"• <b>Action:</b> {action}\n"
                        f"• <b>Shares:</b> {sec_acq}\n"
                        f"• <b>Value:</b> ₹{sec_val}\n"
                        f"• <b>Type:</b> {sec_type}\n"
                        f"<i>Verified Official SEBI PIT Filing</i>"
                    )
                    send_alert(msg)
                    count += 1
                    time.sleep(0.5)

        except Exception as e:
            print(f"[!] PIT scan error: {e}")

    # 2. SEND LATEST BULK / BLOCK DEALS FROM FRIDAY
    def send_recent_bulk_deals(self):
        print("\n[*] Fetching Latest Bulk & Block Deals...")
        url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"

        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200:
                return

            json_data = resp.json()
            deals = json_data.get("BULK_DEALS_DATA", []) + json_data.get("BLOCK_DEALS_DATA", [])
            print(f"[✓] Found {len(deals)} recent large deals.")

            # Send top 5 most recent bulk/block trades to Telegram
            count = 0
            for deal in deals:
                if count >= 5:
                    break

                symbol = deal.get("symbol", "")
                client = deal.get("clientName", "HNI / Institution")
                action = deal.get("buySell", "Trade")
                qty = deal.get("quantityTraded", "0")
                price = deal.get("tradePrice", "0")
                deal_type = deal.get("dealType", "Bulk/Block Deal")

                if symbol:
                    msg = (
                        f"🐋 <b>LATEST LARGE DEAL ({deal_type})</b>\n\n"
                        f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                        f"• <b>Client:</b> {client}\n"
                        f"• <b>Action:</b> {action.upper()}\n"
                        f"• <b>Trade Price:</b> ₹{price}\n"
                        f"• <b>Quantity:</b> {qty}\n"
                        f"<i>Verified Official NSE Large Deal Ledger</i>"
                    )
                    send_alert(msg)
                    count += 1
                    time.sleep(0.5)

        except Exception as e:
            print(f"[!] Bulk deal scan error: {e}")

    def run(self):
        send_alert("📊 <b>PULLING LATEST FRIDAY DISCLOSURES & TRADES...</b>")
        self.send_recent_pit_filings()
        self.send_recent_bulk_deals()

if __name__ == "__main__":
    viewer = FridayTradesViewer()
    viewer.run()
