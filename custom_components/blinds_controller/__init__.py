from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):

    hass.helpers.discovery.load_platform('config_flow', DOMAIN, {}, config)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):


    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):

    return True