#\!/usr/bin/env python3
"""
AmmoSeek Price Tracker
Scrapes best prices from 12 saved searches and APPENDS to ammo_prices.json.
History is preserved â each run adds today's entry without erasing past data.
"""

import json
import os
import time
from datetime import datetime, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    raise

# Optional: paste a session cookie here to help with bot detection
SESSION_COOKIE = None

SEARCHES = {
    "30_carbine": {"label": "30 Carbine", "url": "https://ammoseek.com/ammo/30-carbine?sh=average"},
    "30_06": {"label": "30-06", "url": "https://ammoseek.com/ammo/30-06?sh=low"},
    "300_aac_subsonic": {"label": ".300 AAC Blackout (Subsonic)", "url": "https://ammoseek.com/ammo/300aac-blackout?sh=average&ikw=subsonic&co=new"},
    "303_british": {"label": "303 British", "url": "https://ammoseek.com/ammo/303-british?sh=average"},
    "380_auto": {"label": ".380 Auto", "url": "https://ammoseek.com/ammo/380-auto?sh=average&ekw=Armsocor%20fiocchi%20sinterfire&co=new"},
    "556_nato": {"label": "5.56x45mm NATO", "url": "https://ammoseek.com/ammo/5.56x45mm-nato?sh=low&ekw=Igmab%20turan&co=new"},
    "75x55_swiss": {"label": "7.5x55mm Swiss", "url": "https://ammoseek.com/ammo/7.5x55mm-swiss"},
    "9mm_sb": {"label": "9mm Luger - Sellier and Bellot", "url": "https://ammoseek.com/ammo/9mm-luger/Sellier%20and%20Bellot?sh=lowest&ca=brass&co=new"},
    "9mm_excl_junk": {"label": "9mm Luger (Excl. junk brands)", "url": "https://ammoseek.com/ammo/9mm-luger?ekw=bps%20x-force%20hughes%20ATS%20turan%20zsr%20maxxtech%20rocketfire%20ytr%20remington%20winchester%202a&sh=low&ca=brass&co=new"},
    "9mm_147gr": {"label": "9mm Luger 147gr+", "url": "https://ammoseek.com/ammo/9mm-luger/-handgun-147-999grains?sh=low&ca=brass&ekw=bps%20x-force%20blazer%20merica%20hughes%20ATS%20turan%20zsr%20maxxtech%20rocketfire%20ytr%20remington%20winchester%202a&co=new"},
ttps://ammoseek.com/ammo/9mm-luger?ca=brass&sh=low&co=new&ekw=bps%20x-force%20hughes%20ATS%20veteran%20maxxtech%20ytr%20%241000%20turan%20zsr&ikw=Frangible"},
    "9mm_frangible": {"label": "9mm Luger Frangible", "url": "https://ammoseek.com/ammo/9mm-luger?ikw=frangible&ca=brass&sh=low&co=new"},
}

OUTPUT_FILE = "ammo_prices.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://ammoseek.com/",
}


def load_existing():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"searches": {}, "last_updated": None}


def parse_results(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select("table tbody tr[role='row']"):
        cells = row.find_all("td")
        if len(cells) < 12:
            continue
        try:
            retailer = cells[0].get_text(separator="\n").split("\n")[0].strip()
            description = " ".join(cells[1].get_text().split())[:80]
            price = float(cells[9].get_text(strip=True).replace("$", "").replace(",", ""))
            rounds = int(cells[10].get_text(strip=True).replace(",", ""))
            cpr_raw = cells[11].get_text(strip=True)
            shipping = cells[12].get_text(strip=True) if len(cells) > 12 else "-"
            cpr = float(cpr_raw.replace("$", "")) * 100 if cpr_raw.startswith("$") else float(cpr_raw.replace("c", "").replace("\u00a2", ""))
            if not price or not rounds or not cpr:
                continue
            results.append({"retailer": retailer, "description": description, "price": f"${price:.2f}", "rounds": rounds, "cpr": round(cpr, 1), "cpr_text": f"{cpr:.1f}\u00a2", "shipping": "F" if shipping == "F" else (shipping or "-")})
        except (ValueError, IndexError):
            continue
    results.sort(key=lambda r: r["cpr"])
    return results[:2]


def scrape_search(sid, meta, session):
    try:
        resp = session.get(meta["url"], headers=HEADERS, timeout=15)
        if resp.status_code \!= 200:
            print(f"  [{sid}] HTTP {resp.status_code} â skipping")
            return []
        results = parse_results(resp.text)
        if results:
            print(f"  [{sid}] best: {results[0]['cpr_text']} @ {results[0]['retailer']}")
        else:
            print(f"  [{sid}] No results (likely bot-blocked from cloud IP)")
        return results
    except Exception as e:
        print(f"  [{sid}] Error: {e}")
        return []


def main():
    data = load_existing()
    session = requests.Session()
    if SESSION_COOKIE:
        session.headers.update({"Cookie": SESSION_COOKIE})

    print(f"Scraping {len(SEARCHES)} searches for {TODAY}...\n")

    for sid, meta in SEARCHES.items():
        if sid not in data["searches"]:
            data["searches"][sid] = {"label": meta["label"], "url": meta["url"], "history": []}
        else:
            data["searches"][sid]["label"] = meta["label"]
            data["searches"][sid]["url"] = meta["url"]

        results = scrape_search(sid, meta, session)

        history = data["searches"][sid].setdefault("history", [])
        # Replace today's entry if it exists, otherwise append
        history[:] = [h for h in history if h["date"] \!= TODAY]
        history.append({"date": TODAY, "results": results})
        # Keep last 365 days only
        history.sort(key=lambda h: h["date"])
        data["searches"][sid]["history"] = history[-365:]

        time.sleep(2)

    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    total = sum(1 for s in data["searches"].values() if any(h["date"] == TODAY and h["results"] for h in s.get("history", [])))
    print(f"\nDone. {total}/{len(SEARCHES)} searches scraped for {TODAY}.")
    print(f"Saved -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
