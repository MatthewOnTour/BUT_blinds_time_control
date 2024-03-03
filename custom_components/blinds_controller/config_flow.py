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

    async def async_get_options_flow(self):
        return OptionsFlowHandler(self)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_flow):
        self.config_flow = config_flow

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional("ent_name", default=self.config_flow.config_entry.options.get("ent_name")): str,
                vol.Optional("entity_up", default=self.config_flow.config_entry.options.get("entity_up")): vol.In(self.config_flow._get_entity_ids()),
                vol.Optional("entity_down", default=self.config_flow.config_entry.options.get("entity_down")): vol.In(self.config_flow._get_entity_ids()),
                vol.Optional("time_up", default=self.config_flow.config_entry.options.get("time_up")): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional("time_down", default=self.config_flow.config_entry.options.get("time_down")): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional("tilt_open", default=self.config_flow.config_entry.options.get("tilt_open")): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional("tilt_closed", default=self.config_flow.config_entry.options.get("tilt_closed")): vol.All(vol.Coerce(int), vol.Range(min=0)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)