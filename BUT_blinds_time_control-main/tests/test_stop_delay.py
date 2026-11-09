import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "blinds_controller")))

from calculator import TravelCalculator, PositionType, TravelStatus


class TestStopDelay(unittest.TestCase):
    def test_effective_dead_time_with_stop_delay(self):
        dead_time = 0.78
        stop_delay = 0.15
        effective_dead_time = max(0.0, dead_time - stop_delay)  # 0.63s

        # 100s full travel time
        calc = TravelCalculator(travel_time_down=100.0, travel_time_up=100.0, startup_delay=effective_dead_time)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)

        # Move 1% (1 second of movement)
        calc.start_travel(1)

        # At t = 1000.63s (end of effective dead time), position still 0
        calc.time_set_from_outside = 1000.63
        self.assertEqual(calc.current_position(), 0)

        # At t = 1001.63s (0.63s effective dead time + 1.0s movement = 1.63s total relay time)
        calc.time_set_from_outside = 1001.63
        self.assertEqual(calc.current_position(), 1)
        self.assertTrue(calc.position_reached())

    def test_hold_10s_with_stop_delay(self):
        dead_time = 0.78
        stop_delay = 0.15
        effective_dead_time = max(0.0, dead_time - stop_delay)  # 0.63s

        calc = TravelCalculator(travel_time_down=100.0, travel_time_up=100.0, startup_delay=effective_dead_time)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)
        calc.start_travel_up()

        # Held for 10 seconds: 1000.0 to 1010.0
        # Effective movement = 10.0 - 0.63 = 9.37s -> rounds to 9%
        calc.time_set_from_outside = 1010.0
        self.assertEqual(calc.current_position(), 9)

        calc.stop()
        self.assertEqual(calc.last_known_position, 9)


if __name__ == "__main__":
    unittest.main()
