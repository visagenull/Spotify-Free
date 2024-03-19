from homeassistant.components.media_player import (
    MediaPlayerEntity,
    PLATFORM_SCHEMA,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.const import CONF_HOST, CONF_PORT
import voluptuous as vol
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, STATE_OFF, STATE_UNKNOWN
import homeassistant.util.dt as dt_util

import logging
import json

from .const import DOMAIN
from . import playback
from . import websocket

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

    async_add_entities([SpotifyFree(name, data, hass)])

class SpotifyFree(MediaPlayerEntity):
    def __init__(self, name, data, hass):
        self._sp_dc = data.get("sp_dc")
        self._name = name
        self._last_update = None
        self._icon = "mdi:spotify"
        self.hass = hass
        self._track_name = None
        self._track_artist = None
        self._track_album_name = None
        self._media_image_url = None
        self._current_position = None
        self._media_duration = None
        self._volume = None
        self._is_muted = False
        self._state = None
        self._volume_level = None
        self._shuffle_state = False
        self._repeat_state = False
        self._old_volume = None
        self._devices = {}
        self._source = None
        self._spotify_websocket = None
        self._control_device = None
        self._sources = {}

    async def async_added_to_hass(self):
        self.playback_instance = playback.Spotify(self._sp_dc)
        self._access_token= await self.playback_instance.get_access_token()
        self.spotify_websocket = websocket.SpotifyWebsocket(self.hass, self._access_token)
        self.hass.loop.create_task(self.spotify_websocket.spotify_websocket())
        self.hass.bus.async_listen("spotify_websocket_update", self.async_update)
        self.hass.bus.async_listen("spotify_websocket_restart", self.async_added_to_hass)

    async def async_media_pause(self):
        """Pause playback."""
        await self.playback_instance.pause()

    async def async_media_play(self):
        """Resume playback."""
        await self.playback_instance.resume()

    async def async_media_next_track(self):
        """Skip to next track."""
        await self.playback_instance.next()

    async def async_media_previous_track(self):
        """Skip to previos track."""
        await self.playback_instance.previous()

    async def async_set_volume_level(self, volume):
        """Set the volume."""
        await self.playback_instance.volume_percent(int(volume * 100))

    async def async_media_seek(self, position):
        """Seek to position in seconds."""
        await self.playback_instance.seek(int(position * 1000))

    async def async_set_repeat(self, repeat):
        """Set repeat mode. off/all/one"""
        if repeat == "one":
            await self.playback_instance.set_repeat("track")
        if repeat == "all":
            await self.playback_instance.set_repeat("context")
        else:
           await self.playback_instance.set_repeat("off")

    async def async_set_shuffle(self, shuffle):
        """Set shuffle mode boolean."""
        await self.playback_instance.set_shuffle(shuffle)

    async def async_mute_volume(self, mute):
        """Mute playback."""
        if self._is_muted:
            await self.playback_instance.volume_percent(self._old_volume)
        else:
            self._old_volume = self._volume
            await self.playback_instance.volume_percent(0)

    async def async_select_source(self, source):
        """Select playback source."""
        await self.playback_instance.select_device(self._sources[source]["device_id"], self._control_device)

    @property
    def name(self):
        """Return the name of the player."""
        return self._name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SPOTIFY_FREE

    @property
    def state(self):
        """Return the state of the player."""
        if self._state == True:
            return STATE_PLAYING
        elif self._state == False:
            return STATE_PAUSED

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_name

    @property
    def media_artist(self):
        """Artist of current playing media."""
        return self._track_artist

    @property
    def media_album_name(self):
        """Album name of current playing media."""
        return self._track_album_name

    @property
    def media_image_url(self):
        """Album cover of current playing media."""
        return self._media_image_url

    @property
    def media_duration(self):
        """Duration of current playing media."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._state == True or self._state == False:
            self._last_update = dt_util.utcnow()
            return self._current_position
        return None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid. Returns value from homeassistant.util.dt.utcnow()."""
        return self._last_update

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_muted

    @property
    def repeat(self):
        """Current repeat state."""
        if self._repeat_state == "context":
            return "all"
        if self._repeat_state == "track":
            return "one"
        else:
            return "off"

    @property
    def shuffle(self):
        """Boolean if currently shuffling."""
        return self._shuffle_state

    @property
    def icon(self):
        """Icon for media player."""
        return self._icon

    @property
    def source(self):
        """Current device."""
        return self._source

    @property
    def source_list(self):
        """List of available sources."""

        devices = {}
        sources = []
        if self._devices:
            for device_id, device_data in self._devices.items():
                display_name = None
                        
                if 'device_aliases' in device_data:
                    for alias_data in device_data['device_aliases'].values():
                        if 'display_name' in alias_data:
                            display_name = alias_data['display_name']
                            break

                if not display_name:
                    display_name = device_data['name']
                    
                # Check if device_id is present in device_data, otherwise set it to None
                device_id = device_data.get('device_id')
                            
                devices[display_name] = {'device_id': device_id}
                self._sources = devices

            for device_name, device_info in devices.items():
                sources.append(device_name)
            return sources


    async def async_update(self, event=None):
        self._current_playback = await self.playback_instance.get_playback_status()
        if self._current_playback:
            self._current_playback = self._current_playback["data"]

            self._track_name = self._current_playback["item"]["name"]
            self._track_artist = ", ".join(artist["name"] for artist in self._current_playback["item"]["artists"])
            self._track_album_name = self._current_playback["item"]["album"]["name"]
            self._media_image_url = self._current_playback["item"]["album"]["images"][0]["url"]
            self._current_position = int(self._current_playback["progress_ms"]) / 1000
            self._media_duration = int(self._current_playback["item"]["duration_ms"]) / 1000
            self._volume = self._current_playback["device"]["volume_percent"]
            self._is_muted = self._volume == 0
            self._state = self._current_playback["is_playing"]
            self._volume_level = int(self._current_playback['device']['volume_percent']) / 100
            self._repeat_state = self._current_playback["repeat_state"]
            self._shuffle_state = self._current_playback["shuffle_state"]
            self._source = self._current_playback["device"]["name"]
            self._support_volme = self._current_playback["device"]["supports_volume"]
            self._devices = await self.spotify_websocket.get_devices()
            self._control_device = await self.spotify_websocket.get_device_id()
            self.async_write_ha_state()
