from homeassistant.components.cover import CoverEntity
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Get the blinds data from the config entry
    blinds_data = hass.data[DOMAIN][config_entry.entry_id]

    # Create a list of BlindsCover entities
    entities = [BlindsCover(blinds_data)]

    # Add the entities
    async_add_entities(entities, True)

class BlindsCover(CoverEntity):
    def __init__(self, blinds_data):
        self.blinds_data = blinds_data

    @property
    def name(self):
        return self.blinds_data["ent_name"]