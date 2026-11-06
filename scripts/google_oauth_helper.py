#!/usr/bin/env python3
"""
One-time helper to get a Google Ads API refresh token using the loopback redirect
(the OOB `urn:ietf:wg:oauth:2.0:oob` flow is deprecated and blocked for new OAuth clients).

Prerequisites: an OAuth Client ID of type "Desktop app" in Google Cloud Console with
the Google Ads API enabled.

Usage:
    python google_oauth_helper.py
    (then paste CLIENT_ID and CLIENT_SECRET when asked - they are NOT stored)

It opens your browser, you approve, it catches the redirect on http://localhost:8080,
exchanges the code, and prints the refresh token to paste into .env as
GOOGLE_ADS_REFRESH_TOKEN.
"""

import http.server
import sys
import threading
import urllib.parse
import webbrowser

REDIRECT_PORT = 8080
SCOPES = "https://www.googleapis.com/auth/adwords"


class _Handler(http.server.BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _Handler.auth_code = (params.get("code") or [None])[0]
        error = (params.get("error") or [None])[0]
        self.send_response(200)
        self.end_headers()
        message = ("Token received - you can close this tab."
                   if _Handler.auth_code or error == "access_denied" else
                   f"Problem: {error or 'no code in redirect'}. Close this tab and retry.")
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, *args):
        pass


def main():
    client_id = input("CLIENT_ID: ").strip()
    client_secret = input("CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        sys.exit("ERROR: both values are required.")

    redirect_uri = f"http://localhost:{REDIRECT_PORT}"
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={urllib.parse.quote(client_id)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        "&response_type=code"
        f"&scope={SCOPES}"
        "&access_type=offline"
        "&prompt=consent"
    )
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print(f"\nOpening browser for approval... (if nothing opens, paste this URL manually)\n\n{auth_url}\n")
    webbrowser.open(auth_url)
    print(f"Waiting for the redirect on {redirect_uri} ...")

    server.timeout = 300
    server.handle_request()
    code = _Handler.auth_code
    if not code:
        sys.exit("ERROR: no authorization code received within the timeout. Run again.")

    import requests
    token_resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    payload = token_resp.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        sys.exit(f"ERROR: no refresh token returned: {payload}\n"
                 "If 'invalid_grant': revoke the app at https://myaccount.google.com/permissions "
                 "and run this helper again.")
    print("\nSUCCESS. Paste this line into your .env:\n")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("\nKeep it secret. The token stays valid until you revoke access at "
          "https://myaccount.google.com/permissions")


if __name__ == "__main__":
    main()
