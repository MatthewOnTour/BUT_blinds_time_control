from homeassistant.components.switch import is_on, turn_on, turn_off

class BlindsCover(CoverEntity):
    def __init__(self, hass, blinds_data):
        self.hass = hass
        self.blinds_data = blinds_data

    @property
    def name(self):
        return self.blinds_data["ent_name"]

    def open_cover(self, **kwargs):
        # Call the service of the up button entity
        up_button_entity_id = self.blinds_data["entity_up"]
        if not is_on(self.hass, up_button_entity_id):
            turn_on(self.hass, up_button_entity_id)

    def close_cover(self, **kwargs):
        # Call the service of the down button entity
        down_button_entity_id = self.blinds_data["entity_down"]
        if not is_on(self.hass, down_button_entity_id):
            turn_on(self.hass, down_button_entity_id)