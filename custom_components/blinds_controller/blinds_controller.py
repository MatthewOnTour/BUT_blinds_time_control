from homeassistant.components.cover import CoverEntity

from .const import DOMAIN

def setup_platform(hass, config, add_entities, discovery_info=None):
    # Get the blinds data from the config entry
    blinds_data = hass.data[DOMAIN][discovery_info["entry_id"]]

    # Create a list of BlindsCover entities
    entities = [BlindsCover(blinds_data)]

    # Add the entities
    add_entities(entities, True)

class BlindsCover(CoverEntity):
    def __init__(self, blinds_data):
        self.blinds_data = blinds_data

    @property
    def name(self):
        return self.blinds_data["ent_name"]
