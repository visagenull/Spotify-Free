import aiohttp
import asyncio
import json
import random
import string
import logging
from aiohttp import WSMsgType, ClientResponseError
import ssl
ssl_context = ssl.create_default_context()

_LOGGER = logging.getLogger(__name__)

class SpotifyWebsocket:
    def __init__(self, hass, access_token):
        """Initialize the websocket."""
        self.hass = hass
        self.access_token = access_token
        self.connection_id = None
        self.device_id = None
        self.ws = None
        self._devices = {}
        self.response = None

    async def create_device(self):
        """Create control device."""
        self.device_id = ''.join(random.choices(string.ascii_letters, k=40))

        url = "https://guc-spclient.spotify.com/track-playback/v1/devices"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "device": {
                "brand": "spotify",
                "capabilities": {
                    "change_volume": True,
                    "enable_play_token": True,
                    "supports_file_media_type": True,
                    "play_token_lost_behavior": "pause",
                    "disable_connect": True
                },
                "device_id": self.device_id,
                "device_type": "computer",
                "metadata": {},
                "model": "web_player",
                "name": "Home Assistant Spotify Free",
                "platform_identifier": "web_player windows 10;chrome 87.0.4280.66;desktop"
            },
            "connection_id": self.connection_id,
            "client_version": "harmony:4.11.0-af0ef98",
            "volume": 65535
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    return self.device_id
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error creating device: {err}")
            return None

    async def update_device_state(self):
        """Register devices for Spotify player updates."""
        url = f"https://guc-spclient.spotify.com/connect-state/v1/devices/hobs_{self.device_id}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "x-spotify-connection-id": self.connection_id,
            "Content-Type": "application/json"
        }

        payload = {
            "member_type": "CONNECT_STATE",
            "device": {
                "device_info": {
                    "capabilities": {
                        "can_be_player": False,
                        "hidden": True
                    }
                }
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error updating device state: {err}")

    async def ping_loop(self):
        """Keep the WebSocket connection alive by sending pings every 30 seconds."""
        while True:
            try:
                ping_message = {"type": "ping"}
                if self.ws is not None and not self.ws.closed:
                    await self.ws.send_json(ping_message)
                else:
                    _LOGGER.warning("WebSocket is closed. Stopping ping loop.")
                    break
            except Exception as err:
                _LOGGER.error(f"Error sending ping: {err}")
                break  # Exit the loop on error to allow reconnection logic
            await asyncio.sleep(30)

    
    async def spotify_websocket(self):
        """Create and manage the Spotify websocket connection."""
        uri = f"wss://gew1-dealer.spotify.com/?access_token={self.access_token}"


        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(uri, ssl=ssl_context) as ws:
                    self.ws = ws
                    msg = await ws.receive()
                    if msg.type == WSMsgType.TEXT:
                        self.connection_id = json.loads(msg.data)["headers"]["Spotify-Connection-Id"]
                        device_id = await self.create_device()

                        if device_id:
                            await self.update_device_state()
                            asyncio.create_task(self.ping_loop())

                            async for msg in ws:
                                if msg.type == WSMsgType.TEXT:
                                    response_data = json.loads(msg.data)
                                    if response_data.get("type") == "pong":
                                        continue
                                    await self.process(response_data)
                                elif msg.type == WSMsgType.CLOSED:
                                    _LOGGER.warning("WebSocket closed")
                                    break
                                elif msg.type == WSMsgType.ERROR:
                                    _LOGGER.error("WebSocket error")
                                    break

        except ClientResponseError as e:
            if e.status == 401:
                _LOGGER.error("WebSocket connection failed: Unauthorized (401) – Retrying.")
                self.hass.bus.async_fire("spotify_websocket_restart")
            else:
                _LOGGER.error(f"WebSocket failed with status code {e.status}")
        except aiohttp.ClientConnectionError as e:
            _LOGGER.error(f"WebSocket connection error: {e}")
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred: {e}")


    async def process(self, response):
        """Process the websocket response."""
        try:
            if 'cluster' in response['payloads'][0]:
                devices = response['payloads'][0]['cluster']['devices']
                device_dict = {}
                for device_id, device_info in devices.items():
                    alias_id = next(iter(device_info.get("device_aliases", {})), None)
                    display_name = device_info["device_aliases"].get(alias_id, {}).get("display_name") if alias_id else device_info.get("name", device_id)
                    device_dict[display_name] = device_id
                _LOGGER.info(device_dict)
                self._devices = device_dict
            self.response = response
            self.hass.bus.async_fire("spotify_websocket_update")
            
        except Exception as e:
            _LOGGER.error(f"Error processing response: {e}")
