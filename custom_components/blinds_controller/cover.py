# Import necessary modules from Home Assistant
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from .calculator import TravelCalculator
from .calculator import TravelStatus

# Import the domain constant from the current package
from .const import DOMAIN

logger = logging.getLogger(__name__)

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
        self.hass.bus.async_listen('state_changed', self.handle_state_change)

        self.travel_calc = TravelCalculator(
            self.entry.data["time_down"],
            self.entry.data["time_up"],
        )
        if self._has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self.entry.data["tilt_closed"],
                self.entry.data["tilt_open"],
            )


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
    
    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if self.current_cover_position is not None:
            supported_features |= CoverEntityFeature.SET_POSITION

        if self._has_tilt_support():
            supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
            )
            if self.current_cover_tilt_position is not None:
                supported_features |= CoverEntityFeature.SET_TILT_POSITION

        return supported_features
    
    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.travel_calc.current_position()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt of the cover."""
        return self.tilt_calc.current_position()
        

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
    

    def _has_tilt_support(self):
        """Return True if the cover supports tilt, False otherwise."""
        return self.entry.data["tilt_open"] != 0 and self.entry.data["tilt_closed"] != 0

    # This method is called when the state of the up or down switch changes
    async def handle_state_change(self, event):
        """Handle a state change event from Home Assistant."""
        # If the entity that changed is the up or down switch, update the state and availability
        if event.data['entity_id'] in [self.entry.data["entity_up"], self.entry.data["entity_down"]]:
            # Get the new state of the entity
            new_state = event.data['new_state'].state

            if new_state == 'on':
                # If the up switch turned on, turn off the down switch
                if event.data['entity_id'] == self.entry.data["entity_up"]:
                    await self.hass.services.async_call('homeassistant', 'turn_off', {
                        'entity_id': self.entry.data["entity_down"],
                    }, False)
                # If the down switch turned on, turn off the up switch
                elif event.data['entity_id'] == self.entry.data["entity_down"]:
                    await self.hass.services.async_call('homeassistant', 'turn_off', {
                        'entity_id': self.entry.data["entity_up"],
                    }, False)

            await self.async_update()



    # This method handles commands to open, close, or stop the cover
    async def _async_handle_command(self, command):
        # Turn off both switches
        await self.hass.services.async_call('homeassistant', 'turn_off', {
            'entity_id': self.entry.data["entity_up"],
        }, False)
        await self.hass.services.async_call('homeassistant', 'turn_off', {
            'entity_id': self.entry.data["entity_down"],
        }, False)

        if command == 'open_cover':
            # Then turn on the up switch
            await self.hass.services.async_call('homeassistant', 'turn_on', {
                'entity_id': self.entry.data["entity_up"],
            }, False)
            self._state = True

        elif command == 'close_cover':
            # Then turn on the down switch
            await self.hass.services.async_call('homeassistant', 'turn_on', {
                'entity_id': self.entry.data["entity_down"],
            }, False)
            self._state = False

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