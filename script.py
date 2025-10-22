#!/usr/bin/env python3
"""
rfid_spotify.py
- Reads RFID tags (MFRC522)
- Maps tag UID -> Spotify URI and triggers playback on a Spotify Connect device.

Requires:
pip3 install mfrc522 requests
"""

import time
import base64
import requests
from mfrc522 import SimpleMFRC522
import sys

sys.stdout.reconfigure(line_buffering=True)


# ---------- CONFIG ----------
CLIENT_ID = "your_spotify_client_id"
CLIENT_SECRET = "your_spotify_client_secret"
REFRESH_TOKEN = "your_saved_refresh_token"

# device_id of the Spotify Connect device you want to play to
# get it from https://api.spotify.com/v1/me/player/devices
DEVICE_ID = "your_target_device_id"

# Map RFID UID (string) -> Spotify URI (track/album/playlist/artist)
# Example UID format used below is '12345678' (it's joined decimal from bytes)
TAG_MAP = {
    "732283830995": "spotify:album:6jbtHi5R0jMXoliU2OS0lo",
    "847216211447": "spotify:album:316O0Xetgx2NJLRgJBw4uq",
    "926375589018": "spotify:album:4CZCMvnmbjR6FkOAhzgmg3",
    "539431371257": "spotify:album:6hPt04r4KtO00nwhdGJ8Ox",
}

# Token endpoint details
TOKEN_URL = "https://accounts.spotify.com/api/token"

# ----------------------------

reader = SimpleMFRC522()


def uid_to_str(uid_tuple):
    """Convert uid tuple/list to a single integer string (common style)."""
    return "".join(str(x) for x in uid_tuple)


def refresh_access_token():
    """Exchange refresh token for new access token."""
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN}
    r = requests.post(TOKEN_URL, data=data, headers=headers, timeout=10)
    r.raise_for_status()
    token_info = r.json()
    return token_info["access_token"], token_info.get("expires_in", 3600)


def start_playback(access_token, spotify_uri):
    """Start playback for spotify_uri on DEVICE_ID."""
    url = f"https://api.spotify.com/v1/me/player/play"
    params = {}
    if DEVICE_ID:
        params["device_id"] = DEVICE_ID
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    # The body can be {"uris": [<track-uri>]} for single tracks, or {"context_uri": "<playlist/album-uri>"} for albums/playlists
    body = {}
    if spotify_uri.startswith("spotify:track:"):
        body = {"uris": [spotify_uri]}
    else:
        body = {"context_uri": spotify_uri}
    r = requests.put(url, params=params, headers=headers, json=body, timeout=5)
    # 204 = success (no content). 202 or 403 or 404 may happen.
    if r.status_code in (204, 202):
        return True, r.status_code
    else:
        return False, (r.status_code, r.text)


def get_current_devices(access_token):
    url = "https://api.spotify.com/v1/me/player/devices"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()


def main_loop():
    print("Starting RFID -> Spotify bridge")
    access_token, _ = refresh_access_token()
    print("Got access token (will refresh automatically if error occurs).")

    try:
        devices_resp = get_current_devices(access_token)
        devices = devices_resp.get("devices", [])
        if devices:
            print("Available Spotify Devices:")
            for d in devices:
                print(f"  - ID: {d['id']}")
                print(f"    Name: {d['name']}")
                print(f"    Type: {d['type']}")
                print(f"    Active: {d['is_active']}")
                print(f"    Restricted: {d['is_restricted']}")
                print(f"    Volume: {d.get('volume_percent', 'N/A')}")
                print()
        else:
            print("No available devices found.")
    except Exception as e:
        print("Error fetching devices:", e)

    try:
        while True:
            print("Waiting for tag... (press Ctrl+C to quit)")
            id, text = reader.read()  # this blocks until a tag is read
            # id is integer, but sometimes MFRC522 returns tuple — adapt
            uid_str = str(id)
            print(f"Tag read: {uid_str}")

            if uid_str in TAG_MAP:
                spotify_uri = TAG_MAP[uid_str]
                print(f"Mapped to {spotify_uri}. Triggering playback...")

                # attempt playback, refresh token on unauthorized
                try:
                    ok, info = start_playback(access_token, spotify_uri)
                except requests.HTTPError as e:
                    print("HTTP error while sending play command:", e)
                    ok = False
                    info = e

                if not ok:
                    # Try refreshing token once then retry
                    print("Attempting to refresh access token and retry...")
                    access_token, _ = refresh_access_token()
                    ok, info = start_playback(access_token, spotify_uri)

                if ok:
                    print("Playback triggered.")
                else:
                    print("Failed to start playback:", info)
            else:
                print("Unknown tag. UID:", uid_str)
            # small delay to avoid reading same tag repeatedly
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("Exiting")
    finally:
        try:
            reader.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    # Optionally load TAG_MAP from a file, environment, etc.
    main_loop()
