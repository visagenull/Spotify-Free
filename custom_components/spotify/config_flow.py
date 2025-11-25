from homeassistant import config_entries, exceptions
import voluptuous as vol
from .const import DOMAIN
from . import playback

DATA_SCHEMA = vol.Schema({
    vol.Required("sp_dc"): str,
    vol.Optional("name"): str,
})

async def validate_input(hass, data):
    sp_dc = data["sp_dc"]

    sp = playback.Spotify(sp_dc)
    access_token = await hass.async_add_executor_job(sp.get_access_token)

    if not access_token:
        raise InvalidCredentials

    user_profile = await sp.get_user_profile()



    if "name" in data:
        title = data["name"]
    else:
        title = data.get("name", user_profile["data"]["display_name"])

    return title, {"sp_dc": sp_dc}

class MyMediaPlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                title, data = await validate_input(self.hass, user_input)
                existing_entries = self.hass.config_entries.async_entries(DOMAIN)
                for entry in existing_entries:
                    if entry.title == title:
                        errors["base"] = "Already configured with this name"
                        return self.async_show_form(
                            step_id="user", data_schema=DATA_SCHEMA, errors=errors
                        )
                return self.async_create_entry(title=title, data=data)
            except InvalidCredentials:
                errors["base"] = "Invalid credentials"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        return await self.async_step_user(user_input=import_config)

class InvalidCredentials(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""