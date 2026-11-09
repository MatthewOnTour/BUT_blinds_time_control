"""Config flow for Blinds Controller integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN


class BlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blinds Controller."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return BlindsOptionsFlow(config_entry)

    @callback
    def _get_entity_ids(self, platform="switch"):
        """Return a sorted list of entity IDs for a given platform."""
        return sorted(self.hass.states.async_entity_ids(platform))

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["ent_name"],
                data=user_input,
            )

        all_switches = self._get_entity_ids("switch")
        if not all_switches:
            errors["base"] = "no_switches"

        switch_validator = vol.In(all_switches) if all_switches else str

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name"): str,
                    vol.Required("entity_up"): switch_validator,
                    vol.Required("entity_down"): switch_validator,
                    vol.Required("time_up", default=30.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.1)
                    ),
                    vol.Required("time_down", default=30.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.1)
                    ),
                    vol.Optional("dead_time", default=0.78): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=5.0)
                    ),
                    vol.Optional("stop_delay", default=0.15): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                    ),
                    vol.Optional("sperrzeit", default=0.2): vol.All(
                        vol.Coerce(float), vol.Range(min=0.01, max=3.0)
                    ),
                    vol.Optional("overtravel_time", default=1.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=5.0)
                    ),
                    vol.Optional("interlock_delay", default=0.2): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=2.0)
                    ),
                    vol.Optional("tilt_open", default=0.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0)
                    ),
                    vol.Optional("tilt_closed", default=0.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0)
                    ),
                    vol.Optional("send_stop_at_end", default=True): bool,
                }
            ),
            errors=errors,
        )


class BlindsOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Blinds Controller."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    @callback
    def _get_entity_ids(self, platform="switch"):
        """Return a sorted list of entity IDs for a given platform."""
        return sorted(self.hass.states.async_entity_ids(platform))

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        all_switches = self._get_entity_ids("switch")
        data = self.config_entry.data
        options = self.config_entry.options

        def get_val(key, default):
            return options.get(key, data.get(key, default))

        up_default = get_val("entity_up", "")
        down_default = get_val("entity_down", "")

        up_validator = vol.In(all_switches) if (all_switches and up_default in all_switches) else str
        down_validator = vol.In(all_switches) if (all_switches and down_default in all_switches) else str

        dead_time_val = float(get_val("dead_time", get_val("startup_delay", 0.78)))
        stop_delay_val = float(get_val("stop_delay", 0.15))
        sperrzeit_val = float(get_val("sperrzeit", get_val("pulse_duration", 0.2)))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name", default=get_val("ent_name", "Blinds")): str,
                    vol.Required("entity_up", default=up_default): up_validator,
                    vol.Required("entity_down", default=down_default): down_validator,
                    vol.Required("time_up", default=float(get_val("time_up", 30.0))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.1)
                    ),
                    vol.Required("time_down", default=float(get_val("time_down", 30.0))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.1)
                    ),
                    vol.Optional("dead_time", default=dead_time_val): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=5.0)
                    ),
                    vol.Optional("stop_delay", default=stop_delay_val): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                    ),
                    vol.Optional("sperrzeit", default=sperrzeit_val): vol.All(
                        vol.Coerce(float), vol.Range(min=0.01, max=3.0)
                    ),
                    vol.Optional("overtravel_time", default=float(get_val("overtravel_time", 1.0))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=5.0)
                    ),
                    vol.Optional("interlock_delay", default=float(get_val("interlock_delay", 0.2))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0, max=2.0)
                    ),
                    vol.Optional("tilt_open", default=float(get_val("tilt_open", 0.0))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0)
                    ),
                    vol.Optional("tilt_closed", default=float(get_val("tilt_closed", 0.0))): vol.All(
                        vol.Coerce(float), vol.Range(min=0.0)
                    ),
                    vol.Optional("send_stop_at_end", default=bool(get_val("send_stop_at_end", True))): bool,
                }
            ),
        )
