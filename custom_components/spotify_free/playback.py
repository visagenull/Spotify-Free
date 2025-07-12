import aiohttp
import logging
import json
import time
import pyotp
import base64
import asyncio
from random import randrange

_LOGGER = logging.getLogger(__name__)

def retry_async(max_retries=3, base_delay=2, exceptions=(aiohttp.ClientError, asyncio.TimeoutError, OSError)):
    """A retry decorator for async functions with exponential backoff."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    wait_time = base_delay * (2 ** attempt)
                    _LOGGER.warning(f"{func.__name__} failed on attempt {attempt + 1}: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            _LOGGER.error(f"{func.__name__} failed after {max_retries} attempts.")
            return None
        return wrapper
    return decorator

class Spotify:
    def __init__(self, sp_dc):
        self._sp_dc = sp_dc
        self._access_token = None
        self._headers = {
            "Authorization": f"Bearer {self._access_token}",
            "App-Platform": "WebPlayer",
            "Content-Type": "application/json"
        }

    async def get_random_user_agent(self):
        return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{randrange(11, 15)}_{randrange(4, 9)}) AppleWebKit/{randrange(530, 537)}.{randrange(30, 37)} (KHTML, like Gecko) Chrome/{randrange(80, 105)}.0.{randrange(3000, 4500)}.{randrange(60, 125)} Safari/{randrange(530, 537)}.{randrange(30, 36)}"

    @retry_async()
    async def generate_totp(self):
        url = "https://raw.githubusercontent.com/Thereallo1026/spotify-secrets/refs/heads/main/secrets/secretBytes.json"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch TOTP secrets from GitHub. Status: {resp.status}")
                text = await resp.text()
                secrets_list = json.loads(text)


        # Pick the entry with the highest version
        latest_entry = max(secrets_list, key=lambda x: x["version"])
        version = latest_entry["version"]
        secret_cipher = latest_entry["secret"]

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

        return totp, server_time, version

    @retry_async()
    async def get_access_token(self):
        totp, server_time, totp_version = await self.generate_totp()
        otp_code = totp.at(int(server_time))
        timestamp_ms = int(time.time() * 1000)

        params = {
            'reason': 'init',
            'productType': 'web-player',
            'totp': otp_code,
            'totpServerTime': server_time,
            'totpVer': str(totp_version),  # ✅ Use dynamic version
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
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                token = data.get("accessToken")
                if token and await self.check_token_validity(token):
                    self._access_token = token
                    self._headers["Authorization"] = f"Bearer {token}"
                    return token
                _LOGGER.error(f"Token fetch failed or invalid: {data}")
        return None


    @retry_async()
    async def make_api_call(self, method, url, **kwargs):
        if not self._access_token:
            await self.get_access_token()

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=self._headers, **kwargs) as response:
                if response.status == 401:
                    await self.get_access_token()
                    async with session.request(method, url, headers=self._headers, **kwargs) as retry_response:
                        data = await self._get_response_data(retry_response)
                        return {"status_code": retry_response.status, "data": data}
                data = await self._get_response_data(response)
                return {"status_code": response.status, "data": data}

    async def _get_response_data(self, response):
        if response.content_type == "application/json":
            return await response.json()
        return await response.text()

    @retry_async()
    async def check_token_validity(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me", headers=headers) as response:
                return response.status == 200

    async def get_user_profile(self):
        return await self.make_api_call("GET", "https://api.spotify.com/v1/me")

    async def get_track_info(self, track_id):
        return await self.make_api_call("GET", f"https://api.spotify.com/v1/tracks?ids={track_id}&market=from_token")

    async def pause(self, device):
        data = {'command': {'endpoint': 'pause'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def resume(self, device):
        data = {'command': {'endpoint': 'resume'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def previous(self, device):
        data = {'command': {'endpoint': 'skip_prev'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def next(self, device):
        data = {'command': {'endpoint': 'skip_next'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def seek(self, device, seek_ms):
        data = {'command': {'endpoint': 'seek_to', 'value': seek_ms}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def set_shuffle(self, device, shuffle):
        data = {'command': {'endpoint': 'set_shuffling_context', 'value': shuffle}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def set_repeat(self, device, context=False, track=False):
        data = {'command': {'endpoint': 'set_options', 'repeating_context': context, 'repeating_track': track}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from//to/{device}", data=json.dumps(data))

    async def volume(self, device, volume):
        data = {'volume': volume * 65535}
        return await self.make_api_call("PUT", f"https://gew1-spclient.spotify.com/connect-state/v1/connect/volume/from//to/{device}", data=json.dumps(data))

    async def select_device(self, device):
        data = {'transfer_options': {'restore_paused': 'restore'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/connect/transfer/from//to/{device}", data=json.dumps(data))
