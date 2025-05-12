import aiohttp
import asyncio
import logging
import json
import time
import pyotp
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
        return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{randrange(11, 15)}_{randrange(4, 9)}) AppleWebKit/{randrange(530, 537)}.{randrange(30, 37)} (KHTML, like Gecko) Chrome/{randrange(80, 105)}.0.{randrange(3000, 4500)}.{randrange(60, 125)} Safari/{randrange(530, 537)}.{randrange(30, 36)}"


    async def base32_from_bytes(self, e, secret_sauce):
        t = 0
        n = 0
        r = ""
        for byte in e:
            n = (n << 8) | byte
            t += 8
            while t >= 5:
                index = (n >> (t - 5)) & 31
                r += secret_sauce[index]
                t -= 5
        if t > 0:
            r += secret_sauce[(n << (5 - t)) & 31]
        return r


    async def clean_buffer(self, e):
        e = e.replace(" ", "")
        return bytes(int(e[i:i+2], 16) for i in range(0, len(e), 2))

    async def generate_totp(self):
        _LOGGER.debug("Generating TOTP")
        secret_cipher_bytes = [
            12, 56, 76, 33, 88, 44, 88, 33,
            78, 78, 11, 66, 22, 22, 55, 69, 54,
        ]
        transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_cipher_bytes)]
        joined = "".join(str(num) for num in transformed)
        utf8_bytes = joined.encode("utf-8")
        hex_str = "".join(format(b, 'x') for b in utf8_bytes)
        secret_bytes = await self.clean_buffer(hex_str)
        secret_sauce = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        secret = await self.base32_from_bytes(secret_bytes, secret_sauce)
        _LOGGER.debug("Computed secret: %s", secret)

        headers = {
            "Host": "open.spotify.com",
            "User-Agent": await self.get_random_user_agent(),
            "Accept": "*/*",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://open.spotify.com/server-time", headers=headers) as response:
                data = await response.json()
                server_time = data.get("serverTime")
                if server_time is None:
                    raise Exception("Failed to get server time")
        return pyotp.TOTP(secret, digits=6, interval=30), server_time, secret



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



    async def get_access_token(self):

        totp_obj, server_time, _ = await self.generate_totp()
        timestamp = int(time.time())
        otp_value = totp_obj.at(server_time)
        
        params = {
            "reason": "transport",
            "productType": "web_player",
            "totp": otp_value,
            "totpVer": 5,
            "ts": timestamp,
        }

        headers = {
            "User-Agent": await self.get_random_user_agent(),
            "Accept": "*/*",
            "Cookie": f"sp_dc={self._sp_dc}",
        }

        url = "https://open.spotify.com/get_access_token"
        
        retries = 5
        async with aiohttp.ClientSession() as session:
            for attempt in range(retries):
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        data = await response.json()
                        access_token = data['accessToken']
                        if await self.check_token_validity(access_token):
                            self._access_token = access_token
                            self._headers["Authorization"] = f"Bearer {self._access_token}"
                            return access_token
                
                except Exception as e:
                    _LOGGER.error(f"Get token Error: {str(e)}")
                    return
            return


    async def check_token_validity(self, token):
        headers = {
            "Authorization": f"Bearer {token}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me", headers=headers) as response:
                return response.status == 200

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
