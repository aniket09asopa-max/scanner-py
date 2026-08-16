import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# CREDENTIALS VIA GITHUB SECRETS
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/"
}

def send_alert(message: str):
    """Dispatches instant formatted alert to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[!] Alert Preview (Secrets missing):\n{message}\n")
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
            print("[+] Alert sent to Telegram!")
        else:
            print(f"[!] Telegram API error: {r.text}")
    except Exception as e:
        print(f"[!] Failed to send Telegram alert: {e}")

class NSEOfficialSurveillanceEngine:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._init_session()

    def _init_session(self):
        """Pre-fetch cookies from the NSE homepage."""
        try:
            self.session.get("https://www.nseindia.com", timeout=12)
            self.session.get("https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", timeout=12)
        except Exception as e:
            print(f"[!] Session warmup note: {e}")

    # -------------------------------------------------------------
    # 1. 👑 PROMOTER & INSIDER BUYING (SEBI PIT REG 7 DISCLOSURES)
    # -------------------------------------------------------------
    def check_promoter_insider_filings(self):
        print("\n[*] 1. Scanning SEBI PIT Insider Filings (Official NSE Feed)...")
        from_dt = (datetime.now() - timedelta(days=7)).strftime("%d-%m-%Y")
        to_dt = datetime.now().strftime("%d-%m-%Y")
        url = f"https://www.nseindia.com/api/corporates-pit?from_date={from_dt}&to_date={to_dt}"

        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200:
                print(f"[!] PIT endpoint returned status: {resp.status_code}")
                return []

            data = resp.json().get("data", [])
            print(f"[✓] Retrieved {len(data)} statutory insider filings from NSE.")
            active_symbols = []

            for row in data:
                category = str(row.get("personCategory", "")).strip()
                action = str(row.get("acqMode", "")).upper()
                symbol = row.get("symbol", "")
                acq_name = row.get("acqName", "Undisclosed")
                sec_val = row.get("secVal", "0")
                sec_acq = row.get("secAcq", "0")

                # Filter for Promoter / Director / KMP buying
                is_promoter_group = any(p in category.upper() for p in ["PROMOTER", "DIRECTOR", "KMP", "PROMOTER GROUP"])
                is_buy = any(b in action for b in ["MARKET PURCHASE", "ACQUISITION", "BUY", "PREFERENTIAL", "SUBSCRIPTION"])

                if is_promoter_group and is_buy and symbol:
                    active_symbols.append(symbol)
                    msg = (
                        f"👑 <b>PROMOTER / INSIDER BUYING DETECTED</b> 👑\n\n"
                        f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                        f"• <b>Entity:</b> {acq_name}\n"
                        f"• <b>Designation:</b> {category}\n"
                        f"• <b>Mode:</b> {action}\n"
                        f"• <b>Quantity Bought:</b> {sec_acq}\n"
                        f"• <b>Total Value:</b> ₹{sec_val}\n"
                        f"• <b>Official Filing:</b> SEBI PIT Reg 7(2)\n"
                        f"<i>Verified via NSE Corporate Disclosures</i>"
                    )
                    send_alert(msg)
                    time.sleep(0.3)

            return list(set(active_symbols))
        except Exception as e:
            print(f"[!] PIT Scanner error: {e}")
            return []

    # -------------------------------------------------------------
    # 2. 🐋 LARGE BULK & BLOCK DEAL BUYING (HNI / Non-DII Whales)
    # -------------------------------------------------------------
    def check_bulk_block_deals(self):
        print("\n[*] 2. Scanning Daily Bulk & Block Deals (Official NSE Ledger)...")
        url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"

        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200:
                print(f"[!] Large deal endpoint returned status: {resp.status_code}")
                return []

            json_data = resp.json()
            deals = json_data.get("BULK_DEALS_DATA", []) + json_data.get("BLOCK_DEALS_DATA", [])
            print(f"[✓] Retrieved {len(deals)} large exchange transactions.")
            active_symbols = []

            for deal in deals:
                action = str(deal.get("buySell", "")).upper()
                client = str(deal.get("clientName", "")).strip()
                symbol = deal.get("symbol", "")
                qty = deal.get("quantityTraded", "0")
                price = deal.get("tradePrice", "0")
                deal_type = deal.get("dealType", "Bulk/Block")

                if "BUY" in action and symbol:
                    active_symbols.append(symbol)
                    msg = (
                        f"🐋 <b>WHALE BULK / BLOCK DEAL BUY</b> 🐋\n\n"
                        f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                        f"• <b>Buyer:</b> {client}\n"
                        f"• <b>Price:</b> ₹{price}\n"
                        f"• <b>Quantity:</b> {qty}\n"
                        f"• <b>Segment:</b> {deal_type}\n"
                        f"<i>Verified via NSE Daily Large Deal Ledger</i>"
                    )
                    send_alert(msg)
                    time.sleep(0.3)

            return list(set(active_symbols))
        except Exception as e:
            print(f"[!] Large Deal Scanner error: {e}")
            return []

    # -------------------------------------------------------------
    # 3. ⚡ DERIVATIVES OTM OI ANOMALIES (The "IEX" Pattern)
    # -------------------------------------------------------------
    def check_derivatives_anomalies(self, target_watchlist: list):
        print(f"\n[*] 3. Scanning Option Chains for OTM OI Spikes ({len(target_watchlist)} stocks)...")

        for symbol in target_watchlist:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    continue

                records = resp.json().get("records", {})
                spot = records.get("underlyingValue", 0)
                chain = records.get("data", [])

                for row in chain:
                    strike = row.get("strikePrice", 0)

                    # Deep OTM Call Spike (>4% above spot)
                    if "CE" in row and strike > spot * 1.04:
                        ce_oi_change = row["CE"].get("changeinOpenInterest", 0)
                        if ce_oi_change >= 250_000:
                            msg = (
                                f"⚡ <b>DERIVATIVES SURGE: CALL BUYING</b> ⚡\n\n"
                                f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                                f"• <b>Spot:</b> ₹{spot}\n"
                                f"• <b>OTM Strike:</b> ₹{strike}\n"
                                f"• <b>OI Addition:</b> +{ce_oi_change:,} shares\n"
                                f"• <b>Signal:</b> Aggressive Bullish Positioning\n"
                                f"<i>Verified via NSE Derivatives Chain</i>"
                            )
                            send_alert(msg)

                    # Deep OTM Put Spike (>4% below spot)
                    if "PE" in row and strike < spot * 0.96:
                        pe_oi_change = row["PE"].get("changeinOpenInterest", 0)
                        if pe_oi_change >= 250_000:
                            msg = (
                                f"⚡ <b>DERIVATIVES SURGE: PUT BUYING</b> ⚡\n\n"
                                f"• <b>Stock:</b> <code>#{symbol}</code>\n"
                                f"• <b>Spot:</b> ₹{spot}\n"
                                f"• <b>OTM Strike:</b> ₹{strike}\n"
                                f"• <b>OI Addition:</b> +{pe_oi_change:,} shares\n"
                                f"• <b>Signal:</b> Aggressive Bearish/Hedging Buildup\n"
                                f"<i>Verified via NSE Derivatives Chain</i>"
                            )
                            send_alert(msg)

                time.sleep(0.4)
            except Exception:
                continue

    # -------------------------------------------------------------
    # 4. MASTER RUNNER (RUNS ALL INDEPENDENTLY & PINGS TELEGRAM)
    # -------------------------------------------------------------
    def run_full_market_surveillance(self):
        # Startup ping
        test_ping = (
            f"🚀 <b>NSE MARKET SURVEILLANCE RUNNING</b>\n\n"
            f"• <b>Status:</b> Scanning Official Exchange Disclosures\n"
            f"• <b>Execution Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        send_alert(test_ping)

        # 1. Promoter buys
        pit_symbols = self.check_promoter_insider_filings()

        # 2. Bulk/Block deals
        bulk_symbols = self.check_bulk_block_deals()

        # 3. Derivatives on active candidates + core high-beta F&O names
        core_fno = ["IEX", "TATAPOWER", "RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN", "ADANIENT", "ADANIPORTS", "VEDL", "ITC"]
        combined_watchlist = list(set(pit_symbols + bulk_symbols + core_fno))
        self.check_derivatives_anomalies(combined_watchlist)

        print("\n[✓] Surveillance Run Complete.")


if __name__ == "__main__":
    engine = NSEOfficialSurveillanceEngine()
    engine.run_full_market_surveillance()
