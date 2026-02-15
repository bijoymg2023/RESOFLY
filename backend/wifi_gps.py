
import requests
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import wifi_scanner

class WifiGPS:
    """
    Translates Wi-Fi scan results into GPS coordinates using the Google Geolocation API.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_GEOLOCATION_API_KEY")
        self.last_coords = {"latitude": 0.0, "longitude": 0.0, "accuracy": 0.0, "timestamp": None}
        self.cache_timeout = 60  # Only refresh every 60 seconds to save API quota
        self.last_request_time = 0

    def get_location(self) -> Dict:
        """
        Scans Wi-Fi and calls Google API. Returns cached data if too frequent.
        """
        if not self.api_key:
            return self._error_response("NO_API_KEY")

        now = datetime.now().timestamp()
        if now - self.last_request_time < self.cache_timeout and self.last_coords["timestamp"]:
            return self.last_coords

        try:
            # 1. Get raw Wi-Fi scan
            networks = wifi_scanner.get_wifi_devices()
            if not networks or len(networks) < 2:
                # Need at least 2 networks for decent triangulation
                return self._error_response("INSUFFICIENT_NETWORKS")

            # 2. Format for Google API
            # Google expects: { "wifiAccessPoints": [ { "macAddress": "...", "signalStrength": -65 }, ... ] }
            wifi_aps = []
            for n in networks:
                wifi_aps.append({
                    "macAddress": n["mac"],
                    "signalStrength": n["rssi"]
                })

            payload = {
                "considerIp": "true",
                "wifiAccessPoints": wifi_aps
            }

            url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={self.api_key}"
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.last_coords = {
                    "latitude": data["location"]["lat"],
                    "longitude": data["location"]["lng"],
                    "accuracy": data["accuracy"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "network"
                }
                self.last_request_time = now
                return self.last_coords
            else:
                print(f"[WIFI-GPS] API Error {response.status_code}: {response.text}")
                return self._error_response(f"API_ERROR_{response.status_code}")

        except Exception as e:
            print(f"[WIFI-GPS] Critical failure: {e}")
            return self._error_response("CRITICAL_ERROR")

    def _error_response(self, code: str) -> Dict:
        return {
            "latitude": 0.0,
            "longitude": 0.0,
            "accuracy": 0.0,
            "error": code,
            "source": "network"
        }
