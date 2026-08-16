import os
import time
import requests
from datetime import datetime

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_alert(message: str):
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
            print("[+] Sent to Telegram!")
        else:
            print(f"[!] Telegram error: {r.text}")
    except Exception as e:
        print(f"[!] Alert error: {e}")

class IndianMarketDisclosures:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/json, text/plain, */*"
        }

    # 1. PULL RECENT SEBI PIT INSIDER / PROMOTER FILINGS VIA BSE
    def get_pit_insider_trades(self):
        print("[*] Fetching Official Insider / Promoter Filings...")
        url = "https://api.bseindia.com/BseIndiaAPI/api/InsiderTrading/w?page_no=1"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code != 200:
                print(f"[!] BSE PIT API returned status: {resp.status_code}")
                return

            data = resp.json().get("Table", [])
            print(f"[✓] Retrieved {len(data)} statutory insider filings.")

            count = 0
            for item in data:
                if count >= 6:
                    break

                symbol = item.get("scrip_code", item.get("SYMBOL", ""))
                company = item.get("scrip_name", item.get("COMPANY_NAME", "Indian Co"))
                acq_name = item.get("person_name", item.get("ACQ_NAME", "Promoter/Director"))
                person_cat = item.get("person_category", item.get("CATEGORY", "Insider"))
                action = item.get("mode_of_acq", item.get("ACQ_MODE", "Market Purchase"))
                qty = item.get("no_of_sec_acq", item.get("QUANTITY", "0"))
                val = item.get("val_of_sec_acq", item.get("VALUE", "0"))

                msg = (
                    f"👑 <b>PROMOTER / INSIDER TRADE FILING</b> 👑\n\n"
                    f"• <b>Company:</b> {company} (<code>#{symbol}</code>)\n"
                    f"• <b>Entity:</b> {acq_name}\n"
                    f"• <b>Category:</b> {person_cat}\n"
                    f"• <b>Action:</b> {action}\n"
                    f"• <b>Shares:</b> {qty}\n"
                    f"• <b>Value:</b> ₹{val}\n"
                    f"<i>Official Statutory SEBI PIT Disclosure</i>"
                )
                send_alert(msg)
                count += 1
                time.sleep(0.5)

        except Exception as e:
            print(f"[!] Error reading PIT filings: {e}")

    # 2. PULL RECENT BULK & BLOCK DEALS VIA BSE
    def get_bulk_block_deals(self):
        print("[*] Fetching Official Bulk & Block Deals...")
        url = "https://api.bseindia.com/BseIndiaAPI/api/BulkDeals/w"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code != 200:
                print(f"[!] BSE Bulk Deals API returned status: {resp.status_code}")
                return

            data = resp.json().get("Table", [])
            print(f"[✓] Retrieved {len(data)} large deal transactions.")

            count = 0
            for item in data:
                if count >= 6:
                    break

                company = item.get("scrip_name", "Indian Equity")
                client = item.get("client_name", "HNI / Fund")
                deal_type = item.get("deal_type", "Bulk Deal")
                qty = item.get("quantity", "0")
                price = item.get("price", "0")
                action = item.get("buy_sell", "BUY")

                msg = (
                    f"🐋 <b>LARGE BULK / BLOCK DEAL</b> 🐋\n\n"
                    f"• <b>Company:</b> {company}\n"
                    f"• <b>Client:</b> {client}\n"
                    f"• <b>Action:</b> {action.upper()}\n"
                    f"• <b>Trade Price:</b> ₹{price}\n"
                    f"• <b>Quantity:</b> {qty}\n"
                    f"• <b>Type:</b> {deal_type}\n"
                    f"<i>Official Exchange Bulk Deal Ledger</i>"
                )
                send_alert(msg)
                count += 1
                time.sleep(0.5)

        except Exception as e:
            print(f"[!] Error reading Bulk Deals: {e}")

    def run(self):
        self.get_pit_insider_trades()
        self.get_bulk_block_deals()

if __name__ == "__main__":
    scanner = IndianMarketDisclosures()
    scanner.run()
