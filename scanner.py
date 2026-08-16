import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

class MarketWideInsiderScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/"
        })
        self._init_session()

    def _init_session(self):
        try:
            self.session.get("https://www.nseindia.com", timeout=10)
        except Exception as e:
            print(f"[!] Session setup error: {e}")

    # 1. BATCH FETCH: All Bulk & Block Deals across the entire market
    def get_all_market_deals(self):
        url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                bulk_df = pd.DataFrame(data.get("BULK_DEALS_DATA", []))
                block_df = pd.DataFrame(data.get("BLOCK_DEALS_DATA", []))
                return pd.concat([bulk_df, block_df], ignore_index=True)
        except Exception:
            pass
        return pd.DataFrame()

    # 2. BATCH FETCH: All SEBI PIT Reg 7 Insider Filings (Past 7 Days)
    def get_all_market_pit(self):
        from_date = (datetime.now() - timedelta(days=7)).strftime("%d-%m-%Y")
        to_date = datetime.now().strftime("%d-%m-%Y")
        url = f"https://www.nseindia.com/api/corporates-pit?from_date={from_date}&to_date={to_date}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return pd.DataFrame(resp.json().get("data", []))
        except Exception:
            pass
        return pd.DataFrame()

    # 3. TARGETED DERIVATIVES SCAN: Only run on active candidates
    def scan_derivatives_anomaly(self, symbol):
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            records = resp.json().get("records", {})
            spot = records.get("underlyingValue", 0)
            chain = records.get("data", [])

            otm_puts = [
                row["PE"]["changeinOpenInterest"]
                for row in chain
                if "PE" in row and row.get("strikePrice", 0) < spot * 0.96
            ]
            otm_calls = [
                row["CE"]["changeinOpenInterest"]
                for row in chain
                if "CE" in row and row.get("strikePrice", 0) > spot * 1.04
            ]

            max_put_spike = max(otm_puts) if otm_puts else 0
            max_call_spike = max(otm_calls) if otm_calls else 0

            # Alert if single OTM strike has abnormal accumulation (>300k shares)
            if max_put_spike > 300_000 or max_call_spike > 300_000:
                return {
                    "spot": spot,
                    "max_otm_put_oi": max_put_spike,
                    "max_otm_call_oi": max_call_spike
                }
        except Exception:
            pass
        return None

    # 4. MASTER SCANNER
    def run_market_scan(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Pulling market-wide disclosures...")

        deals_df = self.get_all_market_deals()
        pit_df = self.get_all_market_pit()

        # Extract unique symbols active in deals or insider filings
        deal_symbols = set(deals_df["symbol"].dropna()) if not deals_df.empty else set()
        pit_symbols = set(pit_df["symbol"].dropna()) if not pit_df.empty else set()
        
        active_candidates = deal_symbols.union(pit_symbols)
        print(f"[*] Found {len(active_candidates)} stocks with active bulk/insider filings today.")

        for symbol in active_candidates:
            deriv_anomaly = self.scan_derivatives_anomaly(symbol)
            
            # Confluence check: Has deals/PIT disclosures AND unusual derivatives activity
            if deriv_anomaly:
                self.send_alert(symbol, deriv_anomaly, deals_df, pit_df)
            time.sleep(1)

    def send_alert(self, symbol, deriv, deals_df, pit_df):
        deal_count = len(deals_df[deals_df["symbol"] == symbol]) if not deals_df.empty else 0
        pit_count = len(pit_df[pit_df["symbol"] == symbol]) if not pit_df.empty else 0

        msg = (
            f"🚨 <b>MARKET ANOMALY: {symbol}</b> 🚨\n\n"
            f"• <b>Spot:</b> ₹{deriv['spot']}\n"
            f"• <b>OTM Put OI Spike:</b> +{deriv['max_otm_put_oi']:,}\n"
            f"• <b>OTM Call OI Spike:</b> +{deriv['max_otm_call_oi']:,}\n"
            f"• <b>Bulk Deals Active:</b> {deal_count}\n"
            f"• <b>Insider Filings (7D):</b> {pit_count}\n"
            f"<i>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        print(msg)
        if TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN":
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            )

if __name__ == "__main__":
    scanner = MarketWideInsiderScanner()
    scanner.run_market_scan()
