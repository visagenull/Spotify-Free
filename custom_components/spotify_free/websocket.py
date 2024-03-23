import aiohttp
import asyncio
import websockets
import json
import random
import string
import logging

_LOGGER = logging.getLogger(__name__)

class SpotifyWebsocket:
    def __init__(self, hass, access_token):
        """Initialise websocket."""
        self.hass = hass
        self.access_token = access_token
        self.connection_id = None
        self.device_id = None
        self.ws = None
        self._devices = []

    async def create_device(self):
        """Create control device."""

        self.device_id = ''.join(random.choices(string.ascii_letters, k=40))

        url = "https://guc-spclient.spotify.com/track-playback/v1/devices"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {"device": {"brand": "spotify", "capabilities":
                    {"change_volume": True, "enable_play_token": True,
                    "supports_file_media_type": True,
                    "play_token_lost_behavior": "pause",
                    "disable_connect": True},
                    "device_id": self.device_id, "device_type": "computer",
                    "metadata": {}, "model": "web_player", "name": "Spotify Free Home Assistant",
                    "platform_identifier": "web_player windows 10;chrome 87.0.4280.66;desktop"},
                    "connection_id": self.connection_id, "client_version":
                    "harmony:4.11.0-af0ef98",
                    "volume": 65535}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    return self.device_id
        except aiohttp.ClientError as err:
            print(f"Error: {err}")

        return None

    async def update_device_state(self):
        """Register devices for Spotify player updates."""

        url = f"https://guc-spclient.spotify.com/connect-state/v1/devices/hobs_{self.device_id}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "x-spotify-connection-id": self.connection_id,
            "Content-Type": "application/json"
        }

        payload = {"member_type": "CONNECT_STATE", "device": {"device_info":
                    {"capabilities": {"can_be_player": False,
                    "hidden": True}}}}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error: {err}")

    async def ping_loop(self):
        """Keep websocket alive."""
        while True:
            ping_message = {"type": "ping"}
            await self.ws.send(json.dumps(ping_message))
            await asyncio.sleep(30)

    async def spotify_websocket(self):
        """Create websocket."""

        uri = f"wss://gew1-dealer.spotify.com/?access_token={self.access_token}"

        try:
            async with websockets.connect(uri) as ws:
                self.ws = ws
                response = await self.ws.recv()
                self.connection_id = json.loads(response)["headers"]["Spotify-Connection-Id"]
                device_id = await self.create_device()

                if device_id:
                    await self.update_device_state()
                    asyncio.create_task(self.ping_loop())

                    while True:
                        response = await ws.recv()
                        response_data = json.loads(response)
                        if response_data.get("type") == "pong":
                            pass
                        else:
                            try:
                                self._devices = {}
                                data = response_data['payloads'][0]['cluster']['devices']
                                for device_id, device_data in data.items():
                                    name = device_data['name']
                                    self._devices[name] = {'device_id': device_id, **device_data}
                            except:
                                pass
                            self.hass.bus.async_fire("spotify_websocket_update")

        except websockets.ConnectionClosed as e:
            _LOGGER.error(f"WebSocket connection closed: {e}")
            self.hass.bus.async_fire("spotify_websocket_restart")
        except asyncio.IncompleteReadError as e:
            _LOGGER.error(f"Incomplete read error: {e}")
            self.hass.bus.async_fire("spotify_websocket_restart")
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred: {e}")
