import aiohttp
import asyncio
import logging
import json
import time
import pyotp
import base64
import re
from random import randrange

_LOGGER = logging.getLogger(__name__)


SPOTIFY_API_URL = "https://api.spotify.com/v1/me"

class Spotify:
    def __init__(self, sp_dc):
        self._sp_dc = sp_dc
        self._access_token = None
        self._client_id = None
        self._headers = {
            "Authorization": f"Bearer {self._access_token}",
            "App-Platform": "WebPlayer",
            "Content-Type": "application/json"
        }

    async def get_random_user_agent(self):
        """Generate random user agent for requests."""
        return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{randrange(11, 15)}_{randrange(4, 9)}) AppleWebKit/{randrange(530, 537)}.{randrange(30, 37)} (KHTML, like Gecko) Chrome/{randrange(80, 105)}.0.{randrange(3000, 4500)}.{randrange(60, 125)} Safari/{randrange(530, 537)}.{randrange(30, 36)}"

    async def generate_totp(self):
        """Generate TOTP code using transformed cipher and get Spotify server time."""
        secret_cipher = [12, 56, 76, 33, 88, 44, 88, 33, 78, 78, 11, 66, 22, 22, 55, 69, 54]
        processed = [byte ^ ((i % 33) + 9) for i, byte in enumerate(secret_cipher)]
        processed_str = "".join(map(str, processed))
        utf8_bytes = processed_str.encode('utf-8')
        hex_str = utf8_bytes.hex()
        secret_bytes = bytes.fromhex(hex_str)
        b32_secret = base64.b32encode(secret_bytes).decode('utf-8')
        totp = pyotp.TOTP(b32_secret)

        headers = {
            "Host": "open.spotify.com",
            "User-Agent": await self.get_random_user_agent(),
            "Accept": "*/*",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://open.spotify.com/api/server-time", headers=headers) as resp:
                data = await resp.json()
                server_time = data.get("serverTime")
                if server_time is None:
                    raise Exception("Failed to fetch server time from Spotify")
        return totp, server_time

    async def get_access_token(self):
        """Fetch a new access token using sp_dc and TOTP."""
        totp, server_time = await self.generate_totp()
        otp_code = totp.at(int(server_time))

        timestamp_ms = int(time.time() * 1000)

        params = {
            'reason': 'init',
            'productType': 'web-player',
            'totp': otp_code,
            'totpServerTime': server_time,
            'totpVer': '5',
            'sTime': server_time,
            'cTime': timestamp_ms,
            'buildVer': 'web-player_2025-06-11_1749636522102_27bd7d1',
            'buildDate': '2025-06-11'
        }

        headers = {
            "User-Agent": await self.get_random_user_agent(),
            "Accept": "*/*",
            "Cookie": f"sp_dc={self._sp_dc}"
        }

        url = "https://open.spotify.com/api/token"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    token = data.get("accessToken")
                    if token and await self.check_token_validity(token):
                        self._access_token = token
                        self._headers["Authorization"] = f"Bearer {token}"
                        return token
                    _LOGGER.error(f"Token fetch failed or invalid: {data}")
            except Exception as e:
                _LOGGER.error(f"Exception while fetching token: {e}")
        return None

    async def make_api_call(self, method, url, **kwargs):
        """Make API calls with automatic token refresh on invalid tokens."""
        try:
            if not self._access_token:
                await self.get_access_token()
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self._headers, **kwargs) as response:
                    if response.status == 401:
                        await self.get_access_token()
                        async with session.request(method, url, headers=self._headers, **kwargs) as retry_response:
                            if retry_response.content_type == "application/json":
                                data = await retry_response.json()
                            else:
                                data = await retry_response.text()

                            return {"status_code": retry_response.status, "data": data}
                    if response.content_type == "application/json":
                        data = await response.json()
                    else:
                        data = await response.text()

                    return {"status_code": response.status, "data": data}
        except aiohttp.ClientError as e:
            _LOGGER.error(f"An error occurred during API request: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"An unexpected error occurred: {e}")
            return None


    async def check_token_validity(self, token):
        """Check validity of access token"""
        headers = {
            "Authorization": f"Bearer {token}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me", headers=headers) as response:
                return response.status == 200

    async def get_artist(self, artist_id):
        """Get artist name from HTML"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://open.spotify.com/artist/{artist_id}") as response:
                html = await response.text()
                return html.split("<title>")[1].split("|")[0].strip()

    async def get_user_profile(self):
        """Get user's Spotify profile name from SP_DC."""
        return await self.make_api_call("GET", "https://api.spotify.com/v1/me")

    async def pause(self, device):
        """Pause playback."""
        data = {'command': {'endpoint': 'pause'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def resume(self, device):
        """Resume playback."""
        data = {'command': {'endpoint': 'resume'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def previous(self, device):
        """Skip to previous track."""
        data = {'command': {'endpoint': 'skip_prev'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))
    
    async def next(self, device):
        """Skip to next track."""
        data = {'command': {'endpoint': 'skip_next'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def seek(self, device, seek_ms):
        """Seek to position in milliseconds."""
        data = {'command': {'endpoint': 'seek_to' , 'value': seek_ms}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def set_shuffle(self, device, shuffle):
        """Set shuffle mode."""
        data = {'command': {'endpoint': 'set_shuffling_context' , 'value': shuffle}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def set_repeat(self, device, context=False, track=False):
        """Set repeat mode."""
        data = {'command': {'endpoint': 'set_options' , 'repeating_context': context , 'repeating_track': track}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def volume(self, device, volume):
        """Set volume percentage."""
        data = {'volume': volume * 65535}
        return await self.make_api_call("PUT", f"https://gew1-spclient.spotify.com/connect-state/v1/connect/volume/from//to/{device}", data=json.dumps(data))

    async def select_device(self, device, control_device):
        """Change playback device."""
        data = {'transfer_options': {'restore_paused': 'restore'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/connect/transfer/from//to/{device}", data=json.dumps(data))
