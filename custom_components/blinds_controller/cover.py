# Import necessary modules from Home Assistant
from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from xknx.devices import TravelStatus # Experimental
from xknx.devices import TravelCalculator # Experimental
from homeassistant.helpers import config_validation as cv
# RestoreEntity is used to restore the state of the entity after a restart
from homeassistant.helpers.restore_state import RestoreEntity
from datetime import timedelta
import voluptuous as vol
# Used to schedule callbacks for specific time events
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_utc_time_change,
    async_track_time_interval,
)

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_DEVICE_CLASS,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)

POSITION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_POSITION): cv.positive_int,
    }
)
TILT_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_TILT_POSITION): cv.positive_int,
    }
)


SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_TILT_POSITION = "set_known_tilt_position"

# Import the domain constant from the current package
from .const import DOMAIN


# This function is called by Home Assistant to setup the component
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(hass, entry)])

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION, POSITION_SCHEMA, "set_known_position"
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_TILT_POSITION, TILT_POSITION_SCHEMA, "set_known_tilt_position"
    )

# This class represents a cover entity in Home Assistant

class BlindsCover(CoverEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass    # The Home Assistant instance
        self.entry = entry  # The configuration entry
        self._state = None  # Initialize _state attribute
        self._available = True  # Initialize _available attribute
        # Listen for state changes of the up and down switches
        self.hass.bus.async_listen('state_changed', self.handle_state_change)

        self._travel_time_down = self.entry.data["time_down"]
        self._travel_time_up = self.entry.data["time_up"]
        self._tilting_time_down = self.entry.data["tilt_closed"]	
        self._tilting_time_up = self.entry.data["tilt_open"]

        self.travel_calc = TravelCalculator(
            self._travel_time_down,
            self._travel_time_up,
        )
        if self._has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self._tilting_time_down,
                self._tilting_time_up,
            )

    

    def _has_tilt_support(self):
        """Return if cover has tilt support."""
        return self._tilting_time_down is not None and self._tilting_time_up is not None
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
    
    async def async_added_to_hass(self):
        """ Only cover position and confidence in that matters."""
        """ The rest is calculated from this attribute.        """
        old_state = await self.async_get_last_state()
        if (
            old_state is not None
            and self.travel_calc is not None
            and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            self.travel_calc.set_position(
                int(old_state.attributes.get(ATTR_CURRENT_POSITION))
            )

            if (
                self._has_tilt_support()
                and old_state.attributes.get(ATTR_CURRENT_TILT_POSITION) is not None
            ):
                self.tilt_calc.set_position(
                    int(old_state.attributes.get(ATTR_CURRENT_TILT_POSITION))
                )

    def _handle_stop(self):
        if self.travel_calc.is_traveling():
            self.travel_calc.stop()
            self.stop_auto_updater()

        if self.tilt_calc.is_traveling():
            self.tilt_calc.stop()
            self.stop_auto_updater()

    # The cover is considered closed if _state is False
    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        from xknx.devices import TravelStatus

        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_DOWN
        ) or (
            self._has_tilt_support()
            and self.tilt_calc.is_traveling()
            and self.tilt_calc.travel_direction == TravelStatus.DIRECTION_DOWN
        )
    
    # The cover is considered moving if _state is True
    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_UP
        ) or (
            self._has_tilt_support()
            and self.tilt_calc.is_traveling()
            and self.tilt_calc.travel_direction == TravelStatus.DIRECTION_UP
        )
    
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
    def is_closed(self):
        """Return if the cover is closed."""
        return self.travel_calc.is_closed()

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    # The cover is available if _available is True
    @property
    def available(self):
        """Return True if entity is available."""
        return self._available
    
    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.travel_calc.current_position()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt of the cover."""
        return self.tilt_calc.current_position()

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