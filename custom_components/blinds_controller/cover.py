# TODO add-ons weather date of the time or sunset and sundown automations
# TODO fix if controling from outside tilting works better... not up instantly...
# TODO fix the tilt support. so if the tilt is not supported, it should not be shown in the UI
# TODO the availablity of the cover if entity is not available

# Import necessary modules from Home Assistant
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.helpers import entity_platform
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

# Import the logger and datetime modules
import logging
from datetime import timedelta

# Import the TravelCalculator and TravelStatus classes from the calculator module
# Currently using the:
# https://github.com/XKNX/xknx/blob/0.9.4/xknx/devices/travelcalculator.py
from .calculator import TravelCalculator
from .calculator import TravelStatus

# Import the domain constant from the current package
from .const import DOMAIN

# Logger for debuggind purposes
_LOGGER = logging.getLogger(__name__)

# The service names for setting the known position and tilt position
# Keep same as in services.yaml
SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_TILT_POSITION = "set_known_tilt_position"

# This function takes the Home Assistant instance, the configuration data,
# function to add entities, and optional discovery information.
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    platform = entity_platform.current_platform.get()

    # Register a service for setting the known position of the cover.
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION, "set_known_position"
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_TILT_POSITION, "set_known_tilt_position"
    )

# This function is called by Home Assistant to setup the component
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(hass, entry)])

# This class represents a cover entity in Home Assistant
class BlindsCover(CoverEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass    # The Home Assistant instance
        self.entry = entry  # The configuration entry
        self._state = None  # Initialize _state attribute
        self._available = True  # Initialize _available attribute
        self._setting_position_manually = False  # Initialize _setting_position_manually attribute
        self._setting_tilt_manually = False  # Initialize _setting_tilt_manually attribute
        # Listen for state changes of the up and down switches
        self.hass.bus.async_listen('state_changed', self.handle_state_change)

        self.travel_calc = TravelCalculator(
            self.entry.data["time_down"],
            self.entry.data["time_up"],
        )
        if self.has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self.entry.data["tilt_closed"],
                self.entry.data["tilt_open"],
            )

        self._unsubscribe_auto_updater = None

    # The unique ID of the entity is the ID of the configuration entry
    @property
    def unique_id(self):
        return self.entry.entry_id
    
    # The name of the entity is the "ent_name" from the configuration data
    # Return the name of the cover
    @property
    def name(self):
        return self.entry.data["ent_name"]
    
    # Return the device class of the cover
    @property
    def device_class(self):
        return None

    # The state attributes include various details about the cover (for testing perhaps)
    # Can be removed if not needed in UI
    @property
    def extra_state_attributes(self):
        return {
            "entity_up": self.entry.data["entity_up"],
            "entity_down": self.entry.data["entity_down"],
            "time_up": self.entry.data["time_up"],
            "time_down": self.entry.data["time_down"],
            "tilt_open": self.entry.data["tilt_open"],
            "tilt_closed": self.entry.data["tilt_closed"],
        }
    
    # Adds the features of the cover entity
    # OPEN, CLOSE and STOP are always supported
    # If has_tilt_support is True, OPEN_TILT, CLOSE_TILT and STOP_TILT are also supported
    # as the user wishes to be able to control the tilt of the cover
    @property
    def supported_features(self) -> CoverEntityFeature:
        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if self.current_cover_position is not None:
            supported_features |= CoverEntityFeature.SET_POSITION

        if self.has_tilt_support():
            supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
            )
            if self.current_cover_tilt_position is not None:
                supported_features |= CoverEntityFeature.SET_TILT_POSITION

        return supported_features
    
    # Return the current position of the cover
    @property
    def current_cover_position(self) -> int | None:
        return self.travel_calc.current_position()

    # Return the current tilt of the cover
    @property
    def current_cover_tilt_position(self) -> int | None:
        return self.tilt_calc.current_position()

    # This properties (is_closed, is_opening and is_closing) are needed by the Home Assistant UI 
    # to display the state of the cover correctly
    @property
    def is_closed(self):
        return self.travel_calc.is_closed()
    
    @property
    def is_opening(self):
        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_UP
        ) or (
            self.has_tilt_support()
            and self.tilt_calc.is_traveling()
            and self.tilt_calc.travel_direction == TravelStatus.DIRECTION_UP
        )
    
    @property
    def is_closing(self):
        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_DOWN
        ) or (
            self.has_tilt_support()
            and self.tilt_calc.is_traveling()
            and self.tilt_calc.travel_direction == TravelStatus.DIRECTION_DOWN
        )
    
    # The cover is considered open if _state is True
    @property
    def assumed_state(self):
        return True

    # The cover is available if _available is True
    # TODO i guess this is not working as expected
    @property
    def available(self):
        return self._available  


    # This functions are called while controlling the cover from the Home Assistant UI
    # and are used to open, close, stop, and set the position of the cover
    # Also they call functions to help them with the calculations...

    # This function is called to set the position of the cover
    async def async_set_cover_position(self, **kwargs):
        if ATTR_POSITION in kwargs:
            # Set a flag to indicate that position is being set manually
            self._setting_position_manually = True
            position = kwargs[ATTR_POSITION]
            await self.set_position(position)
            # Reset the flag after setting position
            self._setting_position_manually = False

    # This function is called to set the position of the covers tilt
    async def async_set_cover_tilt_position(self, **kwargs):
        if ATTR_TILT_POSITION in kwargs:
            # Set the flag to indicate manual tilt adjustment
            self._setting_tilt_manually = True
            position = kwargs[ATTR_TILT_POSITION]
            await self.set_tilt_position(position)
            # Reset the flag after setting position
            self._setting_tilt_manually = False

    # This function is called to set the cover to start closing
    async def async_close_cover(self, **kwargs):
        if self.travel_calc.current_position() > 0:
            self.travel_calc.start_travel_down()
            self.start_auto_updater()
            self.update_tilt_before_travel(SERVICE_CLOSE_COVER)
            await self.handle_command(SERVICE_CLOSE_COVER)

    # This function is called to set the cover to start opening 
    async def async_open_cover(self, **kwargs):
        if self.travel_calc.current_position() < 100:
            self.travel_calc.start_travel_up()
            self.start_auto_updater()
            self.update_tilt_before_travel(SERVICE_OPEN_COVER)
            await self.handle_command(SERVICE_OPEN_COVER)

    # This function is called to move the cover tilting to close position
    async def async_close_cover_tilt(self, **kwargs):
        if self.tilt_calc.current_position() > 0:
            self.tilt_calc.start_travel_down()
            self.start_auto_updater()
            await self.handle_command(SERVICE_CLOSE_COVER)

    # This function is called to stop the cover tilting to open position
    async def async_open_cover_tilt(self, **kwargs):
        if self.tilt_calc.current_position() < 100:
            self.tilt_calc.start_travel_up()
            self.start_auto_updater()
            await self.handle_command(SERVICE_OPEN_COVER)

    # This function is called to stop the cover from moving
    async def async_stop_cover(self, **kwargs):
        self.handle_stop()
        await self.handle_command(SERVICE_STOP_COVER)

    # This function handles the stop command
    def handle_stop(self):
        if self.travel_calc.is_traveling():
            self.travel_calc.stop()
            self.stop_auto_updater()

        if self.tilt_calc.is_traveling():
            self.tilt_calc.stop()
            self.stop_auto_updater()

    # This function is called to move the cover to a designated position
    async def set_position(self, position):
        # Get the current position of the cover
        current_position = self.travel_calc.current_position()
        command = None

        # Determine whether to open or close the cover based on the desired position
        if position < current_position:
            # If the desired position is less than the current position, close the cover
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            # If the desired position is greater than the current position, open the cover
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            # Start moving the cover to the desired position
            self.travel_calc.start_travel(position)
            # Update the tilt of the cover before it starts moving
            self.update_tilt_before_travel(command)
            # Execute the open or close command
            await self.handle_command(command)
        return

    # This function is called to move the cover tilt to a designated position
    async def set_tilt_position(self, position):

        # Get the current tilt position
        current_position = self.tilt_calc.current_position()
        command = None

        # Determine whether to open or close the cover based on the desired position
        if position < current_position:
            # If the desired position is less than the current position, close the cover
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            # If the desired position is greater than the current position, open the cover
            command = SERVICE_OPEN_COVER

        if command is not None:
            self.start_auto_updater()
            # Start moving the tilt to the desired position
            self.tilt_calc.start_travel(position)
            # Execute the open or close command
            await self.handle_command(command)
        return
    
    # Stop the autoupdater
    def stop_auto_updater(self):
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    # Start the autoupdater and update the state of the cover while it is moving
    def start_auto_updater(self):
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    # This function updates the state of the cover in the Home Assistant UI
    @callback
    def auto_updater_hook(self, now):
        self.async_schedule_update_ha_state()
        if self.position_reached():
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    # This function is called to check if the cover has reached its final position
    def position_reached(self):
        return self.travel_calc.position_reached() and (
            not self.has_tilt_support() or self.tilt_calc.position_reached()
        )
    
    # This function is called to update the tilt before travel
    def update_tilt_before_travel(self, command):
        if self.has_tilt_support():
            if command == SERVICE_OPEN_COVER:
                self.tilt_calc.set_position(100)
            elif command == SERVICE_CLOSE_COVER:
                self.tilt_calc.set_position(0)

    # This function is called to stop the cover if it has reached its final position
    async def auto_stop_if_necessary(self):
        if self.position_reached():
            self.travel_calc.stop()
            if self.has_tilt_support():
                self.tilt_calc.stop()
            await self.handle_command(SERVICE_STOP_COVER)

    # This functions are to set the known position of the cover and tilt
    async def set_known_position(self, **kwargs):
        position = kwargs[ATTR_POSITION]
        self.handle_stop()
        await self.handle_command(SERVICE_STOP_COVER)
        self.travel_calc.set_position(position)

    async def set_known_tilt_position(self, **kwargs):
        position = kwargs[ATTR_TILT_POSITION]
        await self.handle_command(SERVICE_STOP_COVER)
        self.tilt_calc.set_position(position)
    

    # TODO needs to be fixed 
    # This function is called to check if the cover supports tilt 
    # based on the user input in the configuration flow or option flow
    # Returns True if the cover supports tilt, False otherwise  
    def has_tilt_support(self):
        return self.entry.data["tilt_open"] != 0 and self.entry.data["tilt_closed"] != 0

    # This function is called when the state of the up or down switch changes
    async def handle_command(self, command, *args):
        
        if command == SERVICE_CLOSE_COVER:
            self._state = False
            # Turn off the 'up' entity
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self.entry.data["entity_up"]},
                False,
            )
            # Turn on the 'down' entity
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self.entry.data["entity_down"]},
                False,
            )

        elif command == SERVICE_OPEN_COVER:
            self._state = True
            # Turn off the 'down' entity
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self.entry.data["entity_down"]},
                False,
            )
            # Turn on the 'up' entity
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self.entry.data["entity_up"]},
                False,
            )

        elif command == SERVICE_STOP_COVER:
            self._state = True
            # Turn off both the 'down' and 'up' entities
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self.entry.data["entity_down"]},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self.entry.data["entity_up"]},
                False,
            )


    # This function is called when the state of the up or down switch changes
    async def handle_state_change(self, event):
        # If the cover is not moving and not manually setting position or tilt
        if (
            not self.travel_calc.is_traveling()
            and not self.tilt_calc.is_traveling()
            and not self._setting_position_manually
            and not self._setting_tilt_manually
        ):
            # Handle the 'up' and 'down' events
            if event.data['entity_id'] == self.entry.data["entity_up"]:
                if event.data['new_state'].state == 'on':
                    if self.travel_calc.current_position() < 100:
                        self.travel_calc.start_travel_up()
                        self.start_auto_updater()
                        self.update_tilt_before_travel(SERVICE_OPEN_COVER)
                        await self.handle_command(SERVICE_OPEN_COVER)
            elif event.data['entity_id'] == self.entry.data["entity_down"]:
                if event.data['new_state'].state == 'on':
                    if self.travel_calc.current_position() > 0:
                        self.travel_calc.start_travel_down()
                        self.start_auto_updater()
                        self.update_tilt_before_travel(SERVICE_CLOSE_COVER)
                        await self.handle_command(SERVICE_CLOSE_COVER)

        # Always handle the 'off' event, even if the cover is moving
        if event.data['new_state'].state == 'off':
            self.handle_stop()
            await self.handle_command(SERVICE_STOP_COVER)

                


    # This function is called by Home Assistant to restore the state of the cover
    # from the previous session if Home Assistant was restarted or interrupted
    async def async_added_to_hass(self):
        # Get the last known state of the cover
        old_state = await self.async_get_last_state()

        # If the old state exists and the travel calculator is initialized
        if (
            old_state is not None
            and self.travel_calc is not None
            # And the old state has a current position attribute
            and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            # Set the position of the travel calculator to the old state's current position
            self.travel_calc.set_position(
                int(old_state.attributes.get(ATTR_CURRENT_POSITION))
            )

            # If the cover supports tilt and the old state has a current tilt position attribute
            if (
                self.has_tilt_support()
                and old_state.attributes.get(ATTR_CURRENT_TILT_POSITION) is not None
            ):
                # Set the position of the tilt calculator to the old state's current tilt position
                self.tilt_calc.set_position(
                    int(old_state.attributes.get(ATTR_CURRENT_TILT_POSITION))
                )