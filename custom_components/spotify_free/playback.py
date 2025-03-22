import aiohttp
import asyncio
import logging
import json
import pyotp
import time
from random import randrange

_LOGGER = logging.getLogger(__name__)

TOKEN_URL = "https://open.spotify.com/get_access_token"


def get_random_user_agent():
    return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{randrange(11, 15)}_{randrange(4, 9)}) AppleWebKit/{randrange(530, 537)}.{randrange(30, 37)} (KHTML, like Gecko) Chrome/{randrange(80, 105)}.0.{randrange(3000, 4500)}.{randrange(60, 125)} Safari/{randrange(530, 537)}.{randrange(30, 36)}"


def base32_from_bytes(e: bytes, secret_sauce: str) -> str:
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


def clean_buffer(e: str) -> bytes:
    e = e.replace(" ", "")
    return bytes(int(e[i:i+2], 16) for i in range(0, len(e), 2))


async def generate_totp(session: aiohttp.ClientSession) -> tuple[pyotp.TOTP, int, str]:
    _LOGGER.debug("Generating TOTP")
    secret_cipher_bytes = [
        12, 56, 76, 33, 88, 44, 88, 33,
        78, 78, 11, 66, 22, 22, 55, 69, 54,
    ]
    transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_cipher_bytes)]
    joined = "".join(str(num) for num in transformed)
    utf8_bytes = joined.encode("utf-8")
    hex_str = "".join(format(b, 'x') for b in utf8_bytes)
    secret_bytes = clean_buffer(hex_str)
    secret_sauce = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    secret = base32_from_bytes(secret_bytes, secret_sauce)
    _LOGGER.debug("Computed secret: %s", secret)

    headers = {
        "Host": "open.spotify.com",
        "User-Agent": get_random_user_agent(),
        "Accept": "*/*",
    }
    async with session.get("https://open.spotify.com/server-time", headers=headers) as resp:
        resp.raise_for_status()
        json_data = await resp.json()
        server_time = json_data.get("serverTime")
        if server_time is None:
            raise Exception("Failed to get server time")
    return pyotp.TOTP(secret, digits=6, interval=30), server_time, secret


async def async_refresh_token(cookies: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        totp_obj, server_time, _ = await generate_totp(session)
        _LOGGER.debug("Got TOTP object: %s", totp_obj)
        timestamp = int(time.time())
        otp_value = totp_obj.at(server_time)
        _LOGGER.debug("Using OTP value: %s", otp_value)
        sp_dc = cookies.get("sp_dc", "")
        params = {
            "reason": "transport",
            "productType": "web_player",
            "totp": otp_value,
            "totpVer": 5,
            "ts": timestamp,
        }
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "*/*",
            "Cookie": f"sp_dc={sp_dc}" if sp_dc else "",
        }
        try:
            async with session.get(
                TOKEN_URL,
                params=params,
                allow_redirects=False,
                headers=headers,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                _LOGGER.debug("Got response: %s", data)
        except aiohttp.ClientError as ex:
            _LOGGER.exception("Error getting token: %s", ex)
            raise ex

        token = data.get("accessToken", "")

        if len(token) != 374:
            _LOGGER.debug("Transport mode token length (%d) != 374, retrying with mode 'init'", len(token))
            params["reason"] = "init"
            async with session.get(
                TOKEN_URL,
                params=params,
                allow_redirects=False,
                headers=headers,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                _LOGGER.debug("Got response (init mode): %s", data)

        if not data or "accessToken" not in data:
            raise Exception("Unsuccessful token request")

        return {
            "access_token": data["accessToken"],
            "expires_at": data["accessTokenExpirationTimestampMs"],
            "client_id": data.get("clientId", "")
        }


class Spotify:
    def __init__(self, sp_dc):
        self._sp_dc = sp_dc
        self._access_token = None
        self._headers = {
            "Authorization": f"Bearer {self._access_token}",
            "App-Platform": "WebPlayer",
            "Content-Type": "application/json"
        }

    async def make_api_call(self, method, url, **kwargs):
        try:
            if not self._access_token:
                await self.get_access_token()

            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self._headers, **kwargs) as response:
                    if response.status == 401:
                        await self.get_access_token()
                        response = await session.request(method, url, headers=self._headers, **kwargs)

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
        """Request access token from Spotify using the new method."""
        cookies = {'sp_dc': self._sp_dc}
        token_data = await async_refresh_token(cookies)

        self._access_token = token_data["access_token"]
        self._headers["Authorization"] = f"Bearer {self._access_token}"
        return self._access_token

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

    async def get_playback_status(self):
        """Get info about current playing song and device."""
        return await self.make_api_call("GET", "https://api.spotify.com/v1/me/player")

    async def next(self):
        """Skip to next track."""
        return await self.make_api_call("POST", "https://api.spotify.com/v1/me/player/next")

    async def previous(self):
        """Skip to previous track."""
        return await self.make_api_call("POST", "https://api.spotify.com/v1/me/player/previous")

    async def seek(self, seek_ms):
        """Seek to position in milliseconds."""
        return await self.make_api_call("PUT", f"https://api.spotify.com/v1/me/player/seek?position_ms={seek_ms}")

    async def volume_percent(self, volume_percent):
        """Set volume percentage."""
        return await self.make_api_call("PUT", f"https://api.spotify.com/v1/me/player/volume?volume_percent={volume_percent}")

    async def set_shuffle(self, shuffle):
        """Set shuffle mode."""
        return await self.make_api_call("PUT", f"https://api.spotify.com/v1/me/player/shuffle?state={shuffle}")

    async def set_smart_shuffle(self, smart_shuffle):
        """Set smart shuffle mode, currently unused."""
        return await self.make_api_call("PUT", f"https://api.spotify.com/v1/me/player/smart_shuffle?state={smart_shuffle}")

    async def set_repeat(self, repeat):
        """Set repeat mode."""
        return await self.make_api_call("PUT", f"https://api.spotify.com/v1/me/player/repeat?state={repeat}")

    async def select_device(self, device, control_device):
        """Change playback device."""
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/connect/transfer/from/{control_device}/to/{device}")
    
    async def get_lyrics(self, track_id):
        """Get song lyrics."""
        return await self.make_api_call("GET", f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}")
