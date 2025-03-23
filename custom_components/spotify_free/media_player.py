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
    CONF_HOST,
    CONF_PORT,
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
    """Set up the Spotify Free media player platform."""
    name = entry.title
    data = entry.data

    entity = SpotifyFree(name, data, hass)
    async_add_entities([entity])


class SpotifyFree(MediaPlayerEntity):
    def __init__(self, name, data, hass):
        self._name = name
        self._sp_dc = data.get("sp_dc")
        self.hass = hass

        self._current_playback = None
        self._track_name = None
        self._track_id = None
        self._track_artist = None
        self._track_album_name = None
        self._media_image_url = None
        self._current_position = None
        self._media_duration = None
        self._volume = 0
        self._is_muted = self._volume == 0
        self._state = None
        self._volume_level = None
        self._repeat_state = None
        self._shuffle_state = None
        self._current_device = None
        self._current_device_id = None
        self._devices = None
        self._control_device = None
        self._track_number = None
        self._playlist = None

        self._icon = "mdi:spotify"
        self.spotify_websocket = None
        self._devices = None

        asyncio.create_task(self.reconnect())

    async def async_added_to_hass(self):
        """Set up playback control and start websocket."""
        self.playback_instance = playback.Spotify(self._sp_dc)
        await self.websocket()

        self.hass.bus.async_listen("spotify_websocket_update", self.async_update)
        self.hass.bus.async_listen("spotify_websocket_restart", self.websocket)

        await self.async_update()

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {'entities': []}
        self.hass.data[DOMAIN]['entities'].append(self)

    async def reconnect(self):
        while True:
            await asyncio.sleep(3600)
            await self.websocket()

    async def websocket(self):
        """Set up and restart websocket."""
        if self.spotify_websocket:
            self.spotify_websocket_task.cancel()

        access_token = await self.playback_instance.get_access_token()
        self.spotify_websocket = websocket.SpotifyWebsocket(self.hass, access_token)
        self.spotify_websocket_task = self.hass.loop.create_task(self.spotify_websocket.spotify_websocket())

    async def async_media_pause(self):
        """Pause playback."""
        await self.playback_instance.pause(self._current_device_id)

    async def async_media_play(self):
        """Resume playback."""
        await self.playback_instance.resume(self._current_device_id)

    async def async_media_next_track(self):
        """Skip to next track."""
        await self.playback_instance.next()

    async def async_media_previous_track(self):
        """Skip to previous track."""
        await self.playback_instance.previous()

    async def async_set_volume_level(self, volume):
        """Set the volume."""
        await self.playback_instance.volume_percent(int(volume * 100))

    async def async_media_seek(self, position):
        """Seek to position in seconds."""
        await self.playback_instance.seek(int(position * 1000))

    async def async_set_repeat(self, repeat):
        """Set repeat mode."""
        repeat_map = {
            "one": "track",
            "all": "context",
            "off": "off",
        }
        await self.playback_instance.set_repeat(repeat_map.get(repeat, "off"))

    async def async_set_shuffle(self, shuffle):
        """Set shuffle mode."""
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
        await self.playback_instance.select_device(self._devices[source], self._control_device)

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
        if self._state is None:
            return STATE_OFF
        return STATE_PLAYING if self._state else STATE_PAUSED

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
    def media_playlist(self):
        """Current playing playlist."""
        return getattr(self, '_playlist', None)

    @property
    def media_image_url(self):
        """Album cover of current playing media."""
        return self._media_image_url

    @property
    def media_track(self):
        """Track number of current playing media."""
        return self._track_number if hasattr(self, '_playlist') else None

    @property
    def media_duration(self):
        """Duration of current playing media."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._state in [True, False]:
            self._last_update = dt_util.utcnow()
            return self._current_position
        return None

    @property
    def media_position_updated_at(self):
        """When the position of the current playing media was valid."""
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
        repeat_map = {
            "context": "all",
            "track": "one",
            "off": "off"
        }
        return repeat_map.get(self._repeat_state, "off")

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
        return self._current_device

    @property
    def source_list(self):
        """List of available devices."""
        try:
            device_names = [key for key in self._devices if 'hobs' not in key]
            return device_names
        except:
            return None

    async def async_update(self, event=None):
        """Retrieve latest state."""
        self._current_playback = await self.playback_instance.get_playback_status()
        if self._current_playback:
            try:
                self._current_playback = self._current_playback["data"]
                self._track_name = self._current_playback["item"].get("name")
                self._track_id = self._current_playback["item"].get("id")
                self._track_artist = ", ".join(artist["name"] for artist in self._current_playback["item"].get("artists", []))
                self._track_album_name = self._current_playback["item"]["album"].get("name")
                self._media_image_url = self._current_playback["item"]["album"]["images"][0].get("url")
                self._current_position = int(self._current_playback.get("progress_ms", 0)) / 1000
                self._media_duration = int(self._current_playback["item"].get("duration_ms", 0)) / 1000
                self._volume = self._current_playback["device"].get("volume_percent")
                self._is_muted = self._volume == 0
                self._state = self._current_playback.get("is_playing")
                self._volume_level = int(self._current_playback['device'].get('volume_percent', 0)) / 100
                self._repeat_state = self._current_playback.get("repeat_state")
                self._shuffle_state = self._current_playback.get("shuffle_state")
                self._current_device = self._current_playback["device"].get("name")
                self._current_device_id = self._current_playback["device"].get("id")
                self._devices = self.spotify_websocket._devices
                self._control_device = self.spotify_websocket.device_id
                self._track_number = self._current_playback["item"].get("track_number")
                self._playlist = self._current_playback["context"].get("external_urls", {}).get("spotify")
            except Exception as e:
                _LOGGER.error("Update Error: %s", e)
        self.async_write_ha_state()
