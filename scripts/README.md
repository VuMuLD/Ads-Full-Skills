# ads-optimizer scripts

Python 3.10+ scripts that connect to the Google Ads API and the Meta (Facebook/Instagram)
Marketing API, pull live performance data, and produce Decision-Engine recommendations.

## Setup

```powershell
# Python 3.10+ (Windows: winget install Python.Python.3.12), then:
py -m pip install -r requirements.txt

# credentials: create ../.env (skill root) from ../.env.example
# verify:
py check_connection.py --platform both
```

Full credential walkthrough: `../references/setup-connection.md`.

## Scripts

| Script | Purpose |
|---|---|
| `check_connection.py` | Verify Google and/or Meta credentials, show account currency/timezone |
| `optimize.py` | **Flagship.** Pulls both platforms, classifies every campaign/ad (scale / keep / decrease / pause / sleep), detects hour/placement/device/geo/age cuts, fatigue, search-term waste, proposes A/B tests. Saves a Markdown + JSON report to `./reports/`. |
| `pull_google.py` | Ad-hoc Google data: overview, campaigns, keywords, search terms, ads, hour/day/device breakdowns |
| `pull_meta.py` | Ad-hoc Meta data: overview, campaigns, ad sets, ads, breakdowns (hourly, placement, device, age, gender, region) |
| `update_google.py` | Change campaign status/budget/name — **dry-run by default**, `--yes` applies |
| `update_meta.py` | Change campaign/ad set/ad status/budget/name — currency-aware, **dry-run by default**, `--yes` applies |
| `common.py`, `google_client.py`, `meta_client.py` | Shared config/env loading, formatting, API clients |

## Notes

- All analysis windows end **yesterday** — today's partial data is excluded on purpose.
- Budget figures for Meta are converted with the account currency's minor units
  (VND/JPY/KRW → whole units; USD/EUR → cents) automatically.
- Google costs come as `cost_micros` (1e-6 of the account currency) and are converted for display.
- Recommendations are **drafts**. Apply only with explicit user confirmation, one change at a
  time; never delete objects — pause/archive only.
