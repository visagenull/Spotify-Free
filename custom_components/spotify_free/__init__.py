"""Spotify Free integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["media_player"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the my_media_player component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up my_media_player from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "media_player")
    return True
