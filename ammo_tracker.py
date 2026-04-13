#!/usr/bin/env python3
"""
AmmoSeek Price Tracker
Scrapes the top 2 cheapest listings for each saved search and stores them in ammo_prices.json.
Run daily (or via GitHub Actions cron).
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Saved searches - comment out any you don't want to track
# ---------------------------------------------------------------------------
SEARCHES = {
    "30_carbine": {
        "label": "30 Carbine",
        "url": "https://ammoseek.com/ammo/30-carbine?sh=average",
    },
    "30_06": {
        "label": "30-06",
        "url": "https://ammoseek.com/ammo/30-06?sh=low",
    },
    "300_aac_subsonic": {
        "label": ".300 AAC Blackout (Subsonic)",
        "url": "https://ammoseek.com/ammo/300aac-blackout?sh=average&ikw=subsonic&co=new",
    },
    "303_british": {
        "label": "303 British",
        "url": "https://ammoseek.com/ammo/303-british?sh=average",
    },
    "380_auto": {
        "label": ".380 Auto",
        "url": "https://ammoseek.com/ammo/380-auto?sh=average&ekw=Armsocor%20fiocchi%20sinterfire&co=new",
    },
    "556_nato": {
        "label": "5.56x45mm NATO",
        "url": "https://ammoseek.com/ammo/5.56x45mm-nato?sh=low&ekw=Igmab%20turan&co=new",
    },
    "75x55_swiss": {
        "label": "7.5x55mm Swiss",
        "url": "https://ammoseek.com/ammo/7.5x55mm-swiss",
    },
    "9mm_sb": {
        "label": "9mm Luger - Sellier & Bellot",
        "url": "https://ammoseek.com/ammo/9mm-luger/Sellier%20and%20Bellot?sh=lowest&ca=brass&co=new",
    },
    "9mm_excl_junk": {
        "label": "9mm Luger (Excl. junk brands)",
        "url": "https://ammoseek.com/ammo/9mm-luger?ekw=bps%20x-force%20hughes%20ATS%20turan%20zsr%20maxxtech%20rocketfire%20ytr%20remington%20winchester%202a&sh=low&ca=brass&co=new",
    },
    "9mm_147gr": {
        "label": "9mm Luger 147gr+",
        "url": "https://ammoseek.com/ammo/9mm-luger/-handgun-147-999grains?sh=low&ca=brass&ekw=bps%20x-force%20blazer%20merica%20hughes%20ATS%20turan%20zsr%20maxxtech%20rocketfire%20ytr%20remington%20winchester%202a&co=new",
    },
    "9mm_frangible_premium": {
        "label": "9mm Luger Frangible (Premium)",
        "url": "https://ammoseek.com/ammo/9mm-luger?ca=brass&sh=low&co=new&ekw=bps%20x-force%20hughes%20ATS%20veteran%20maxxtech%20ytr%20%241000%20turan%20zsr&ikw=Frangible",
    },
    "9mm_frangible": {
        "label": "9mm Luger Frangible",
        "url": "https://ammoseek.com/ammo/9mm-luger?ikw=frangible&ca=brass&sh=low&co=new",
    },
}

DATA_FILE = "ammo_prices.json"
TOP_N = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://ammoseek.com/",
    "DNT": "1",
}

SESSION_COOKIE = None


def parse_price(text):
    m = re.search(r"[\d]+\.[\d]+", text.replace(",", ""))
    return float(m.group()) if m else None


def parse_rounds(text):
    m = re.search(r"(\d[\d,]*)\s*(?:rounds?|rds?|ct)", text, re.I)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"(\d[\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else None


def scrape_search(url, label):
    session = requests.Session()
    if SESSION_COOKIE:
        session.cookies.set("session", SESSION_COOKIE, domain="ammoseek.com")
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: Request failed for {label}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    rows = soup.select("tr[data-retailer], tr[data-name]")
    if rows:
        for row in rows:
            try:
                retailer = row.get("data-retailer") or "Unknown"
                description = row.get("data-name") or ""
                price_raw = row.get("data-price") or ""
                rounds_raw = row.get("data-rounds") or row.get("data-qty") or ""
                cpr_raw = row.get("data-cpr") or row.get("data-unitprice") or ""
                shipping_raw = row.get("data-shipping") or row.get("data-free-shipping") or ""
                price = parse_price(price_raw)
                rounds = int(rounds_raw) if str(rounds_raw).isdigit() else parse_rounds(str(rounds_raw))
                cpr = float(cpr_raw) * 100 if cpr_raw and float(cpr_raw) < 10 else (float(cpr_raw) if cpr_raw else None)
                if price and rounds and not cpr:
                    cpr = round((price / rounds) * 100, 2)
                if not (price and rounds and cpr):
                    continue
                shipping = "F" if str(shipping_raw).upper() in ("FREE", "F", "1", "TRUE") else (str(shipping_raw) or "-")
                results.append({"retailer": str(retailer).strip(), "description": str(description).strip(),
                    "price": f"${price:.2f}", "rounds": int(rounds), "cpr": round(cpr, 2),
                    "cpr_text": f"{cpr:.1f}c/rd", "shipping": shipping})
            except (ValueError, TypeError):
                continue

    if not results:
        table = (soup.find("table", id=re.compile(r"ammo", re.I))
            or soup.find("table", class_=re.compile(r"ammo|result|listing", re.I))
            or soup.find("table"))
        if table:
            tbody = table.find("tbody") or table
            for row in tbody.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                try:
                    cell_texts = [c.get_text(" ", strip=True) for c in cells]
                    price = None
                    price_idx = None
                    for i, t in enumerate(cell_texts):
                        p = parse_price(t)
                        if p and 1 < p < 5000:
                            price = p; price_idx = i; break
                    if not price: continue
                    rounds = None
                    for t in cell_texts:
                        r = parse_rounds(t)
                        if r and 1 <= r <= 10000:
                            rounds = r; break
                    if not rounds: continue
                    cpr = round((price / rounds) * 100, 2)
                    retailer_el = row.select_one("a[href*='retailer'], .retailer, td:first-child a")
                    retailer = retailer_el.get_text(strip=True) if retailer_el else cell_texts[0][:50]
                    description = max((t for i, t in enumerate(cell_texts) if i != price_idx and len(t) > 10), key=len, default="")
                    shipping = "F" if "free" in row.get_text(" ", strip=True).lower() else "-"
                    results.append({"retailer": retailer.strip(), "description": description.strip(),
                        "price": f"${price:.2f}", "rounds": int(rounds), "cpr": cpr,
                        "cpr_text": f"{cpr:.1f}c/rd", "shipping": shipping})
                except (ValueError, TypeError):
                    continue

    results.sort(key=lambda r: r["cpr"])
    return results[:TOP_N]


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"searches": {}, "last_updated": None}


def save_data(data):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved to {DATA_FILE}")


def main():
    print("AmmoSeek Price Tracker")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Tracking {len(SEARCHES)} searches\n")
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    for sid, search in SEARCHES.items():
        label = search["label"]
        url = search["url"]
        print(f"Scraping: {label}")
        results = scrape_search(url, label)
        if results:
            best = results[0]
            print(f"  Best: {best['cpr_text']} - {best['retailer']} ({best['price']} / {best['rounds']}rd)")
        else:
            print(f"  No results (site may be blocking - try adding SESSION_COOKIE)")
        if sid not in data["searches"]:
            data["searches"][sid] = {"label": label, "url": url, "history": []}
        else:
            data["searches"][sid]["label"] = label
            data["searches"][sid]["url"] = url
        history = data["searches"][sid]["history"]
        if history and history[-1]["date"] == today:
            history[-1]["results"] = results
        else:
            history.append({"date": today, "results": results})
        time.sleep(2)
    save_data(data)


if __name__ == "__main__":
    main()
