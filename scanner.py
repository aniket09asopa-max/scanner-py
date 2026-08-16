import os
import time
import json
import hashlib
import requests
from datetime import datetime

# ==========================================
# CREDENTIALS & PERSISTENCE CONFIG
# ==========================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
STATE_FILE = "seen_trades.json"

def load_seen_hashes() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[!] Error loading state cache: {e}")
    return set()

def save_seen_hashes(seen_set: set):
    try:
        with open(STATE_FILE, "w") as f:
            # Retain the most recent 1000 hashes to prevent unbound file growth
            json.dump(list(seen_set)[-1000:], f)
    except Exception as e:
        print(f"[!] Error saving state cache: {e}")

def send_alert(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[!] Telegram credentials missing. Alert preview:\n{message}\n")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code != 200:
            print(f"[!] Telegram API error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[!] Telegram post failed: {e}")

class InstitutionalMarketRadar:
    def __init__(self):
        self.bse_session = requests.Session()
        self.nse_session = requests.Session()
        self.seen_hashes = load_seen_hashes()
        self.initial_seen_count = len(self.seen_hashes)
        self.flagged_stocks = {}

        self.bse_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com"
        }
        self.nse_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/"
        }
        self._init_nse_session()

    def _init_nse_session(self):
        try:
            self.nse_session.get("https://www.nseindia.com", headers=self.nse_headers, timeout=10)
            time.sleep(1.0)
        except Exception as e:
            print(f"[!] NSE session initialization notice: {e}")

    def _generate_record_hash(self, *args) -> str:
        raw_str = "|".join(str(a).strip().upper() for a in args)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def _record_confluence_flag(self, symbol: str, reason: str):
        symbol = str(symbol).upper().strip()
        if symbol not in self.flagged_stocks:
            self.flagged_stocks[symbol] = []
        self.flagged_stocks[symbol].append(reason)

    # -------------------------------------------------------------
    # 1. PROMOTER & INSIDER BUYING (BSE PIT ENDPOINT)
    # -------------------------------------------------------------
    def scan_promoter_insiders(self):
        print("\n[*] 1. Scanning SEBI PIT Insider Filings...")
        url = "https://api.bseindia.com/BseIndiaAPI/api/InsiderTrading/w?page_no=1"

        try:
            resp = self.bse_session.get(url, headers=self.bse_headers, timeout=12)
            if resp.status_code != 200:
                print(f"[!] BSE PIT API returned HTTP {resp.status_code}")
                return

            if not resp.text.strip().startswith("{"):
                print("[!] BSE PIT returned non-JSON response.")
                return

            data = resp.json().get("Table", [])
            print(f"[✓] Retrieved {len(data)} PIT records from BSE API.")

            if data:
                # Diagnostic Schema Check: Print raw keys of first record
                print(f"[Debug] Raw Sample PIT Keys: {list(data[0].keys())}")

            for item in data:
                # Schema extraction with fallbacks
                cat = str(item.get("person_category", item.get("CATEGORY", item.get("sec_type", "")))).upper().strip()
                mode = str(item.get("mode_of_acq", item.get("ACQ_MODE", item.get("tdp_mode", "")))).upper().strip()
                company = item.get("scrip_name", item.get("COMPANY_NAME", item.get("company", ""))).strip()
                scrip_code = str(item.get("scrip_code", item.get("SCRIP_CD", ""))).strip()
                person = item.get("person_name", item.get("ACQ_NAME", item.get("tdp_name", ""))).strip()
                qty = str(item.get("no_of_sec_acq", item.get("QUANTITY", item.get("tdp_acq_no", "0")))).strip()
                val = str(item.get("val_of_sec_acq", item.get("VALUE", item.get("tdp_val", "0")))).strip()

                # Discard if critical data fields are missing
                if not company and not scrip_code:
                    continue

                is_promoter = any(p in cat for p in ["PROMOTER", "DIRECTOR", "KMP", "PROMOTER GROUP"])
                is_buy = any(b in mode for b in ["MARKET PURCHASE", "ACQUISITION", "BUY", "PREFERENTIAL", "SUBSCRIPTION"])

                if is_promoter and is_buy:
                    record_hash = self._generate_record_hash("PIT", scrip_code or company, person, qty, val)
                    if record_hash in self.seen_hashes:
                        continue

                    card = (
                        f"👑 <b>PROMOTER / INSIDER ACQUISITION</b>\n\n"
                        f"• <b>Company:</b> {company or 'Scrip'} (<code>{scrip_code}</code>)\n"
                        f"• <b>Insider:</b> {person or 'Undisclosed'}\n"
                        f"• <b>Designation:</b> {cat}\n"
                        f"• <b>Mode:</b> {mode}\n"
                        f"• <b>Shares Acquired:</b> {qty}\n"
                        f"• <b>Reported Value:</b> ₹{val}\n"
                        f"<i>Feed: BSE API (InsiderTrading)</i>"
                    )
                    send_alert(card)
                    self.seen_hashes.add(record_hash)
                    self._record_confluence_flag(company or scrip_code, "Promoter/Insider Acquisition")
                    time.sleep(0.4)

        except Exception as e:
            print(f"[!] Error in scan_promoter_insiders: {e}")

    # -------------------------------------------------------------
    # 2. BULK & BLOCK DEALS (BSE LARGE DEAL ENDPOINT)
    # -------------------------------------------------------------
    def scan_bulk_block_deals(self):
        print("\n[*] 2. Scanning Daily Bulk & Block Deals...")
        url = "https://api.bseindia.com/BseIndiaAPI/api/BulkDeals/w"

        try:
            resp = self.bse_session.get(url, headers=self.bse_headers, timeout=12)
            if resp.status_code != 200:
                print(f"[!] BSE Bulk Deals API returned HTTP {resp.status_code}")
                return

            if not resp.text.strip().startswith("{"):
                print("[!] BSE Bulk Deals returned non-JSON response.")
                return

            data = resp.json().get("Table", [])
            print(f"[✓] Retrieved {len(data)} large deal records from BSE API.")

            if data:
                # Diagnostic Schema Check: Print raw keys of first record
                print(f"[Debug] Raw Sample Bulk Deal Keys: {list(data[0].keys())}")

            for deal in data:
                action = str(deal.get("buy_sell", deal.get("BUY_SELL", ""))).upper().strip()
                company = deal.get("scrip_name", deal.get("COMPANY_NAME", deal.get("scripname", ""))).strip()
                scrip_code = str(deal.get("scrip_code", deal.get("SCRIP_CD", ""))).strip()
                client = deal.get("client_name", deal.get("CLIENT_NAME", deal.get("clientname", ""))).strip()
                qty = str(deal.get("quantity", deal.get("QUANTITY", "0"))).strip()
                price = str(deal.get("price", deal.get("PRICE", deal.get("rate", "0")))).strip()
                deal_type = deal.get("deal_type", "Bulk Deal")

                if not company and not scrip_code:
                    continue

                if "BUY" in action:
                    record_hash = self._generate_record_hash("BULK", scrip_code or company, client, qty, price)
                    if record_hash in self.seen_hashes:
                        continue

                    card = (
                        f"🐋 <b>EXCHANGE {str(deal_type).upper()} BUY</b>\n\n"
                        f"• <b>Company:</b> {company or 'Scrip'} (<code>{scrip_code}</code>)\n"
                        f"• <b>Buyer:</b> {client or 'Undisclosed'}\n"
                        f"• <b>Action:</b> {action}\n"
                        f"• <b>Quantity:</b> {qty}\n"
                        f"• <b>Trade Price:</b> ₹{price}\n"
                        f"<i>Feed: BSE API (BulkDeals)</i>"
                    )
                    send_alert(card)
                    self.seen_hashes.add(record_hash)
                    self._record_confluence_flag(company or scrip_code, f"Whale {deal_type} Buy")
                    time.sleep(0.4)

        except Exception as e:
            print(f"[!] Error in scan_bulk_block_deals: {e}")

    # -------------------------------------------------------------
    # 3. DERIVATIVES OTM OI SURGE (DYNAMIC RATIO ANALYSIS)
    # -------------------------------------------------------------
    def scan_derivatives_spikes(self):
        print("\n[*] 3. Scanning Options Chains for Dynamic OI Surges...")
        watchlist = ["IEX", "TATAPOWER", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "ADANIENT"]

        for symbol in watchlist:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
            try:
                resp = self.nse_session.get(url, headers=self.nse_headers, timeout=10)
                
                # Explicit diagnostics per symbol
                if resp.status_code == 401 or resp.status_code == 403:
                    print(f"[!] NSE WAF rate-limited on {symbol} (HTTP {resp.status_code}). Refreshing session...")
                    self._init_nse_session()
                    time.sleep(2.0)
                    continue
                elif resp.status_code != 200:
                    print(f"[!] NSE returned HTTP {resp.status_code} for {symbol}")
                    continue

                if not resp.text.strip().startswith("{"):
                    print(f"[!] Non-JSON payload returned for {symbol}")
                    continue

                records = resp.json().get("records", {})
                spot = records.get("underlyingValue", 0)
                chain = records.get("data", [])

                if spot <= 0 or not chain:
                    print(f"[-] {symbol}: No active chain/spot data found.")
                    continue

                for item in chain:
                    strike = item.get("strikePrice", 0)

                    # Dynamic OTM Call Check (>3.5% above spot)
                    if "CE" in item and strike > spot * 1.035:
                        ce = item["CE"]
                        ce_oi = ce.get("openInterest", 0)
                        ce_chg = ce.get("changeinOpenInterest", 0)
                        base_oi = ce_oi - ce_chg

                        # Ratio check: delta OI >= 50% of prior base, min net addition of 25,000 contracts
                        if base_oi > 0 and (ce_chg / base_oi) >= 0.50 and ce_chg >= 25000:
                            surge_pct = round((ce_chg / base_oi) * 100, 1)
                            record_hash = self._generate_record_hash("DERIV_CE", symbol, strike, ce_chg)
                            if record_hash in self.seen_hashes:
                                continue

                            card = (
                                f"⚡ <b>DERIVATIVES ANOMALY: OTM CALL SURGE</b>\n\n"
                                f"• <b>Symbol:</b> #{symbol}\n"
                                f"• <b>Spot:</b> ₹{spot}\n"
                                f"• <b>OTM Strike:</b> ₹{strike} (+{round(((strike/spot)-1)*100, 1)}% OTM)\n"
                                f"• <b>OI Surge:</b> +{surge_pct}% (+{ce_chg:,} contracts)\n"
                                f"• <b>Total Strike OI:</b> {ce_oi:,}\n"
                                f"<i>Feed: NSE Options Chain Live</i>"
                            )
                            send_alert(card)
                            self.seen_hashes.add(record_hash)
                            self._record_confluence_flag(symbol, f"OTM Call OI Surge (+{surge_pct}%)")
                            time.sleep(0.4)

                    # Dynamic OTM Put Check (>3.5% below spot)
                    if "PE" in item and strike < spot * 0.965:
                        pe = item["PE"]
                        pe_oi = pe.get("openInterest", 0)
                        pe_chg = pe.get("changeinOpenInterest", 0)
                        base_oi = pe_oi - pe_chg

                        if base_oi > 0 and (pe_chg / base_oi) >= 0.50 and pe_chg >= 25000:
                            surge_pct = round((pe_chg / base_oi) * 100, 1)
                            record_hash = self._generate_record_hash("DERIV_PE", symbol, strike, pe_chg)
                            if record_hash in self.seen_hashes:
                                continue

                            card = (
                                f"⚡ <b>DERIVATIVES ANOMALY: OTM PUT SURGE</b>\n\n"
                                f"• <b>Symbol:</b> #{symbol}\n"
                                f"• <b>Spot:</b> ₹{spot}\n"
                                f"• <b>OTM Strike:</b> ₹{strike} (-{round((1-(strike/spot))*100, 1)}% OTM)\n"
                                f"• <b>OI Surge:</b> +{surge_pct}% (+{pe_chg:,} contracts)\n"
                                f"• <b>Total Strike OI:</b> {pe_oi:,}\n"
                                f"<i>Feed: NSE Options Chain Live</i>"
                            )
                            send_alert(card)
                            self.seen_hashes.add(record_hash)
                            self._record_confluence_flag(symbol, f"OTM Put OI Surge (+{surge_pct}%)")
                            time.sleep(0.4)

                # Generous sleep to respect NSE rate-limit ceilings
                time.sleep(1.5)

            except Exception as e:
                print(f"[!] Error reading option chain for {symbol}: {e}")
                continue

    # -------------------------------------------------------------
    # 4. MULTI-SIGNAL CONFLUENCE EVALUATOR
    # -------------------------------------------------------------
    def evaluate_confluence(self):
        print("\n[*] 4. Checking Cross-Signal Confluence...")
        for stock, signals in self.flagged_stocks.items():
            if len(signals) >= 2:
                sig_list = "\n".join([f"  • {s}" for s in signals])
                card = (
                    f"🚨 <b>MULTI-SIGNAL CONFLUENCE DETECTED</b> 🚨\n\n"
                    f"• <b>Entity:</b> <code>#{stock}</code>\n"
                    f"• <b>Overlapping Indicators:</b>\n{sig_list}\n\n"
                    f"<i>Triggered across independent statutory disclosures and derivatives volume.</i>"
                )
                send_alert(card)
                time.sleep(0.5)

    def run(self):
        self.scan_promoter_insiders()
        self.scan_bulk_block_deals()
        self.scan_derivatives_spikes()
        self.evaluate_confluence()

        # Save updated deduplication registry
        if len(self.seen_hashes) != self.initial_seen_count:
            save_seen_hashes(self.seen_hashes)
            print(f"[✓] State file updated ({len(self.seen_hashes)} total records cached).")
        else:
            print("[✓] Scan complete. No new unique disclosures since last cycle.")

if __name__ == "__main__":
    radar = InstitutionalMarketRadar()
    radar.run()
