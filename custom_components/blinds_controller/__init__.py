from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    # Return True here and the user will be able to initiate the config flow from the integrations page
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Set up your integration with the configuration entry
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    # Load the cover platform with the configuration entry
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "cover")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Unload your integration when the configuration entry is removed
    await hass.config_entries.async_forward_entry_unload(entry, "cover")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True