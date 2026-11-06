# Setup & Connection Guide

One-time setup to put ads-optimizer in CONNECTED mode. Nothing is required for ADVISORY mode.

## 0. Install Python + dependencies (Windows)

```powershell
# Python 3.10+ (skip if `py --version` works)
winget install Python.Python.3.12
# then reopen the terminal

cd C:\Users\phong\.agents\skills\ads-optimizer\scripts
py -m pip install -r requirements.txt
```

## 1. Credentials file

Create `.env` in **this skill's root** (`C:\Users\phong\.agents\skills\ads-optimizer\.env`)
or in `scripts/`. Templates: see `.env.example` at the skill root. Load order: skill root →
`scripts/.env` → current working directory.

Connect only the platforms you need; the other one stays in ADVISORY mode.

---

## 2. Google Ads API

Required credentials (all from the account you want to read — an MCC/manager account is
recommended so one token can serve multiple clients):

| Env var | Where to get it |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads UI → Tools & Settings → Setup → API Center (account needs to be the token holder; "Basic access" is enough) |
| `GOOGLE_ADS_CLIENT_ID` + `GOOGLE_ADS_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID (Desktop app). Enable the **Google Ads API** in APIs & Services → Library |
| `GOOGLE_ADS_REFRESH_TOKEN` | Generated once via the OAuth flow below |
| `GOOGLE_ADS_CUSTOMER_ID` | The 10-digit account ID, e.g. `123-456-7890` |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Only if authenticating through an MCC: the MCC's ID (no dashes) |

### Generating the refresh token (one-time, automated)

New OAuth clients are blocked from the old out-of-band (OOB) flow — use the bundled loopback
helper (needs `pip install requests python-dotenv` only):

1. Ensure the OAuth client type is **Desktop app** and the Google Ads API is enabled.
2. Run:
   ```powershell
   py google_oauth_helper.py
   ```
3. Paste CLIENT_ID / CLIENT_SECRET when asked; the browser opens, you approve, the helper
   catches `http://localhost:8080`, exchanges the code, and prints the refresh token.
4. Paste `GOOGLE_ADS_REFRESH_TOKEN=...` into `.env`.
5. Developer token note: a **new developer token has a 24-hour approval wait** after first
   request. Test accounts via MCC are usable immediately.
6. If you see `invalid_grant`: revoke the app at myaccount.google.com/permissions and rerun.

Verify: `py check_connection.py --platform google`

---

## 3. Meta (Facebook/Instagram) Marketing API

Recommended: a **System User token** (long-lived, doesn't expire like user tokens).

| Env var | Where to get it |
|---|---|
| `META_ACCESS_TOKEN` | business.facebook.com → Business Settings → Users → System users → Add → role Admin → Generate new token → select your ad account's asset → scopes: `ads_management`, `ads_read`, `business_management`, `pages_read_engagement` (pages scope only if you manage Page-level assets) |
| `META_AD_ACCOUNT_ID` | The numeric ID from Ads Manager URL (`act_` prefix optional — auto-added) |
| `META_APP_ID` (optional) | business.facebook.com → App settings; needed only for token refresh flows |

Steps:
1. Create a Business Manager if you don't have one (business.facebook.com).
2. Add yourself/your app as a System User, grant it the **ad account** asset with full
   ad-management permissions, generate the token with the scopes above.
3. Copy the token immediately (shown once). Store in `.env`.
4. Token lifetime: a Graph API Explorer token dies in ~1 hour — fine for a first test, but
   for real use either create a **System User token** (long-lived) or exchange the short
   token for a ~60-day one:
   `GET https://graph.facebook.com/v22.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
5. Error 1359208 during audience upload = re-accept the Custom Audience TOS in Ads Manager
   (the API cannot detect or fix this).

Verify: `py check_connection.py --platform meta`

---

## 4. Troubleshooting

| Symptom | Fix |
|---|---|
| `Python was not found` | Install Python 3.10+ (see §0), reopen terminal, use `py` |
| `ModuleNotFoundError: google.ads` | `py -m pip install -r requirements.txt` |
| Google `ACCESS_TOKEN_SCOPE_INSUFFICIENT` | Regenerate refresh token with the `adwords` scope (§2) |
| Google `USER_PERMISSION_DENIED` | Set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to the MCC ID; ensure the token holder has access to the account |
| Google `DEVELOPER_TOKEN_PROVISIONING` / not approved | Wait 24h for basic access, or use an MCC test account first |
| Meta `Error code 190` (token expired/invalid) | Regenerate the System User token; confirm scopes |
| Meta `( #3 ) Application does not have permission` | Add the ad account asset to the System User, re-generate token |
| Meta `Unsupported get request` on account | Wrong `META_AD_ACCOUNT_ID` — copy from Ads Manager URL |
| Nothing to spend shown | Check window: data ends **yesterday** (today's partial data is excluded) |

Security: `.env` holds spend-controlling credentials. Never commit it, never paste tokens in
chat. If a token leaks, revoke it in Business Settings / Google Cloud Console immediately.
