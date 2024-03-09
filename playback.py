import aiohttp
import asyncio

class Spotify:
    def __init__(self, sp_dc):
        self._sp_dc = sp_dc
        self._access_token = None
        self._headers = {
            "Authorization": f"Bearer {self._access_token}",
            "App-Platform": "WebPlayer",
            "Content-Type": "application/json"
        }

    @staticmethod
    def refresh_token_decorator(api_function):
        async def wrapper(self, *args, **kwargs):
            try:
                response = await api_function(self, *args, **kwargs)
                if response is not None:
                    if response["status_code"] == 401:
                        access_token = await self.get_access_token()
                        self._headers["Authorization"] = f"Bearer {access_token}"
                        refreshed_response = await api_function(self, *args, **kwargs)
                        return {"status_code": refreshed_response["status_code"], "data": refreshed_response["data"]}
                    if response["status_code"] == 404:
                        print(response["data"])
                    return response
            except Exception as e:
                print(f"An error occurred during API request: {e}")

        return wrapper

    async def get_access_token(self):
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
                        print(f"Error: {response}")

        except Exception as e:
            print(f"Error: {str(e)}")

    @refresh_token_decorator
    async def get_user_profile(self):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def pause(self):
        async with aiohttp.ClientSession() as session:
            async with session.put("https://api.spotify.com/v1/me/player/pause", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def resume(self):
        async with aiohttp.ClientSession() as session:
            async with session.put("https://api.spotify.com/v1/me/player/play", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def get_playback_status(self):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me/player", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def next(self):
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.spotify.com/v1/me/player/next", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def previous(self):
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.spotify.com/v1/me/player/previous", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def seek(self, seek_ms):
        async with aiohttp.ClientSession() as session:
            async with session.put(f"https://api.spotify.com/v1/me/player/seek?position_ms={seek_ms}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def volume_percent(self, volume_percent):
        async with aiohttp.ClientSession() as session:
            async with session.put(f"https://api.spotify.com/v1/me/player/volume?volume_percent={volume_percent}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def set_shuffle(self, shuffle):
        async with aiohttp.ClientSession() as session:
            async with session.put(f"https://api.spotify.com/v1/me/player/shuffle?state={shuffle}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def set_smart_shuffle(self, smart_shuffle):
        async with aiohttp.ClientSession() as session:
            async with session.put(f"https://api.spotify.com/v1/me/player/smart_shuffle?state={smart_shuffle}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def set_repeat(self, repeat):
        async with aiohttp.ClientSession() as session:
            async with session.put(f"https://api.spotify.com/v1/me/player/repeat?state={repeat}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

    @refresh_token_decorator
    async def select_device(self, device, control_device):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://gew1-spclient.spotify.com/connect-state/v1/connect/transfer/from/{control_device}/to/{device}", headers=self._headers) as response:
                return {"status_code": response.status, "data": await response.json()}

