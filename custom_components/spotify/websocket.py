import aiohttp
from typing import Callable
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
    def __init__(self, access_token: str):
        """Initialise websocket with access token."""

        self.__access_token = access_token
        self.__connection_id = None
        self.__device_id = None
        self.__ws = None
        self.__devices = {}
        self.__response = None
        self.__websocket_task = None
        self.__reconnect_task = None
        self.__reconnect_delay = 10
        self.__callback_function = None


    @property
    def response(self):
        """Latest websocket response"""
        return self.__response
    
    
    @property
    def devices(self):
        """Latest websocket response"""
        return self.__devices


    async def register_callback(self, callback_function: Callable):
        """Function to be run on websocket update."""
        self.__callback_function = callback_function


    async def start_websocket(self):
        """Create and manage the Spotify websocket connection."""

        url = f"wss://gew1-dealer.spotify.com/?access_token={self.__access_token}"

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, ssl=ssl_context) as self.__ws:
                msg = await self.__ws.receive()
                if msg.type == WSMsgType.TEXT:
                    self.__connection_id = json.loads(msg.data)["headers"]["Spotify-Connection-Id"]
                    _LOGGER.info(f"WebSocket connection established. Connection ID: {self.__connection_id}")
                    await self.__update_device_state()
                    asyncio.create_task(self.__ping_loop())

                    async for msg in self.__ws:
                        if msg.type == WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "pong":
                                continue
                            await self.__process(data)
                        elif msg.type == WSMsgType.CLOSED:
                            _LOGGER.warning("WebSocket closed")
                            break
                        elif msg.type == WSMsgType.ERROR:
                            _LOGGER.error("WebSocket error")
                            break


    async def __update_device_state(self):
        self.__device_id = ''.join(random.choices(string.ascii_letters, k=40))
        url = f"https://guc-spclient.spotify.com/connect-state/v1/devices/hobs_{self.__device_id}"

        headers = {
            "Authorization": f"Bearer {self.__access_token}",
            "x-spotify-connection-id": self.__connection_id,
            "Content-Type": "application/json"
        }

        json = {
            "member_type": "CONNECT_STATE",
            "device": {
                "device_info": {
                    "capabilities": {
                        "can_be_player": True,
                        "hidden": False
                    }
                }
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=json, headers=headers) as response:
                    response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error updating device state: {err}")


    async def __ping_loop(self):
        """Keep the WebSocket connection alive."""
        while self.__ws:
            try:
                await self.__ws.send_json({"type": "ping"})
            except Exception as err:
                _LOGGER.error(f"Ping failed: {err}")
                break
            await asyncio.sleep(30)


    async def __process(self, response):
        """Process the websocket response."""
        try:
            if 'cluster' in response['payloads'][0]:
                devices = response['payloads'][0]['cluster']['devices']
                device_dict = {}
                for device_id, device_info in devices.items():
                    alias_id = next(iter(device_info.get("device_aliases", {})), None)
                    display_name = device_info["device_aliases"].get(alias_id, {}).get("display_name") if alias_id else device_info.get("name", device_id)
                    device_dict[display_name] = device_id
                self.__devices = device_dict
            self.__response = response

            await self.__callback_function()

        except Exception as e:
            _LOGGER.error(f"Error processing response: {e}")

