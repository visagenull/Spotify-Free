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
    def __init__(self, name: str, data, hass):

        self.__icon = "mdi:spotify"
        self.__sp_dc = data.get("sp_dc")
        self.__name = name
        self.__hass = hass
        self.__track_info = None
        self.__current_playback = None
        self.__track_name = None
        self.__track_id = None
        self.__track_artist = None
        self.__track_album_name = None
        self.__media_image_url = None
        self.__current_position = None
        self.__media_duration = None
        self.__volume = 0
        self.__is_muted = False
        self.__state = None
        self.__repeat_state = None
        self.__shuffle_state = None
        self.__current_device = None
        self.__current_device_id = None
        self.__control_device = None
        self.__track_number = None
        self.__playlist = None       
        self.__spotify_websocket = None
        self.__devices = None
        self.__last_update = "1970-01-01T00:00:00+00:00"
        self.__metadata = None
        self.__repeating_context = False
        self.__repeating_track = False
        self.__player_state = None

        asyncio.create_task(self.reconnect())



    async def async_added_to_hass(self):
        self.__playback_instance = await playback.Playback.create(self.__sp_dc)

        await self.__websocket()
        await self.async_update()

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {'entities': []}
        self.hass.data[DOMAIN]['entities'].append(self)


    async def reconnect(self):
        while True:
            try:
                await asyncio.sleep(3600)
                await self.__websocket()
            except Exception as e:
                _LOGGER.error("WebSocket reconnect failed: %s", e)
                await asyncio.sleep(30)


    async def __ensure_websocket(self):
        if not self.__spotify_websocket:
            _LOGGER.warning("WebSocket disconnected. Attempting to reconnect.")
            await self.__websocket()


    async def __update(self):
        self.__last_update = dt_util.utcnow()
        await self.async_update()


    async def __websocket(self):
        access_token = await self.__playback_instance.refresh_token()

        self.__spotify_websocket = websocket.SpotifyWebsocket(access_token)
        await self.__spotify_websocket.register_callback(self.__update)

        asyncio.create_task(self.__spotify_websocket.start_websocket())
        await self.async_update()




    async def async_media_pause(self):
        await self.__ensure_websocket()
        await self.__playback_instance.pause()

    async def async_media_play(self):
        await self.__ensure_websocket()
        await self.__playback_instance.resume()

    async def async_media_previous_track(self):
        await self.__ensure_websocket()
        await self.__playback_instance.previous()

    async def async_media_next_track(self):
        await self.__ensure_websocket()
        await self.__playback_instance.next()

    async def async_media_seek(self, position):
        await self.__ensure_websocket()
        await self.__playback_instance.seek(seek_ms=int(position * 1000))

    async def async_set_repeat(self, repeat):
        await self.__ensure_websocket()
        repeat_map = {
            "off": (False, False),
            "all": (True, False),
            "one": (True, True),
        }
        context, track = repeat_map.get(repeat, (False, False))
        await self.__playback_instance.set_repeat(context, track)

    async def async_set_shuffle(self, shuffle):
        await self.__ensure_websocket()
        await self.__playback_instance.set_shuffle(shuffle)

    async def async_set_volume_level(self, volume):
        await self.__ensure_websocket()
        await self.__playback_instance.volume(volume)

    async def async_mute_volume(self, mute):
        await self.__ensure_websocket()
        if self.__is_muted:
            await self.__playback_instance.volume(self.__old_volume)
        else:
            self.__old_volume = self.__volume
            await self.__playback_instance.volume(level=0)

    async def async_select_source(self, source):
        await self.__ensure_websocket()
        await self.__playback_instance.select_device(self.__devices[source])

    @property
    def name(self):
        return self.__name

    @property
    def supported_features(self):
        return SUPPORT_SPOTIFY_FREE

    @property
    def state(self):
        if self.__state is None:
            return STATE_OFF
        return STATE_PLAYING if self.__state else STATE_PAUSED

    @property
    def media_title(self):
        return self.__track_name

    @property
    def media_artist(self):
        return self.__track_artist

    @property
    def media_album_name(self):
        return self.__track_album_name

    @property
    def media_playlist(self):
        return self.__playlist

    @property
    def media_image_url(self):
        return self.__media_image_url

    @property
    def media_track(self):
        return self.__track_number if hasattr(self, '_playlist') else None

    @property
    def media_duration(self):
        return self.__media_duration

    @property
    def media_position(self):
        if self.__state in [True, False]:
            return self.__current_position
        return None

    @property
    def media_position_updated_at(self):
        return self.__last_update

    @property
    def volume_level(self):
        return self.__volume

    @property
    def is_volume_muted(self):
        return self.__is_muted

    @property
    def repeat(self):
        repeat_map = {
            (False, False): "off",
            (True, False): "all",
            (True, True): "one",
        }
        return repeat_map.get((self.__repeating_context, self.__repeating_track), "off")

    @property
    def shuffle(self):
        return self.__shuffle_state

    @property
    def icon(self):
        return self.__icon

    @property
    def source(self):
        return self.__current_device

    @property
    def source_list(self):
        if not self.__devices:
            return None
        try:
            return [key for key in self.__devices if 'hobs' not in key]
        except Exception as e:
            _LOGGER.warning("Could not retrieve source list: %s", e)
            return None

    async def async_update(self, event=None):
        await self.__ensure_websocket()
        self.__state = self.__spotify_websocket.response
        if self.__state:
            try:                
                cluster = self.__state.get("payloads", [{}])[0].get("cluster", {})
                self.__player_state = cluster.get("player_state", {})

                self.__track = self.__player_state.get("track", {})
                self.__track_id = self.__track.get("uri", "").split(":")[-1]
                self.__metadata = self.__track.get("metadata", {})
                self.__media_image_url = f"https://i.scdn.co/image/{self.__metadata.get("image_xlarge_url", {}).split(":")[-1]}"
                self.__track_name = self.__metadata.get("title", "")
                self.__track_album_name = self.__metadata.get("album_title", "")
                self.__track_artist = self.__metadata.get("artist_uri", "").split(":")[-1]
                self.__current_position = int(self.__player_state.get("position_as_of_timestamp", 0)) / 1000
                self.__media_duration = int(self.__player_state.get("duration", 0)) / 1000
                self.__state = self.__player_state.get("is_playing", False) and not self.__player_state.get("is_paused", True)
                options = self.__player_state.get("options", {})
                self.__shuffle_state = options.get("shuffling_context", False)
                self.__repeating_context = options.get("repeating_context", False)
                self.__repeating_track = options.get("repeating_track", False)
                index = self.__player_state.get("index", {})
                self.__track_number = index.get("track", 0)
                self.__current_device_id = cluster.get("active_device_id", "")
                self.__playback_instance.device_id = self.__current_device_id
                devices = cluster.get("devices", {})
                current = devices.get(self.__current_device_id, {})
                self.__volume = int(current.get("volume", 0)) / 65535
                self.__is_muted = self.__volume == 0
                self.__devices = self.__spotify_websocket.devices
                self.__current_device = next(
                    (name for name, id_ in self.__devices.items() if id_ == self.__current_device_id),
                    None
                )
                _LOGGER.error(self.__player_state.get("context_uri", ""))
                self.__playlist = f"https://open.spotify.com/playlist/{self.__player_state.get("context_uri", "").split(":")[-1]}"
                
                
                


            except Exception as e:
                _LOGGER.error("Update Error: %s", e)

        self.async_write_ha_state()
