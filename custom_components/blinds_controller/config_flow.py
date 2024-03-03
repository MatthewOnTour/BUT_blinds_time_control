from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN

class BlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @callback
    def _get_entity_ids(self):
        # Fetch the list of entity IDs
        return self.hass.states.async_entity_ids()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["ent_name"],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name"): str,
                    vol.Required("entity_up"): vol.In(self._get_entity_ids()),
                    vol.Required("entity_down"): vol.In(self._get_entity_ids()),
                    vol.Required("time_up"): vol.All(vol.Coerce(int), vol.Range(min=0)),
                    vol.Required("time_down"): vol.All(vol.Coerce(int), vol.Range(min=0)),
                    vol.Required("tilt_open"): vol.All(vol.Coerce(int), vol.Range(min=0)),
                    vol.Required("tilt_closed"): vol.All(vol.Coerce(int), vol.Range(min=0)),
                }
            ),
            errors=errors,
        )
