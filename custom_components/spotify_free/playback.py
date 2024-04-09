import aiohttp
import asyncio
import logging
import json

_LOGGER = logging.getLogger(__name__)

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
        """Request access token from Spotify."""
        url = 'https://open.spotify.com/get_access_token?'
        cookies = {'sp_dc': self._sp_dc}
        headers = {
            'user-agent': (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 "
                "Safari/537.36"
            )
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, cookies=cookies) as response:
                    if response.status == 200:
                        data = await response.json()
                        access_token = data['accessToken']
                        self._access_token = access_token
                        self._headers["Authorization"] = f"Bearer {self._access_token}"
                        return access_token
                    else:
                        _LOGGER.error(f"Error: {response}")
        except Exception as e:
            _LOGGER.error(f"Error: {str(e)}")

    async def get_user_profile(self):
        """Get user's Spotify profile name from SP_DC."""
        return await self.make_api_call("GET", "https://api.spotify.com/v1/me")

    async def pause(self, device, control_device):
        """Pause playback."""
        data = {'command': {'endpoint': 'pause'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from/{control_device}/to/{device}", data=json.dumps(data))

    async def resume(self, device, control_device):
        """Resume playback."""
        data = {'command': {'endpoint': 'resume'}}
        return await self.make_api_call("POST", f"https://gew1-spclient.spotify.com/connect-state/v1/player/command/from/{control_device}/to/{device}", data=json.dumps(data))

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

    async def lyrics(self, track_id):
        """Get lyrics of a track."""
        params = {
            'format': 'json',
            'vocalRemoval': 'false',
            'market': 'from_token'
        }
        return await self.make_api_call("GET", f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}", params=params)