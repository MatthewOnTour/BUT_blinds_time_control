# TODO add-ons weather date of the time or sunset and sundown automations
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
from homeassistant.helpers.event import async_track_state_change

# Import the logger and datetime modules
import logging
from datetime import datetime, timedelta, timezone
import asyncio
import urllib.request
import json


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

        # Add ons
        self._timed_control_down = entry.data["timed_control_down"]
        self._time_to_roll_up = entry.data["time_to_roll_up"]
        self._timed_control_up = entry.data["timed_control_up"]
        self._time_to_roll_down = entry.data["time_to_roll_down"]
        self._delay_control = entry.data["delay_control"]
        self._delay_sunrise = entry.data["delay_sunrise"]
        self._delay_sunset = entry.data["delay_sunset"]
        self._night_lights = entry.data["night_lights"]
        self._entity_night_lights = entry.data["entity_night_lights"]
        self._tilting_day = entry.data["tilting_day"]
        self._protect_the_blinds = entry.data["protect_the_blinds"]
        self._set_wind_speed = entry.data["wind_speed"]
        self._wmo_code = entry.data["wmo_code"]
        self._send_stop_at_end = entry.data["send_stop_at_end"]

        self._sun_next_sunrise = self.hass.states.get("sensor.sun_next_dawn").state
        self._sun_next_sunset = self.hass.states.get("sensor.sun_next_dusk").state

        self._target_position = 0
        self._target_tilt_position = 0

        self._weather_check_counter = 0 
        self._tilt_check_counter = 0

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
        self._night_lights_state = "off"

    async def sun_state_changed(self, entity_id, old_state, new_state):
        if new_state is not None:
            if entity_id == "sensor.sun_next_dawn":
                self._sun_next_sunrise = new_state.state
            elif entity_id == "sensor.sun_next_dusk":
                self._sun_next_sunset = new_state.state


    
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
                self.tilt_calc.start_travel_up()
            elif command == SERVICE_CLOSE_COVER:
                self.tilt_calc.start_travel_down()
    

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

    async def add_ons(self, now):
        # Adjust the current time by adding one hour
        corrected_time = now + timedelta(hours=1) # Edit the time if needed to correct the time zone

        # Format the corrected time to display only HH:MM
        formatted_time = corrected_time.strftime("%H:%M")


        if self._timed_control_down and not self.travel_calc.is_traveling():
            try:
                parsed_time_to_roll_down = datetime.strptime(self._time_to_roll_down, "%H:%M")
                formatted_time_to_roll_down = parsed_time_to_roll_down.strftime("%H:%M")  
            except ValueError:
                _LOGGER.error("Invalid format for timed control")
                return
            
            if formatted_time_to_roll_down == formatted_time and self.travel_calc.current_position() > 0:
                await self.async_close_cover()
        
        if self._timed_control_up and not self.travel_calc.is_traveling():
            try:
                parsed_time_to_roll_up = datetime.strptime(self._time_to_roll_up, "%H:%M")
                formatted_time_to_roll_up = parsed_time_to_roll_up.strftime("%H:%M")
            except ValueError:
                _LOGGER.error("Invalid format for timed control")
                return
            
            if formatted_time_to_roll_up == formatted_time and self.travel_calc.current_position() < 100:
                await self.async_open_cover()

        if self._delay_control and not self.travel_calc.is_traveling():
            parse_time_sunset = datetime.fromisoformat(self._sun_next_sunset)
            parse_time_sunrise = datetime.fromisoformat(self._sun_next_sunrise)

            formatted_time_sunset = parse_time_sunset.strftime("%H:%M")
            formatted_time_sunrise = parse_time_sunrise.strftime("%H:%M")

            parsed_offset_sunset = datetime.strptime(formatted_time_sunset, "%H:%M")
            parsed_offset_sunrise = datetime.strptime(formatted_time_sunrise, "%H:%M")

            offset_time_sunset = parsed_offset_sunset + timedelta(minutes=self._delay_sunset)
            offset_time_sunrise = parsed_offset_sunrise + timedelta(minutes=self._delay_sunrise)

            formatted_offset_sunset = offset_time_sunset.strftime("%H:%M")
            formatted_offset_sunrise = offset_time_sunrise.strftime("%H:%M")

            if formatted_offset_sunset == formatted_time and self.travel_calc.current_position() > 0:
                await self.async_close_cover()

            if formatted_offset_sunrise == formatted_time and self.travel_calc.current_position() < 100:
                await self.async_open_cover()

        if self._night_lights and not self.travel_calc.is_traveling():
            parse_time_sunset = datetime.fromisoformat(self._sun_next_sunset)
            parse_time_sunrise = datetime.fromisoformat(self._sun_next_sunrise)

            formatted_time_sunset = parse_time_sunset.strftime("%H:%M")
            formatted_time_sunrise = parse_time_sunrise.strftime("%H:%M")

            if (formatted_time > formatted_time_sunset or formatted_time < formatted_time_sunrise) and self._night_lights_state == "on" and self.travel_calc.current_position() > 0:
                await self.async_close_cover()
        
        if self.has_tilt_support():
            self._tilt_check_counter += 1
            if self._tilt_check_counter == 10:
                self._tilt_check_counter = 0
                if self._tilting_day and not self.travel_calc.is_traveling() and not self.tilt_calc.is_traveling():
                    parse_time_sunset = datetime.fromisoformat(self._sun_next_sunset)
                    parse_time_sunrise = datetime.fromisoformat(self._sun_next_sunrise)

                    formatted_time_sunset = parse_time_sunset.strftime("%H:%M")
                    formatted_time_sunrise = parse_time_sunrise.strftime("%H:%M")

                    if not (formatted_time > formatted_time_sunset or formatted_time < formatted_time_sunrise) and self.tilt_calc.current_position() < 100:
                        await self.async_open_cover_tilt()

        _LOGGER.info("self._protect_the_blinds: %s", self._protect_the_blinds)
        if self._protect_the_blinds and not self.travel_calc.is_traveling():
                    self._weather_check_counter += 1
                     # Check if the counter reaches 30
                    if self._weather_check_counter == 30:
                        self._weather_check_counter = 0
                        latitude, longitude = self.get_location_coordinates(self.hass)
                        _LOGGER.info("Latitude: %s, Longitude: %s", latitude, longitude)
                        
                        # Construct the API URL
                        api_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=wind_speed_10m&daily=weather_code"
                        
                        try:
                            # Make the request asynchronously
                            response = await self.hass.async_add_executor_job(urllib.request.urlopen, api_url)
                            data = json.loads(response.read().decode('utf-8'))
                            _LOGGER.info("Retrieved data: %s", data)
                            
                            # Extract wind speed and weather code
                            current_data = data.get('current', {})
                            wind_speed = current_data.get('wind_speed_10m')
                            
                            daily_data = data.get('daily', {})
                            weather_code = daily_data.get('weather_code')
                            
                            if wind_speed > self._set_wind_speed and self.travel_calc.current_position() < 100:
                                await self.async_open_cover()
                                _LOGGER.info("Wind speed is too high: %s", wind_speed)
                            today_weather_code = data.get('daily', {}).get('weather_code', [])[0]
                            if today_weather_code > self._wmo_code and self.travel_calc.current_position() < 100:
                                await self.async_open_cover()
                                _LOGGER.info("Weather code indicates rain: %s", weather_code)
                            
                            _LOGGER.info("Wind speed: %s, Weather code: %s", wind_speed, weather_code)
                            
                        except Exception as e:
                            _LOGGER.error("Error retrieving weather data: %s", e)

        _LOGGER.info("Current time: %s", formatted_time)   
                
        
    # This function is called to get latitude and longitude from Home Assistant configuration
    def get_location_coordinates(self, hass):
        # Access the latitude and longitude from Home Assistant configuration
        latitude = hass.config.latitude
        longitude = hass.config.longitude
        return latitude, longitude

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
        
        if event.data.get("entity_id") == self._entity_night_lights:
            if self._night_lights_state == event.data.get("new_state").state:
                return
            self._night_lights_state = event.data.get("new_state").state

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
        # Set up periodic time update
        self.hass.helpers.event.async_track_time_interval(self.add_ons, timedelta(minutes=1))
        async_track_state_change(
            self.hass, "sensor.sun_next_dawn", self.sun_state_changed
        )
        async_track_state_change(
            self.hass, "sensor.sun_next_dusk", self.sun_state_changed
        )


        
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
                    if self._send_stop_at_end:
                        await self._async_handle_command(SERVICE_STOP_COVER)
            else:
                if (current_position > 0) and (current_position < 100):
                    await self._async_handle_command(SERVICE_STOP_COVER)
                else:
                    if self._send_stop_at_end:
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