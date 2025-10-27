#!/usr/bin/env python3
"""
get_spotify_refresh_token.py

Run this script, it will:
 - Start a small local HTTP server on localhost:8888
 - Open the Spotify authorize URL in your browser
 - Capture the code from the redirect
 - Exchange the code for access + refresh tokens
 - Save the refresh_token to refresh_token.txt

Usage:
  1) Set CLIENT_ID and CLIENT_SECRET below (or export SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET env vars)
  2) Ensure Redirect URI in Spotify Dashboard includes http://localhost:8888/callback
  3) Run: python3 get_spotify_refresh_token.py
"""

import http.server
import socketserver
import urllib.parse as up
import threading
import webbrowser
import requests
import base64
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Redirect URI must match what you've added to Spotify Dashboard
REDIRECT_URI = "http://localhost:8888/callback"

# Scopes needed for playback control (adjust if you need extra)
SCOPES = [
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
]

# Server settings
LISTEN_PORT = 8888
TOKEN_SAVE_PATH = "refresh_token.txt"
# ----------------------------

if CLIENT_ID.startswith("your_") or CLIENT_SECRET.startswith("your_"):
    print(
        "Please set CLIENT_ID and CLIENT_SECRET in the script or export SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET environment variables."
    )
    sys.exit(1)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Thread-safe container to receive the code from the handler
server_data = {"code": None, "error": None}


class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = up.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        qs = up.parse_qs(parsed.query)
        if "error" in qs:
            server_data["error"] = qs.get("error", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization failed or denied.</h2>You can close this window.</body></html>"
            )
            # shutdown will be handled by main thread
            return

        code = qs.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<html><body><h2>No code received.</h2></body></html>")
            return

        server_data["code"] = code
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authorization successful.</h2>You can close this window and return to the terminal.</body></html>"
        )

    # avoid noisy logging
    def log_message(self, format, *args):
        pass


def start_http_server():
    with socketserver.TCPServer(("localhost", LISTEN_PORT), CallbackHandler) as httpd:
        # handle_request will serve a single request then return, but we loop until code is received or timeout
        httpd.timeout = 1  # seconds
        while server_data["code"] is None and server_data["error"] is None:
            httpd.handle_request()


def build_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "show_dialog": "true",
    }
    return AUTH_URL + "?" + up.urlencode(params)


def exchange_code_for_tokens(code):
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=data, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print(
        "Starting local HTTP server on http://localhost:%d to receive the callback..."
        % LISTEN_PORT
    )
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()

    auth_url = build_auth_url()
    print(
        "\nOpen this URL in your browser (it should open automatically):\n\n"
        + auth_url
        + "\n"
    )
    try:
        webbrowser.open(auth_url, new=2)
    except Exception:
        pass

    # Wait for code (timeout after 120 seconds)
    timeout = 300
    poll = 0.5
    waited = 0.0
    while (
        server_data["code"] is None
        and server_data["error"] is None
        and waited < timeout
    ):
        time.sleep(poll)
        waited += poll

    if server_data["error"]:
        print("Authorization error:", server_data["error"])
        sys.exit(1)

    if not server_data["code"]:
        print(
            "Timed out waiting for authorization code. Make sure you completed the login in the browser."
        )
        sys.exit(1)

    code = server_data["code"]
    print("Got authorization code. Exchanging for tokens...")

    try:
        tokens = exchange_code_for_tokens(code)
    except requests.HTTPError as e:
        print("Failed to exchange code for token:", e)
        print("Response:", getattr(e.response, "text", ""))
        sys.exit(1)

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    expires_in = tokens.get("expires_in")

    if not refresh_token:
        print("No refresh_token received. Response:")
        print(tokens)
        sys.exit(1)

    # Save refresh token (careful with permissions!)
    with open(TOKEN_SAVE_PATH, "w") as f:
        f.write(refresh_token)
    print(f"Saved refresh token to {TOKEN_SAVE_PATH}")
    print("Access token (short-lived):", access_token)
    print("expires_in (s):", expires_in)
    print(
        "\nIMPORTANT: Keep your refresh token and client secret safe. Do NOT share them.\n"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(0)
