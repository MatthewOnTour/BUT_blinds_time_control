from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # Create a new cover entity for each configuration entry
    async_add_entities([BlindsCover(entry)])

class BlindsCover(CoverEntity):
    def __init__(self, entry: ConfigEntry):
        self.entry = entry

    @property
    def unique_id(self):
        # Use the entry ID as the unique ID for this entity
        return self.entry.entry_id

    @property
    def name(self):
        # Use the "ent_name" from the configuration data as the name of this entity
        return self.entry.data["ent_name"]

    @property
    def is_closed(self):
        # This is a required property, but since this entity doesn't actually control a device,
        # we'll just return None to indicate that the closed state is unknown
        return None