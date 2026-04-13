# 🎯 AmmoSeek Price Tracker

A self-hosted ammo price dashboard that scrapes your 12 saved AmmoSeek searches daily and displays price trends over time.

---

## How it works

| File | Purpose |
|---|---|
| `ammo_tracker.py` | Python scraper - fetches the top 2 cheapest results for each search and saves them to `ammo_prices.json` |
| `dashboard.html` | Dark-themed web dashboard - reads `ammo_prices.json` and shows price charts, deltas, and retailer tables |
| `.github/workflows/daily-scrape.yml` | GitHub Actions cron job - runs the scraper every morning at 8 AM ET automatically |

---

## Daily automation

Every day at 8 AM Eastern, GitHub Actions runs the scraper on GitHub's servers (free), commits the updated `ammo_prices.json` to this repo, and your dashboard at GitHub Pages automatically reflects the new data. You don't need your computer on.

## Your dashboard URL

https://beleita.github.io/ammo-tracker/dashboard.html

## Customise

**Add/remove searches:** Open `ammo_tracker.py` and comment out any searches in the `SEARCHES` dictionary you don't want.

**Change the run time:** Edit `.github/workflows/daily-scrape.yml` and update the cron line.

**Add a session cookie (optional):** If AmmoSeek blocks the scraper, paste your session cookie into `ammo_tracker.py` where it says `SESSION_COOKIE = None`.

## Troubleshooting

**Dashboard shows 'No data found'** - Go to Actions tab and run the workflow manually.

**GitHub Actions run fails** - Most likely AmmoSeek is temporarily blocking. Wait a day and retry, or add your session cookie.

