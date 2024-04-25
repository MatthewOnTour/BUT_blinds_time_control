from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
import re

from .const import DOMAIN


class BlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @callback
    def _get_entity_ids(self):
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
                    vol.Required("entity_up", default=None): vol.In(self._get_entity_ids()),
                    vol.Required("entity_down", default=None): vol.In(self._get_entity_ids()),
                    vol.Required("time_up"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("time_down"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_open"): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_closed"): vol.All(vol.Coerce(float), vol.Range(min=0)),

                    vol.Required("timed_control_down", default=False): bool,
                    vol.Optional("time_to_roll_down", default = "12:00"): vol.All(vol.Coerce(str)),
                    vol.Required("timed_control_up", default=False): bool,
                    vol.Optional("time_to_roll_up", default = "12:00"): vol.All(vol.Coerce(str)),

                    vol.Required("delay_control",default=False): bool,
                    vol.Optional("delay_sunrise",default=0): vol.All(vol.Coerce(int)),
                    vol.Optional("delay_sunset",default=0): vol.All(vol.Coerce(int)),

                    vol.Required("night_lights",default=False): bool,
                    vol.Optional("entity_night_lights", default=None): vol.Any(None, vol.In(self._get_entity_ids())),

                    vol.Required("tilting_day", default=False): bool,

                    vol.Required("protect_the_blinds", default=False): bool,
                    vol.Optional("wind_speed", default=30): vol.All(vol.Coerce(float)),
                    vol.Optional("wmo_code", default=80): vol.All(vol.Coerce(int)),

                    vol.Required("netamo_enable", default=False): bool,
                    vol.Optional("netamo_speed_entity", default=None): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_speed", default=30): vol.All(vol.Coerce(float)),
                    vol.Optional("netamo_gust_entity", default=None): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_gust", default=40): vol.All(vol.Coerce(float)),
                    vol.Optional("netamo_rain_entity", default=None): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_rain", default=40): vol.All(vol.Coerce(float)),


                    vol.Required("send_stop_at_end", default=True): bool
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BlindsOptionsFlow(config_entry)

class BlindsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    @callback
    def _get_entity_ids(self):
        return self.hass.states.async_entity_ids()

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            updated_data = dict(self.config_entry.data)
            updated_data.update(user_input)
            self.hass.config_entries.async_update_entry(entry=self.config_entry, data=updated_data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("ent_name", default=self.config_entry.data.get("ent_name", "")): str,
                    vol.Required("entity_up", default=self.config_entry.data.get("entity_up", "")): vol.In(self._get_entity_ids()),
                    vol.Required("entity_down", default=self.config_entry.data.get("entity_down", "")): vol.In(self._get_entity_ids()),
                    vol.Required("time_up", default=self.config_entry.data.get("time_up", 0.0)): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("time_down", default=self.config_entry.data.get("time_down", 0.0)): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_open", default=self.config_entry.data.get("tilt_open", 0.0)): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    vol.Required("tilt_closed", default=self.config_entry.data.get("tilt_closed", 0.0)): vol.All(vol.Coerce(float), vol.Range(min=0)),
                    
                    vol.Required("timed_control_down", default=self.config_entry.data.get("timed_control_down")): bool,
                    vol.Optional("time_to_roll_down", default=self.config_entry.data.get("time_to_roll_down", "")) : vol.All(vol.Coerce(str)),
                    vol.Required("timed_control_up", default=self.config_entry.data.get("timed_control_up")): bool,
                    vol.Optional("time_to_roll_up", default=self.config_entry.data.get("time_to_roll_up", "")) : vol.All(vol.Coerce(str)),

                    vol.Required("delay_control", default=self.config_entry.data.get("delay_control")): bool, 
                    vol.Optional("delay_sunrise", default=self.config_entry.data.get("delay_sunrise", 0)): vol.All(vol.Coerce(int)),
                    vol.Optional("delay_sunset", default=self.config_entry.data.get("delay_sunset", 0)): vol.All(vol.Coerce(int)),

                    vol.Required("night_lights", default=self.config_entry.data.get("night_lights")): bool, 
                    vol.Optional("entity_night_lights", default=self.config_entry.data.get("entity_night_lights")) : vol.Any(None, vol.In(self._get_entity_ids())),

                    vol.Required("tilting_day", default=self.config_entry.data.get("tilting_day")): bool,

                    vol.Required("protect_the_blinds", default=self.config_entry.data.get("protect_the_blinds")): bool,
                    vol.Optional("wind_speed", default=self.config_entry.data.get("wind_speed")): vol.All(vol.Coerce(float)),
                    vol.Optional("wmo_code", default=self.config_entry.data.get("wmo_code")): vol.All(vol.Coerce(int)),

                    vol.Required("netamo_enable", default=self.config_entry.data.get("netamo_enable")): bool,
                    vol.Optional("netamo_speed_entity", default=self.config_entry.data.get("netamo_speed_entity")): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_speed", default=self.config_entry.data.get("netamo_speed")): vol.All(vol.Coerce(float)),
                    vol.Optional("netamo_gust_entity", default=self.config_entry.data.get("netamo_gust_entity")): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_gust", default=self.config_entry.data.get("netamo_gust")): vol.All(vol.Coerce(float)),
                    vol.Optional("netamo_rain_entity", default=self.config_entry.data.get("netamo_rain_entity")): vol.Any(None, vol.In(self._get_entity_ids())),
                    vol.Optional("netamo_rain", default=self.config_entry.data.get("netamo_rain")): vol.All(vol.Coerce(float)),

                    vol.Required("send_stop_at_end", default=self.config_entry.data.get("send_stop_at_end")): bool,
                }
            ),
        )
