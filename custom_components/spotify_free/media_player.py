import asyncio
import logging

import voluptuous as vol
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    PLATFORM_SCHEMA,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.const import (
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.util.dt as dt_util

from . import playback
from . import websocket
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_SPOTIFY_FREE = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("sp_dc"): str,
})


async def async_setup_entry(hass, entry, async_add_entities):
    name = entry.title
    data = entry.data
    entity = SpotifyFree(name, data, hass)
    async_add_entities([entity])


class SpotifyFree(MediaPlayerEntity):
    def __init__(self, name, data, hass):
        self._icon = "mdi:spotify"
        self._sp_dc = data.get("sp_dc")
        self._name = name
        self.hass = hass

        self._track_info = None
        self._current_playback = None
        self._track_name = None
        self._track_id = None
        self._track_artist = None
        self._track_album_name = None
        self._media_image_url = None
        self._current_position = None
        self._media_duration = None
        self._volume = 0
        self._is_muted = False
        self._state = None
        self._repeat_state = None
        self._shuffle_state = None
        self._current_device = None
        self._current_device_id = None
        self._devices = None
        self._control_device = None
        self._track_number = None
        self._playlist = None       
        self.spotify_websocket = None
        self._devices = None
        self._last_update = "1970-01-01T00:00:00+00:00"

        asyncio.create_task(self.reconnect())

    async def async_added_to_hass(self):
        self.playback_instance = playback.Spotify(self._sp_dc)
        await self.websocket()

        self.hass.bus.async_listen("spotify_websocket_update", self.update)
        self.hass.bus.async_listen("spotify_websocket_restart", self.websocket)

        await self.async_update()

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {'entities': []}
        self.hass.data[DOMAIN]['entities'].append(self)

    async def reconnect(self):
        while True:
            try:
                await asyncio.sleep(3600)
                await self.websocket()
            except Exception as e:
                _LOGGER.error("WebSocket reconnect failed: %s", e)
                await asyncio.sleep(30)

    async def ensure_websocket(self):
        if not self.spotify_websocket or self.spotify_websocket_task.done():
            _LOGGER.warning("WebSocket disconnected. Attempting to reconnect.")
            await self.websocket()

    async def update(self, blah):
        self._last_update = dt_util.utcnow()
        await self.async_update()

    async def websocket(self):
        try:
            if self.spotify_websocket:
                self.spotify_websocket_task.cancel()

            access_token = await self.playback_instance.get_access_token()
            self.spotify_websocket = websocket.SpotifyWebsocket(self.hass, access_token)
            self.spotify_websocket_task = self.hass.loop.create_task(
                self.spotify_websocket.spotify_websocket()
            )
            _LOGGER.info("WebSocket reconnected.")
            await self.async_update()
        except Exception as e:
            _LOGGER.error("WebSocket setup failed: %s", e)

    async def async_media_pause(self):
        await self.ensure_websocket()
        await self.playback_instance.pause(self._current_device_id)

    async def async_media_play(self):
        await self.ensure_websocket()
        await self.playback_instance.resume(self._current_device_id)

    async def async_media_previous_track(self):
        await self.ensure_websocket()
        await self.playback_instance.previous(self._current_device_id)

    async def async_media_next_track(self):
        await self.ensure_websocket()
        await self.playback_instance.next(self._current_device_id)

    async def async_media_seek(self, position):
        await self.ensure_websocket()
        await self.playback_instance.seek(self._current_device_id, seek_ms=int(position * 1000))

    async def async_set_repeat(self, repeat):
        await self.ensure_websocket()
        repeat_map = {
            "off": (False, False),
            "all": (True, False),
            "one": (True, True),
        }
        context, track = repeat_map.get(repeat, (False, False))
        await self.playback_instance.set_repeat(self._current_device_id, context, track)

    async def async_set_shuffle(self, shuffle):
        await self.ensure_websocket()
        await self.playback_instance.set_shuffle(self._current_device_id, shuffle)

    async def async_set_volume_level(self, volume):
        await self.ensure_websocket()
        await self.playback_instance.volume(self._current_device_id, volume)

    async def async_mute_volume(self, mute):
        await self.ensure_websocket()
        if self._is_muted:
            await self.playback_instance.volume(self._current_device_id, self._old_volume)
        else:
            self._old_volume = self._volume
            await self.playback_instance.volume(self._current_device_id, volume=0)

    async def async_select_source(self, source):
        await self.ensure_websocket()
        await self.playback_instance.select_device(self._devices[source])

    @property
    def name(self):
        return self._name

    @property
    def supported_features(self):
        return SUPPORT_SPOTIFY_FREE

    @property
    def state(self):
        if self._state is None:
            return STATE_OFF
        return STATE_PLAYING if self._state else STATE_PAUSED

    @property
    def media_title(self):
        return self._track_name

    @property
    def media_artist(self):
        return self._track_artist

    @property
    def media_album_name(self):
        return self._track_album_name

    @property
    def media_playlist(self):
        return getattr(self, '_playlist', None)

    @property
    def media_image_url(self):
        return self._media_image_url

    @property
    def media_track(self):
        return self._track_number if hasattr(self, '_playlist') else None

    @property
    def media_duration(self):
        return self._media_duration

    @property
    def media_position(self):
        if self._state in [True, False]:
            return self._current_position
        return None

    @property
    def media_position_updated_at(self):
        return self._last_update

    @property
    def volume_level(self):
        return self._volume

    @property
    def is_volume_muted(self):
        return self._is_muted

    @property
    def repeat(self):
        repeat_map = {
            (False, False): "off",
            (True, False): "all",
            (True, True): "one",
        }
        return repeat_map.get((self._repeating_context, self._repeating_track), "off")

    @property
    def shuffle(self):
        return self._shuffle_state

    @property
    def icon(self):
        return self._icon

    @property
    def source(self):
        return self._current_device

    @property
    def source_list(self):
        if not self._devices:
            return None
        try:
            return [key for key in self._devices if 'hobs' not in key]
        except Exception as e:
            _LOGGER.warning("Could not retrieve source list: %s", e)
            return None

    @property
    def extra_state_attributes(self):
        return {
            "websocket_connected": self.spotify_websocket and not self.spotify_websocket_task.done(),
            "last_update": str(self._last_update),
        }

    async def async_update(self, event=None):
        await self.ensure_websocket()
        self._state = self.spotify_websocket.response
        if self._state:
            try:                
                cluster = self._state["payloads"][0]["cluster"]
                player_state = cluster["player_state"]

                track = player_state["track"]
                self._track_id = track["uri"].split(":")[-1]
                response = await self.playback_instance.get_track_info(self._track_id)
                self._track_info = response["data"]["tracks"][0]

                self._track_name = self._track_info["name"]
                self._track_album_name = self._track_info["album"]["name"]
                self._media_image_url = self._track_info["album"]["images"][0]["url"]
                self._track_artist = self._track_info["artists"][0]["name"]

                self._current_position = int(player_state.get("position_as_of_timestamp")) / 1000
                self._media_duration = int(player_state.get("duration")) / 1000
                self._state = player_state["is_playing"] and not player_state["is_paused"]
                self._shuffle_state = player_state["options"]["shuffling_context"]

                self._repeating_context = player_state["options"]["repeating_context"]
                self._repeating_track = player_state["options"]["repeating_track"]

                self._track_number = player_state["index"]["track"]
                self._current_device_id = cluster["active_device_id"]
                current = cluster["devices"][self._current_device_id]
                self._volume = int(current.get("volume", 0)) / 65535
                self._is_muted = self._volume == 0
                self._devices = self.spotify_websocket._devices
                self._current_device = next((name for name, id_ in self._devices.items() if id_ == self._current_device_id), None)
                self._playlist = "https://open.spotify.com/playlist/" + player_state["context_uri"].split(":")[-1]

            except Exception as e:
                _LOGGER.error("Update Error: %s", e)

        self.async_write_ha_state()
