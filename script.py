#!/usr/bin/env python3
"""
rfid_spotify.py
- Reads RFID tags (MFRC522)
- Master tag puts system in write mode to program album URIs onto tags
- Regular tags store and play album URIs from their text field
"""

import time
import base64
import requests
from mfrc522 import SimpleMFRC522
import sys
import os
from dotenv import load_dotenv
import RPi.GPIO as GPIO
import json

sys.stdout.reconfigure(line_buffering=True)

# Load environment variables from .env file
load_dotenv()

# ---------- CONFIG ----------
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
TARGET_DEVICE_NAME = os.getenv("SPOTIFY_TARGET_DEVICE")

# Validate required config
if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, TARGET_DEVICE_NAME]):
    print("ERROR: Missing required environment variables in .env file")
    print(
        "Required: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN, SPOTIFY_TARGET_DEVICE"
    )
    sys.exit(1)

# Current device ID (will be populated at startup)
DEVICE_ID = None

# Master tag identifier (written to tag with write_master_tag.py)
MASTER_TAG_ID = "MASTER_TAG"

# Token endpoint details
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Tag map file path
TAG_MAP_FILE = "tag_map.json"
TAG_MAP = {}

# ----------------------------

reader = SimpleMFRC522()

LED_PIN = 18
GPIO.setup(LED_PIN, GPIO.OUT)


def load_tag_map():
    """Load tag ID to Spotify URI mapping from file."""
    global TAG_MAP
    try:
        with open(TAG_MAP_FILE, "r") as f:
            TAG_MAP = json.load(f)
        print(f"Loaded tag map with {len(TAG_MAP)} entries")
    except FileNotFoundError:
        print(f"Tag map file not found ({TAG_MAP_FILE}), starting with empty map")
        TAG_MAP = {}
    except json.JSONDecodeError:
        print(f"Error decoding tag map file, starting with empty map")
        TAG_MAP = {}


def save_tag_map():
    """Save tag ID to Spotify URI mapping to file."""
    try:
        with open(TAG_MAP_FILE, "w") as f:
            json.dump(TAG_MAP, f, indent=2)
    except Exception as e:
        print(f"Error saving tag map: {e}")


def flash_led(times=1, delay=0.2):
    """Flash LED a certain number of times (normal tag feedback)."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(delay)


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


def start_playback(access_token, spotify_uri, device_id):
    """Start playback for spotify_uri on the given device."""
    url = f"https://api.spotify.com/v1/me/player/play"
    params = {}
    if device_id:
        params["device_id"] = device_id
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


def find_device_id_by_name(access_token, target_name):
    """Find device ID by name (case-insensitive). Returns ID or None if not found."""
    devices_resp = get_current_devices(access_token)
    devices = devices_resp.get("devices", [])

    if devices:
        print("Available Spotify Devices:")
        for d in devices:
            print(f"  - {d['name']} (ID: {d['id']})")
    else:
        print("No available devices found.")

    target_lower = target_name.lower()
    for device in devices:
        if device["name"].lower() == target_lower:
            return device["id"]

    return None


def get_currently_playing(access_token):
    """Get the currently playing track and return its album URI. Returns None if nothing playing or album unavailable."""
    url = "https://api.spotify.com/v1/me/player/currently-playing"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 204:
            print("Nothing currently playing")
            return None
        r.raise_for_status()
        data = r.json()
        if data and data.get("item") and data["item"].get("album"):
            album_uri = data["item"]["album"]["uri"]
            album_name = data["item"]["album"]["name"]
            print(f"Currently playing album: {album_name}")
            return album_uri
        else:
            print("No album found in currently playing track")
            return None
    except Exception as e:
        print(f"Error getting currently playing: {e}")
        return None


def main_loop():
    global DEVICE_ID

    print("Starting RFID -> Spotify bridge")
    load_tag_map()
    access_token, _ = refresh_access_token()
    print("Got access token (will refresh automatically if error occurs).")

    # Look up device ID by name
    DEVICE_ID = find_device_id_by_name(access_token, TARGET_DEVICE_NAME)
    if DEVICE_ID:
        print(f"Using device ID: {DEVICE_ID}")
    else:
        print(f"ERROR: Could not find target device '{TARGET_DEVICE_NAME}'.")
        return

    write_mode = False
    pending_album_uri = None

    try:
        while True:
            if write_mode:
                print("WRITE MODE: Present tag to map...")
                print(f"Album URI to map: {pending_album_uri}")
                GPIO.output(LED_PIN, GPIO.HIGH)

                write_success = False
                while not write_success:
                    try:
                        tag_id, text = reader.read()
                        uid_str = str(tag_id)

                        # Map tag ID to album URI
                        TAG_MAP[uid_str] = pending_album_uri
                        save_tag_map()

                        write_success = True
                        print(f"✓ Tag {uid_str} mapped to album successfully")
                    except Exception as e:
                        print(f"Error: {e}. Try again...")

                GPIO.output(LED_PIN, GPIO.LOW)
                write_mode = False
                pending_album_uri = None
                time.sleep(1.0)
            else:
                print("Waiting for tag... (press Ctrl+C to quit)")
                id, text = reader.read()  # this blocks until a tag is read
                uid_str = str(id)
                print(f"Tag read: {uid_str}, text: {text}")

                # Normalize text for comparison (strip whitespace)
                text = text.strip() if isinstance(text, str) else text

                if text == MASTER_TAG_ID:
                    # Master tag detected - enter write mode
                    flash_led(2, 0.1)
                    print("Master tag detected. Entering write mode...")

                    album_uri = get_currently_playing(access_token)
                    if album_uri:
                        write_mode = True
                        pending_album_uri = album_uri
                        GPIO.output(LED_PIN, GPIO.HIGH)
                        print("Ready to write to next tag presented")
                    else:
                        print(
                            "Cannot enter write mode - nothing playing or no album available"
                        )
                    time.sleep(1.0)
                elif uid_str in TAG_MAP:
                    # Tag ID found in map - trigger playback
                    flash_led(2, 0.1)
                    spotify_uri = TAG_MAP[uid_str]
                    print(f"Album URI: {spotify_uri}. Triggering playback...")

                    # attempt playback, refresh token on unauthorized
                    try:
                        ok, info = start_playback(access_token, spotify_uri, DEVICE_ID)
                    except requests.HTTPError as e:
                        print("HTTP error while sending play command:", e)
                        ok = False
                        info = e

                    if not ok:
                        status_code, _ = info
                        # Handle 404 device not found
                        if status_code == 404:
                            print(
                                "Device not found (404). Refreshing device list and retrying..."
                            )
                            try:
                                DEVICE_ID = find_device_id_by_name(
                                    access_token, TARGET_DEVICE_NAME
                                )
                                if DEVICE_ID:
                                    print(
                                        f"Found device, retrying with ID: {DEVICE_ID}"
                                    )
                                    ok, info = start_playback(
                                        access_token, spotify_uri, DEVICE_ID
                                    )
                                else:
                                    print("Could not find target device after refresh.")
                            except Exception as e:
                                print("Error refreshing device list:", e)

                        # If still not ok, try refreshing token
                        if not ok:
                            print("Attempting to refresh access token and retry...")
                            try:
                                access_token, _ = refresh_access_token()
                                ok, info = start_playback(
                                    access_token, spotify_uri, DEVICE_ID
                                )
                            except Exception as e:
                                print("Error refreshing token:", e)

                    if ok:
                        print("Playback triggered.")
                    else:
                        print("Failed to start playback:", info)
                    time.sleep(1.0)
                else:
                    print(f"Unknown tag (not in map): {uid_str}")
                    time.sleep(1.0)

    except KeyboardInterrupt:
        print("Exiting")
    finally:
        try:
            reader.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    main_loop()
