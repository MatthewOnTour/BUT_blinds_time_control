# Import necessary modules from Home Assistant
from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

# Import the domain constant from the current package
from .const import DOMAIN

# This function is called by Home Assistant to setup the component
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(hass, entry)])

# This class represents a cover entity in Home Assistant
class BlindsCover(CoverEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass    # The Home Assistant instance
        self.entry = entry  # The configuration entry
        self._state = None  # Initialize _state attribute
        self._available = True  # Initialize _available attribute

        # Listen for state changes of the up and down switches
        hass.bus.async_listen('state_changed', self.handle_state_change)


    # The unique ID of the entity is the ID of the configuration entry
    @property
    def unique_id(self):
        return self.entry.entry_id
    
    # The name of the entity is the "ent_name" from the configuration data
    @property
    def name(self):
        return self.entry.data["ent_name"]


    # The state attributes include various details about the cover (for testing perhaps)
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

    # The cover is considered closed if _state is False
    @property
    def is_closed(self):
        if self._state is None:
            return None
        return not self._state
    
    # The cover is considered moving if _state is True
    @property
    def is_moving(self):
        return self._state

    # The cover is available if _available is True
    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    # This method is called when the state of the up or down switch changes
    async def handle_state_change(self, event):
        """Handle a state change event from Home Assistant."""
        # If the entity that changed is the up or down switch, update the state and availability
        if event.data['entity_id'] in [self.entry.data["entity_up"], self.entry.data["entity_down"]]:
            await self.async_update()



    # This method handles commands to open, close, or stop the cover
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



    # These methods are called by Home Assistant to open, close, or stop the cover
    async def async_open_cover(self, **kwargs):
        await self._async_handle_command('open_cover')

    async def async_close_cover(self, **kwargs):
        await self._async_handle_command('close_cover')

    async def async_stop_cover(self, **kwargs):
        await self._async_handle_command('stop_cover')





    # This method updates the state of the cover based on the state of the up and down switches
    async def async_update(self):

        # Get the state of the up and down switches
        up_switch = self.hass.states.get(self.entry.data["entity_up"])
        down_switch = self.hass.states.get(self.entry.data["entity_down"])

        # If either switch is unavailable, the cover is unavailable
        if up_switch.state == 'unavailable' or down_switch.state == 'unavailable':
            self._available = False
        else:
            self._available = True

        # If both switches are off, the cover is stopped
        if up_switch.state == 'off' and down_switch.state == 'off':
            self._state = None
        # If the up switch is on, the cover is opening
        elif up_switch.state == 'on':
            self._state = True
        # If the down switch is on, the cover is closing
        elif down_switch.state == 'on':
            self._state = False

        # Update state of entity
        self.async_write_ha_state()