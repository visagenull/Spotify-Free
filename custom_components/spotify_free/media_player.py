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
        self._icon = "mdi:spotify"
        self._sp_dc = data.get("sp_dc")
        self._name = name
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
        self._data = None        
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

    """Media player controls"""

    async def async_media_pause(self):
        """Pause playback."""
        await self.playback_instance.pause(self._current_device_id)

    async def async_media_play(self):
        """Resume playback."""
        await self.playback_instance.resume(self._current_device_id)

    async def async_media_previous_track(self):
        """Skip to previous track."""
        await self.playback_instance.previous(self._current_device_id)

    async def async_media_next_track(self):
        """Skip to next track."""
        await self.playback_instance.next(self._current_device_id)

    async def async_media_seek(self, position):
        """Seek to position in seconds."""
        await self.playback_instance.seek(self._current_device_id, seek_ms=int(position * 1000))

    async def async_set_repeat(self, repeat):
        """Set repeat mode."""
        repeat_map = {
            "off": (False, False),
            "all": (True, False),
            "one": (False, True),
        }
        context, track = repeat_map.get(repeat, (False, False))
        await self.playback_instance.set_repeat(self._current_device_id, context, track)

    async def async_set_shuffle(self, shuffle):
        """Set shuffle mode."""
        await self.playback_instance.set_shuffle(self._current_device_id, shuffle)

    async def async_set_volume_level(self, volume):
        """Set the volume."""
        await self.playback_instance.volume(self._current_device_id, volume)

    async def async_mute_volume(self, mute):
        """Mute playback."""
        if self._is_muted:
            await self.playback_instance.volume(self._current_device_id, self._old_volume)
        else:
            self._old_volume = self._volume
            await self.playback_instance.volume(self._current_device_id, volume=0)

    async def async_select_source(self, source):
        """Select playback source."""
        await self.playback_instance.select_device(self._devices[source], self._control_device)

    """Media player properties"""

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
        return self._volume

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
        self._state = self.spotify_websocket.response
        if self._state:
            try:                
                cluster = self._state["payloads"][0]["cluster"]
                player_state = cluster["player_state"]
                track = player_state["track"]
                metadata = track["metadata"]
                self._track_name = metadata["title"]
                self._track_id = track["uri"].split(":")[-1]
                self._track_artist = "Unknown"
                self._track_album_name = metadata["album_title"]
                self._media_image_url = "https://i.scdn.co/image/" + metadata["image_large_url"].split(":")[-1]
                self._current_position = int(player_state.get("position_as_of_timestamp")) / 1000
                self._media_duration = int(player_state.get("duration")) / 1000
                self._state = player_state["is_playing"] and not player_state["is_paused"]
                self._shuffle_state = player_state["options"]["shuffling_context"]
                self._repeat_state = "context" if player_state["options"]["repeating_context"] else "off"
                self._track_number = player_state["index"]["track"]
                self._current_device_id = cluster["active_device_id"]
                current = cluster["devices"][self._current_device_id]
                self._volume = int(current.get("volume" , 0)) / 65535
                self._is_muted = self._volume == 0
                self._devices = self.spotify_websocket._devices
                self._current_device = next((name for name, id_ in self._devices.items() if id_ == self._current_device_id), None)
                self._playlist = "https://open.spotify.com/playlist/" + player_state["context_uri"].split(":")[-1]
            except Exception as e:
                _LOGGER.error("Update Error: %s", e)
        self.async_write_ha_state()
