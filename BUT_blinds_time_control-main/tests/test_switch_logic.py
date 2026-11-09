import unittest
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "blinds_controller")))

from calculator import TravelCalculator, TravelStatus


class MockSwitchCoverController:
    """Mock controller encapsulating the switch logic with dead_time and sperrzeit."""

    def __init__(self, time_down=100.0, time_up=100.0, dead_time=0.78, sperrzeit=0.2, overtravel_time=1.0):
        self.dead_time = dead_time
        self.sperrzeit = sperrzeit
        self.overtravel_time = overtravel_time
        self.travel_calc = TravelCalculator(time_down, time_up, startup_delay=dead_time)

        self.up_switch = "switch.blind_up"
        self.down_switch = "switch.blind_down"

        self.switch_press_time = {}
        self.expected_switch_states = {}  # {entity_id: (state, timestamp)}
        self.current_mock_time = 1000.0
        self.travel_calc.time_set_from_outside = self.current_mock_time

        self.switch_states = {self.up_switch: "off", self.down_switch: "off"}
        self.auto_updater_running = False
        self.stopped_count = 0

    def get_time(self):
        return self.current_mock_time

    def set_time(self, new_time):
        self.current_mock_time = new_time
        self.travel_calc.time_set_from_outside = new_time

    # Command from HA
    def ha_set_position(self, target_pos: int):
        current_pos = self.travel_calc.current_position()
        if target_pos == current_pos:
            return "same_position"

        rel_pos = abs(target_pos - current_pos)
        full_time = self.travel_calc.travel_time_up if target_pos > current_pos else self.travel_calc.travel_time_down
        move_time = full_time * rel_pos / 100.0
        total_relay_time = move_time + self.dead_time

        # Sperrzeit lockout check
        if total_relay_time <= self.sperrzeit:
            return "blocked_by_sperrzeit"

        target_switch = self.up_switch if target_pos > current_pos else self.down_switch
        other_switch = self.down_switch if target_switch == self.up_switch else self.up_switch

        self.expected_switch_states[other_switch] = ("off", self.get_time())
        self.switch_states[other_switch] = "off"
        self.expected_switch_states[target_switch] = ("on", self.get_time())
        self.switch_states[target_switch] = "on"

        self.travel_calc.start_travel(target_pos)
        self.auto_updater_running = True
        return "started"

    def ha_stop_cover(self):
        self.expected_switch_states[self.up_switch] = ("off", self.get_time())
        self.switch_states[self.up_switch] = "off"
        self.expected_switch_states[self.down_switch] = ("off", self.get_time())
        self.switch_states[self.down_switch] = "off"

        self.travel_calc.stop()
        self.auto_updater_running = False
        self.stopped_count += 1

    # Switch state change event handler
    def on_switch_state_changed(self, entity_id: str, new_state: str):
        # 1. Echo suppression
        expected = self.expected_switch_states.get(entity_id)
        if expected is not None:
            exp_state, exp_time = expected
            if new_state == exp_state and (self.get_time() - exp_time < 5.0):
                del self.expected_switch_states[entity_id]
                return "ignored_echo"

        # 2. External switch event
        if new_state == "on":
            # If cover is already moving -> tap to stop!
            if self.travel_calc.is_traveling():
                self.ha_stop_cover()
                return "tapped_to_stop"

            # Cover was stopped -> start travel
            self.switch_press_time[entity_id] = self.get_time()
            if entity_id == self.up_switch:
                self.travel_calc.start_travel_up()
                self.auto_updater_running = True
                return "started_up"
            elif entity_id == self.down_switch:
                self.travel_calc.start_travel_down()
                self.auto_updater_running = True
                return "started_down"

        elif new_state == "off":
            press_time = self.switch_press_time.pop(entity_id, None)
            if press_time is not None:
                duration = self.get_time() - press_time
                if duration <= self.sperrzeit:
                    # Short pulse (<= sperrzeit, e.g. 0.1s):
                    # Physical hardware triggered full travel!
                    return "short_pulse_keep_running"
                else:
                    # Hold released (> sperrzeit):
                    # Motor stopped; record position factoring in dead_time!
                    self.travel_calc.stop()
                    self.auto_updater_running = False
                    self.stopped_count += 1
                    return "hold_stopped"

        return "no_action"


class TestSwitchLogic(unittest.TestCase):
    def setUp(self):
        # 100s travel time, 0.78s dead_time, 0.2s sperrzeit
        self.ctrl = MockSwitchCoverController(
            time_down=100.0, time_up=100.0, dead_time=0.78, sperrzeit=0.2
        )
        self.ctrl.travel_calc.set_position(100)  # initially fully open (100%)

    def test_ha_command_echo_suppressed(self):
        res = self.ctrl.ha_set_position(50)
        self.assertEqual(res, "started")
        res1 = self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "on")
        res2 = self.ctrl.on_switch_state_changed(self.ctrl.up_switch, "off")
        self.assertEqual(res1, "ignored_echo")
        self.assertEqual(res2, "ignored_echo")

    def test_external_short_pulse_0_1s_completes_full_travel(self):
        # User presses down switch for 0.1s (< sperrzeit 0.2s)
        res_on = self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "on")
        self.assertEqual(res_on, "started_down")
        self.assertTrue(self.ctrl.travel_calc.is_traveling())

        # 0.1s later: switch turns OFF
        self.ctrl.set_time(1000.1)
        res_off = self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "off")
        self.assertEqual(res_off, "short_pulse_keep_running")

        # Crucial: The cover MUST STILL BE TRAVELING towards 0%!
        self.assertTrue(self.ctrl.travel_calc.is_traveling())

        # Advance time to full travel (0.78s dead time + 100s travel = 100.78s)
        self.ctrl.set_time(1100.78)
        self.assertEqual(self.ctrl.travel_calc.current_position(), 0)
        self.assertTrue(self.ctrl.travel_calc.position_reached())

    def test_external_press_under_dead_time_no_movement(self):
        # User presses down switch for 0.5s (> sperrzeit 0.2s, but < dead_time 0.78s)
        self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "on")

        # Released at 0.5s
        self.ctrl.set_time(1000.5)
        res_off = self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "off")
        self.assertEqual(res_off, "hold_stopped")

        # Position must NOT have changed because dead time (0.78s) was not reached!
        self.assertEqual(self.ctrl.travel_calc.current_position(), 100)
        self.assertFalse(self.ctrl.travel_calc.is_traveling())

    def test_external_hold_10s_accounts_for_dead_time(self):
        # User holds down switch for 10.0s (1000.0 to 1010.0)
        self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "on")

        self.ctrl.set_time(1010.0)
        res_off = self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "off")
        self.assertEqual(res_off, "hold_stopped")

        # Held for 10s -> Effective travel = 10.0 - 0.78 = 9.22s.
        # Position moving down from 100% with 100s total travel: 100 - 9.22% = 90.78% -> rounds to 91%
        self.assertEqual(self.ctrl.travel_calc.current_position(), 91)
        self.assertFalse(self.ctrl.travel_calc.is_traveling())

    def test_tap_while_moving_stops_cover(self):
        # Start travel via short pulse
        self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "on")
        self.ctrl.set_time(1000.1)
        self.ctrl.on_switch_state_changed(self.ctrl.down_switch, "off")
        self.assertTrue(self.ctrl.travel_calc.is_traveling())

        # At t = 1020.0 (20s into travel), user taps switch to stop
        self.ctrl.set_time(1020.0)
        res = self.ctrl.on_switch_state_changed(self.ctrl.up_switch, "on")
        self.assertEqual(res, "tapped_to_stop")
        self.assertFalse(self.ctrl.travel_calc.is_traveling())


if __name__ == "__main__":
    unittest.main()
