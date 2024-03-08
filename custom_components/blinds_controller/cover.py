# Import the domain constant from the current package
from .const import DOMAIN
# Import necessary modules from Home Assistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_utc_time_change,
    async_track_time_interval,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from datetime import timedelta
import voluptuous as vol
from xknx.devices import TravelStatus
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

CONF_DEVICES = "devices"
CONF_TRAVELLING_TIME_DOWN = "time_down"
CONF_TRAVELLING_TIME_UP = "time_up"
CONF_TILTING_TIME_CLOSED = "tilt_closed"
CONF_TILTING_TIME_OPEN = "tilt_open"
DEFAULT_TRAVEL_TIME = 30

CONF_OPEN_SWITCH_ENTITY_ID = "entity_up"
CONF_CLOSE_SWITCH_ENTITY_ID = "entity_down"

SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_TILT_POSITION = "set_known_tilt_position"

# This function is called by Home Assistant to setup the component
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(hass, entry)])

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the cover platform."""

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION, "set_known_position"
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_TILT_POSITION,  "set_known_tilt_position"
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
        self._travel_time_down = self.entry.data.get(CONF_TRAVELLING_TIME_DOWN)
        self._travel_time_up = self.entry.data.get(CONF_TRAVELLING_TIME_UP)
        self._tilting_time_down = self.entry.data.get(CONF_TILTING_TIME_CLOSED)
        self._tilting_time_up = self.entry.data.get(CONF_TILTING_TIME_OPEN)
        self._open_switch_entity_id = self.entry.data.get(CONF_OPEN_SWITCH_ENTITY_ID)
        self._close_switch_entity_id = self.entry.data.get(CONF_CLOSE_SWITCH_ENTITY_ID)
        
        from xknx.devices import TravelCalculator

        self._unsubscribe_auto_updater = None

        self.travel_calc = TravelCalculator(
            self._travel_time_down,
            self._travel_time_up,
        )
        if self._has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self._tilting_time_down,
                self._tilting_time_up,
            )
    async def async_added_to_hass(self):
        """Only cover's position and tilt matters."""
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
        """Handle stop"""
        if self.travel_calc.is_traveling():
            self.travel_calc.stop()
            self.stop_auto_updater()

        if self.tilt_calc.is_traveling():
            self.tilt_calc.stop()
            self.stop_auto_updater()

    # The unique ID of the entity is the ID of the configuration entry
    @property
    def unique_id(self):
        return self.entry.entry_id
    
    # The name of the entity is the "ent_name" from the configuration data
    @property
    def name(self):
        return self.entry.data["ent_name"]

    @property
    def device_class(self):
        """Return the device class of the cover."""
        return None


    # The state attributes include various details about the cover (for testing perhaps)
    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up
        attr[CONF_TILTING_TIME_CLOSED] = self._tilting_time_down
        attr[CONF_TILTING_TIME_OPEN] = self._tilting_time_up
        attr[CONF_OPEN_SWITCH_ENTITY_ID] = self._open_switch_entity_id
        attr[CONF_CLOSE_SWITCH_ENTITY_ID] = self._close_switch_entity_id
        return attr

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.travel_calc.current_position()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt of the cover."""
        return self.tilt_calc.current_position()

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
    def is_closed(self):
        """Return if the cover is closed."""
        return self.travel_calc.is_closed()
    
    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True
    

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
    

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self.set_position(position)


    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if ATTR_TILT_POSITION in kwargs:
            position = kwargs[ATTR_TILT_POSITION]
            await self.set_tilt_position(position)

    async def async_close_cover(self, **kwargs):
        """Turn the device close."""
        if self.travel_calc.current_position() > 0:
            self.travel_calc.start_travel_down()
            self.start_auto_updater()
            self._update_tilt_before_travel(SERVICE_CLOSE_COVER)
            await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs):
        """Turn the device open."""
        if self.travel_calc.current_position() < 100:
            self.travel_calc.start_travel_up()
            self.start_auto_updater()
            self._update_tilt_before_travel(SERVICE_OPEN_COVER)
            await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_close_cover_tilt(self, **kwargs):
        """Turn the device close."""
        if self.tilt_calc.current_position() > 0:
            self.tilt_calc.start_travel_down()
            self.start_auto_updater()
            await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover_tilt(self, **kwargs):
        """Turn the device open."""
        if self.tilt_calc.current_position() < 100:
            self.tilt_calc.start_travel_up()
            self.start_auto_updater()
            await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        self._handle_stop()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_position(self, position):
        """Move cover to a designated position."""
        current_position = self.travel_calc.current_position()
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            self.travel_calc.start_travel(position)
            self._update_tilt_before_travel(command)
            await self._async_handle_command(command)
        return

    async def set_tilt_position(self, position):
        """Move cover tilt to a designated position."""
        current_position = self.tilt_calc.current_position()
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            self.tilt_calc.start_travel(position)
            await self._async_handle_command(command)
        return

    def start_auto_updater(self):
        """Start the autoupdater to update HASS while cover is moving."""
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        self.async_schedule_update_ha_state()
        if self.position_reached():
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        """Return if cover has reached its final position."""
        return self.travel_calc.position_reached() and (
            not self._has_tilt_support() or self.tilt_calc.position_reached()
        )
    
    def _update_tilt_before_travel(self, command):
        """Updating tilt before travel."""
        if self._has_tilt_support():
            if command == SERVICE_OPEN_COVER:
                self.tilt_calc.set_position(100)
            elif command == SERVICE_CLOSE_COVER:
                self.tilt_calc.set_position(0)

    async def auto_stop_if_necessary(self):
        """Do auto stop if necessary."""
        if self.position_reached():
            self.travel_calc.stop()
            if self._has_tilt_support():
                self.tilt_calc.stop()
            await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_known_position(self, **kwargs):
        """We want to do a few things when we get a position"""
        position = kwargs[ATTR_POSITION]
        self._handle_stop()
        await self._async_handle_command(SERVICE_STOP_COVER)
        self.travel_calc.set_position(position)

    async def set_known_tilt_position(self, **kwargs):
        """We want to do a few things when we get a position"""
        position = kwargs[ATTR_TILT_POSITION]
        await self._async_handle_command(SERVICE_STOP_COVER)
        self.tilt_calc.set_position(position)

    def _has_tilt_support(self):
        """Return if cover has tilt support."""
        return self._tilting_time_down is not None and self._tilting_time_up is not None

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
    async def _async_handle_command(self, command, *args):
        if command == SERVICE_CLOSE_COVER:
            cmd = "DOWN"
            self._state = False
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._open_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self._close_switch_entity_id},
                False,
            )

        elif command == SERVICE_OPEN_COVER:
            cmd = "UP"
            self._state = True
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._close_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self._open_switch_entity_id},
                False,
            )

        elif command == SERVICE_STOP_COVER:
            cmd = "STOP"
            self._state = True
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._close_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._open_switch_entity_id},
                False,
            )



    # These methods are called by Home Assistant to open, close, or stop the cover
    async def async_open_cover(self, **kwargs):
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_close_cover(self, **kwargs):
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_stop_cover(self, **kwargs):
        await self._async_handle_command(SERVICE_STOP_COVER)





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