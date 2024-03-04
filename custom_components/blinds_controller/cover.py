from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(hass, entry)])

class BlindsCover(CoverEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._state = None  # Initialize _state attribute

    @property
    def unique_id(self):
        # Use the entry ID as the unique ID for this entity
        return self.entry.entry_id

    @property
    def name(self):
        # Use the "ent_name" from the configuration data as the name of this entity
        return self.entry.data["ent_name"]

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {
            "entity_up": self.entry.data["entity_up"],
            "entity_down": self.entry.data["entity_down"],
            "time_up": self.entry.data["time_up"],
            "time_down": self.entry.data["time_down"],
            "tilt_open": self.entry.data["tilt_open"],
            "tilt_closed": self.entry.data["tilt_closed"],
        }

    @property
    def is_closed(self):
        if self._state is None:
            return None
        return not self._state

    async def _async_handle_command(self, command):
        if command == 'open_cover':
            # If the cover is closing, stop it
            if self._state == False:
                await self.hass.services.async_call('homeassistant', 'turn_off', {
                    'entity_id': self.entry.data["entity_down"],
                }, False)
            await self.hass.services.async_call('homeassistant', 'turn_on', {
                'entity_id': self.entry.data["entity_up"],
            }, False)
            self._state = True

        elif command == 'close_cover':
            # If the cover is opening, stop it
            if self._state == True:
                await self.hass.services.async_call('homeassistant', 'turn_off', {
                    'entity_id': self.entry.data["entity_up"],
                }, False)
            await self.hass.services.async_call('homeassistant', 'turn_on', {
                'entity_id': self.entry.data["entity_down"],
            }, False)
            self._state = False

        elif command == 'stop_cover':
            await self.hass.services.async_call('homeassistant', 'turn_off', {
                'entity_id': self.entry.data["entity_up"],
            }, False)
            await self.hass.services.async_call('homeassistant', 'turn_off', {
                'entity_id': self.entry.data["entity_down"],
            }, False)
            self._state = None

        # Update state of entity
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        await self._async_handle_command('open_cover')

    async def async_close_cover(self, **kwargs):
        await self._async_handle_command('close_cover')

    async def async_stop_cover(self, **kwargs):
        await self._async_handle_command('stop_cover')