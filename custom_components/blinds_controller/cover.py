# TODO add-ons weather date of the time or sunset and sundown automations
# TODO sync with other entities
# TODO clean up code

# Import necessary modules from Home Assistant
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
    CoverEntity,
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
import asyncio

# Import the TravelCalculator and TravelStatus classes from the calculator module
# Currently using the:
# https://github.com/XKNX/xknx/blob/0.9.4/xknx/devices/travelcalculator.py
from .calculator import TravelCalculator
from .calculator import TravelStatus

# Import the domain constant from the current package
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
    name = entry.title 
    device_id = entry.entry_id 
    async_add_entities([BlindsCover(hass, entry, name, device_id)])


# This class represents a cover entity in Home Assistant
class BlindsCover(CoverEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name, device_id):
        self.hass = hass    # The Home Assistant instance
        self.entry = entry  # The configuration entry
        self._state = None  # Initialize _state attribute
        self._available = True  # Initialize _available attribute  

        self._travel_time_down = entry.data["time_down"]
        self._travel_time_up = entry.data["time_up"]
        self._travel_tilt_closed = entry.data["tilt_closed"]
        self._travel_tilt_open = entry.data["tilt_open"]
        self._up_switch_entity_id = entry.data["entity_up"]
        self._down_switch_entity_id = entry.data["entity_down"]
        
        # OPTIONAL - can be set to False if you don't want the switch to switch off when it reaches the end
        # DEFAULT is set to True (swtitches off the switch when it reaches the end)
        self._send_stop_at_ends = True

        self._target_position = 0
        self._target_tilt_position = 0

        self._unique_id = device_id
        if name:
            self._name = name
        else:
            self._name = device_id

        self._unsubscribe_auto_updater = None

        self.travel_calc = TravelCalculator(
            self._travel_time_down,
            self._travel_time_up,
        )
        if self.has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self._travel_tilt_closed,
                self._travel_tilt_open,
            )
        else:
            self.tilt_calc = None  # Initialize tilt_calc to None if tilt support is not available

        self._switch_close_state = "off"
        self._switch_open_state = "off"
    
    # Return the name
    @property
    def name(self):
        return self._name

    # The unique ID of the entity is the ID of the configuration entry
    @property
    def unique_id(self):
        return "cover_timebased_synced_uuid_" + self._unique_id
    
    # Return the device class of the cover
    @property
    def device_class(self):
        return None
    
    # The state attributes include various details about the cover (for testing perhaps)
    # Can be removed if not needed in UI
    @property
    def extra_state_attributes(self):
        return {
            "entity_up": self._up_switch_entity_id,
            "entity_down": self._down_switch_entity_id,
            "time_up": self._travel_time_up,
            "time_down": self._travel_time_down,
            "tilt_open": self._travel_tilt_open,
            "tilt_closed": self._travel_tilt_closed,
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
    def current_cover_tilt_position(self) -> float | None:
        if self.has_tilt_support():
            return self.tilt_calc.current_position()
        else:
            return None

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
    
    # The cover is available if _available is True
    @property
    def available(self):
        return self._available  
    
    # This functions are called while controlling the cover from the Home Assistant UI
    # and are used to open, close, stop, and set the position of the cover
    # Also they call functions to help them with the calculations...

    # This function is called to set the position of the cover
    async def async_set_cover_position(self, **kwargs):
       if ATTR_POSITION in kwargs:
           self._target_position = kwargs[ATTR_POSITION]
           await self.set_position(self._target_position)

    # This function is called to set the position of the covers tilt
    async def async_set_cover_tilt_position(self, **kwargs):
        if ATTR_TILT_POSITION in kwargs:
            _target_tilt_position = kwargs[ATTR_TILT_POSITION]
            await self.set_tilt_position(_target_tilt_position)

    # This function is called to set the cover to start closing
    async def async_close_cover(self, **kwargs):
        if self.travel_calc.current_position() > 0:
            self.travel_calc.start_travel_down()
            self.start_auto_updater()
            self.update_tilt_before_travel(SERVICE_CLOSE_COVER)
            await self._async_handle_command(SERVICE_CLOSE_COVER)

    # This function is called to set the cover to start opening
    async def async_open_cover(self, **kwargs):
        if self.travel_calc.current_position() < 100:
            self.travel_calc.start_travel_up()
            self.start_auto_updater()
            self.update_tilt_before_travel(SERVICE_OPEN_COVER)
            await self._async_handle_command(SERVICE_OPEN_COVER)

    # This function is called to move the cover tilting to close position
    async def async_close_cover_tilt(self, **kwargs):
        if self.tilt_calc.current_position() > 0:
            self.tilt_calc.start_travel_down()
            self.start_auto_updater()
            await self._async_handle_command(SERVICE_CLOSE_COVER)

    # This function is called to stop the cover tilting to open position
    async def async_open_cover_tilt(self, **kwargs):
        if self.tilt_calc.current_position() < 100:
            self.tilt_calc.start_travel_up()
            self.start_auto_updater()
            await self._async_handle_command(SERVICE_OPEN_COVER)


    # This function is called to stop the cover from moving
    async def async_stop_cover(self, **kwargs):
        await self._async_handle_command(SERVICE_STOP_COVER)

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
            await self._async_handle_command(command)
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
            await self._async_handle_command(command)

        # The function does not return anything
        return

    # This function is called to update the tilt before travel
    def update_tilt_before_travel(self, command):
        if self.has_tilt_support():
            if command == SERVICE_OPEN_COVER:
                self.tilt_calc.set_position(100)
            elif command == SERVICE_CLOSE_COVER:
                self.tilt_calc.set_position(0)
    

    def stop_auto_updater(self):
        self._target_position = 0
        self._target_tilt_position = 0
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def start_auto_updater(self):
        if self._unsubscribe_auto_updater is None:
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval)

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
    
    # This function is called to check if the cover supports tilt 
    # based on the user input in the configuration flow or option flow
    # Returns True if the cover supports tilt, False otherwise  
    def has_tilt_support(self):
        return (
            self.entry.data.get("tilt_open") is not None
            and self.entry.data.get("tilt_closed") is not None
            and self._travel_tilt_open != 0
            and self._travel_tilt_closed != 0
        )
    
    async def _handle_state_changed(self, event):
        if event.data.get("new_state") is None:
            return

        if event.data.get("old_state") is None:
            return

        if event.data.get("new_state").state == event.data.get("old_state").state:
            return

        if event.data.get("entity_id") == self._down_switch_entity_id:
            if self._switch_close_state == event.data.get("new_state").state:
                return
            self._switch_close_state = event.data.get("new_state").state
        elif event.data.get("entity_id") == self._up_switch_entity_id:
            if self._switch_open_state == event.data.get("new_state").state:
                return
            self._switch_open_state = event.data.get("new_state").state
        else:
            return

        if self._switch_open_state == "off" and self._switch_close_state == "off":
            self._handle_my_button()
        elif self._switch_open_state == "on" and self._switch_close_state == "on":
            self._handle_my_button()
            if event.data.get("entity_id") == self._down_switch_entity_id:
                await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._up_switch_entity_id}, False)
            if event.data.get("entity_id") == self._up_switch_entity_id:
                await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._down_switch_entity_id}, False)
        elif self._switch_open_state == "on" and self._switch_close_state == "off":
            if not self.has_tilt_support():
                if self._target_position != 100 and self._target_position != 0:
                    self.travel_calc.start_travel(self._target_position)
                else:
                    self._target_position = 100
                    self.travel_calc.start_travel_up()
                self.start_auto_updater()
            else:
                if not self.tilt_calc.is_traveling():
                    self.update_tilt_before_travel(SERVICE_OPEN_COVER)
                    if self._target_position != 100 and self._target_position != 0:
                        self.travel_calc.start_travel(self._target_position)
                    else:
                        self._target_position = 100
                        self.travel_calc.start_travel_up()
                    self.start_auto_updater()
        elif self._switch_open_state == "off" and self._switch_close_state == "on":
            if not self.has_tilt_support():
                if self._target_position != 100 and self._target_position != 0:
                    self.travel_calc.start_travel(self._target_position)
                else:
                    self._target_position = 0
                    self.travel_calc.start_travel_down()
                self.start_auto_updater()
            else:
                if not self.tilt_calc.is_traveling():
                    self.update_tilt_before_travel(SERVICE_CLOSE_COVER)
                    if self._target_position != 100 and self._target_position != 0:
                        self.travel_calc.start_travel(self._target_position)
                    else:
                        self._target_position = 0
                        self.travel_calc.start_travel_down()
                    self.start_auto_updater()
        # Update state of entity
        self.async_write_ha_state()
            

    async def async_added_to_hass(self):
        self.hass.bus.async_listen("state_changed", self._handle_state_changed)
        
        old_state = await self.async_get_last_state()

        if (old_state is not None and self.travel_calc is not None and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None):
            self.travel_calc.set_position(int(old_state.attributes.get(ATTR_CURRENT_POSITION)))

            # If the cover supports tilt and the old state has a current tilt position attribute
            if (
                self.has_tilt_support()
                and old_state.attributes.get(ATTR_CURRENT_TILT_POSITION) is not None
            ):
                # Set the position of the tilt calculator to the old state's current tilt position
                self.tilt_calc.set_position(
                    int(old_state.attributes.get(ATTR_CURRENT_TILT_POSITION))
                )

    def _handle_my_button(self):
        if self.travel_calc.is_traveling() or (self.has_tilt_support() and self.tilt_calc.is_traveling()):
            self.travel_calc.stop()
            if self.has_tilt_support():
                self.tilt_calc.stop()
            self.stop_auto_updater()
        

    # This function is called to stop the cover if it has reached its final position
    async def auto_stop_if_necessary(self):
        current_tilt_position = self.tilt_calc.current_position() if self.has_tilt_support() else None
        current_position = self.travel_calc.current_position()

        if self.position_reached():
            self.travel_calc.stop()
            if self.has_tilt_support():
                self.tilt_calc.stop()
            if ((current_position > 0) and (current_position < 100)) or ((current_tilt_position > 0) and (current_tilt_position < 100)):
                await self._async_handle_command(SERVICE_STOP_COVER)
            else:
                if self._send_stop_at_ends:
                    await self._async_handle_command(SERVICE_STOP_COVER)


    async def _async_handle_command(self, command, *args):
        if command == "close_cover":
            self._state = False
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._up_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._down_switch_entity_id}, False)

        elif command == "open_cover":
            self._state = True
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._down_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": self._up_switch_entity_id}, False)

        elif command == "stop_cover":
            self._state = True
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._up_switch_entity_id}, False)
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": self._down_switch_entity_id}, False)


        # Update state of entity
        self.async_write_ha_state()