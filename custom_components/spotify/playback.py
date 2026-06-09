import aiohttp
import json
import logging
from random import randrange

import pyotp

SECRET_BYTES_url = "https://raw.githubusercontent.com/xyloflake/spot-secrets-go/main/secrets/secretBase32.json"
PATHFINDER_url = "https://api-partner.spotify.com/pathfinder/v2/query"
TOKEN_url = "https://open.spotify.com/api/token"

_LOGGER = logging.getLogger(__name__)


async def get_access_token(sp_dc: str) -> str:
    """Request access token from Spotify using "sp_dc" cookie"""
    totp, server_time, version = await _generate_totp()

    params = {
        "reason": "init",
        "productType": "web-player",
        "totp": totp.at(int(server_time)),
        "totpServerTime": server_time,
        "totpVer": str(version),
    }

    headers = {
        "User-Agent": await _generate_user_agent(),
        "Cookie": f"sp_dc={sp_dc}",
        "Accept": "*/*",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(TOKEN_url, params=params, headers=headers) as response:
            data = await response.json()

    access_token = data.get("accessToken")
    if not access_token:
        raise RuntimeError("failed to acquire access token")
        

    return access_token



async def _generate_user_agent() -> str:
    return (
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{randrange(11,15)}_{randrange(4,9)}) "
        f"AppleWebKit/{randrange(530,537)}.{randrange(30,37)} "
        f"(KHTML, like Gecko) Chrome/{randrange(90,115)}.0."
        f"{randrange(3000,5000)}.{randrange(60,150)} Safari/"
        f"{randrange(530,537)}.{randrange(30,36)}"
    )


async def _generate_totp():
    async with aiohttp.ClientSession() as session:
        async with session.get(SECRET_BYTES_url) as response:
            text = await response.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse JSON: {e}")
            
    base32_secret = data.get("secret")
    version = data.get("version")
    
    if not base32_secret or version is None:
        _LOGGER.error("Secret or version is missing in the responseonse")

    totp = pyotp.TOTP(base32_secret)

    headers = {
        "User-Agent": await _generate_user_agent(),
        "Accept": "*/*",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://open.spotify.com/api/server-time",
            headers=headers
        ) as response:
            data = await response.json()

    server_time = data.get("serverTime")
    if server_time is None:
        _LOGGER.error("Spotify server time missing")

    return totp, server_time, version


class Playback:
    def __init__(self, sp_dc: str, access_token: str, session: aiohttp.ClientSession):
        """DON NOT USE THIS, use playback.create(sp_dc)"""
        self._sp_dc = sp_dc
        self._access_token = access_token
        self._session = session
        self._device_id = None
    
    @classmethod
    async def create(cls, sp_dc: str):
        """Create Playback client"""
        access_token = await get_access_token(sp_dc)

        headers = {
            "User-Agent": await _generate_user_agent(),
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        session = aiohttp.ClientSession(headers=headers)

        return cls(sp_dc, access_token, session)
    

    async def close(self):
        """Close aiohttp session"""
        if self._session:
            await self._session.close()


    async def refresh_token(self):
        """Refresh access token"""
        self._access_token = await get_access_token(self._sp_dc)
        return self._access_token


    @property
    def access_token(self):
        """Access token used by this instance"""
        return self._access_token
    

    @property
    def device_id(self):
        """The device currently being controlled"""
        return self._device_id


    @device_id.setter
    def device_id(self, device_id: str):
        """Set the device to be controlled"""
        self._device_id = device_id


    async def __request(self, method: str, url: str, json: dict = {}):
        response = await self._session.request(method, url, json=json)

        if response.status != 200:
            await self.refresh_token()
            _LOGGER.debug("Requesting new access token")
            response = await self._session.request(method, url, json=json)
            if response.status != 200:
                _LOGGER.error("Request Failed", response)
                return False

        return response 
    

    async def get_username(self):
        """Returns the username from the access token"""
        operation = "profileAttributes"
        sha = "53bcb064f6cd18c23f752bc324a791194d20df612d8e1239c735144ab0399ced"

        json = {
            "operationName": operation,
            "extensions": {
                "persistedQuery": {
                "version": 1,
                "sha256Hash": sha
                }
            }
        }

        response = await self.__request("POST", PATHFINDER_url, json=json)
        response = await response.json()
        response = response.get("data", {}).get("me", {}).get("profile", {}).get("username")
        return response 


    async def __command(self, command: dict):
        url = f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from/app/to/{self._device_id}"
        return await self.__request("POST", url, json={"command": command})


    async def pause(self):
        """Pauses playback on currently selected device"""
        return await self.__command({"endpoint": "pause"})


    async def resume(self):
        """Resumes playback on currently selected device"""
        return await self.__command({"endpoint": "resume"})
    

    async def next(self):
        """Skips to next track on currently selected device"""
        return await self.__command({"endpoint": "skip_next"})


    async def previous(self):
        """Skips to previous track on currently selected device"""
        return await self.__command({"endpoint": "skip_prev"})


    async def seek(self, seek_ms: int):
        """Seeks to position in ms on currently selected device"""
        return await self.__command({"endpoint": "seek_to", "value": seek_ms})


    async def set_shuffle(self, enabled: bool):
        """Sets shuffle mode on currently selected device"""
        return await self.__command({"endpoint": "set_shuffling_context", "value": enabled})


    async def set_repeat(self, context, track):
        """Sets repeat mode on currently selected device"""
        return await self.__command({"endpoint": "set_options", "repeating_context": context, "repeating_track": track})


    async def volume(self, level: float):
        """Sets volume on currently selected device"""
        url = f"https://gew1-spclient.spotify.com/connect-state/v1/connect/volume/from/app/to/{self._device_id}"
        return await self.__request("PUT", url, json={"volume": int(level * 65535)})


    async def select_device(self, device_id: str):
        """Change playback to selected device"""
        url = f"https://gew1-spclient.spotify.com/connect-state/v1/connect/transfer/from/app/to/{device_id}"
        return await self.__request("POST", url, json={"transfer_options": {"restore_paused": "restore"}})
