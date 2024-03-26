# Import necessary modules from Home Assistant
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
# Import the domain constant from the current package
from .const import DOMAIN

# Define the configuration flow for the blinds
class BlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    # Callback to get the list of entity IDs
    @callback
    def _get_entity_ids(self):
        # Fetch the list of entity IDs
        return self.hass.states.async_entity_ids()

    # Step for user input
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # If user input is not None, create a new entry
            return self.async_create_entry(
                title=user_input["ent_name"],
                data=user_input,
            )
        # Show the form for user input
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name"): str,
                    vol.Required("entity_up"): vol.In(self._get_entity_ids()),
                    vol.Required("entity_down"): vol.In(self._get_entity_ids()),
                    vol.Required("time_up"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("time_down"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_open"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_closed"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                }
            ),
            errors=errors,
        )

    # Get the options flow for this entry
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BlindsOptionsFlow(config_entry)


# Define the options flow for the blinds
class BlindsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    # Callback to get the list of entity IDs
    @callback
    def _get_entity_ids(self):
        # Fetch the list of entity IDs
        return self.hass.states.async_entity_ids()

    # Step for user input
    async def async_step_init(self, user_input=None):
        # If user input is not None, update the entry
        if user_input is not None:
            updated_data = dict(self.config_entry.data)  # Create a mutable copy
            updated_data.update(user_input)  # Update the copy with the new data
            self.hass.config_entries.async_update_entry(entry=self.config_entry, data=updated_data)  # Update the entry
            return self.async_create_entry(title="", data={})  # Return to the options menu

        # Show the form for user input
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name", default=self.config_entry.data.get("ent_name")): str,
                    vol.Required("entity_up", default=self.config_entry.data.get("entity_up")): vol.In(self._get_entity_ids()),
                    vol.Required("entity_down", default=self.config_entry.data.get("entity_down")): vol.In(self._get_entity_ids()),
                    vol.Required("time_up", default=self.config_entry.data.get("time_up")): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("time_down", default=self.config_entry.data.get("time_down")): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_open", default=self.config_entry.data.get("tilt_open")): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_closed", default=self.config_entry.data.get("tilt_closed")): vol.All(vol.Coerce(float), vol.Range(min=0)),
                }
            ),
        )