from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN

class BlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate user input here and proceed to next step if valid
            # If invalid, add error messages to `errors` dict
            return self.async_create_entry(
                title=user_input["ent_name"],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name"): str,
                    vol.Required("entity_up"): str,
                    vol.Required("entity_down"): str,
                    vol.Required("time_up"): int,
                    vol.Required("time_down"): int,
                    vol.Required("tilt_open"): int,
                    vol.Required("tilt_closed"): int,
                }
            ),
            errors=errors,
        )

    async def async_step_abort(self, user_input=None):
        # Handle abort step here
        pass

    async def async_step_error(self, user_input=None):
        # Handle error step here
        pass