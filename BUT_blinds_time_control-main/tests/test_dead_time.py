import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "blinds_controller")))

from calculator import TravelCalculator, PositionType, TravelStatus


class TestTravelCalculatorDeadTime(unittest.TestCase):
    def test_dead_time_0_78s_and_1_percent_move(self):
        # 100s total travel time, 0.78s dead time
        calc = TravelCalculator(travel_time_down=100.0, travel_time_up=100.0, startup_delay=0.78)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)

        # Move to 1% (1 second of travel + 0.78s dead time = 1.78s total relay time)
        calc.start_travel(1)
        self.assertTrue(calc.is_traveling())

        # At t = 1000.5s (within 0.78s dead time): position must still be 0
        calc.time_set_from_outside = 1000.5
        self.assertEqual(calc.current_position(), 0)
        self.assertFalse(calc.position_reached())

        # At t = 1000.78s (exact end of dead time): position still 0
        calc.time_set_from_outside = 1000.78
        self.assertEqual(calc.current_position(), 0)
        self.assertFalse(calc.position_reached())

        # At t = 1001.78s (0.78s dead time + 1.0s travel = 1.78s): position reached 1%
        calc.time_set_from_outside = 1001.78
        self.assertEqual(calc.current_position(), 1)
        self.assertTrue(calc.position_reached())

    def test_hold_10s_with_dead_time(self):
        # 100s travel time, 0.78s dead time
        calc = TravelCalculator(travel_time_down=100.0, travel_time_up=100.0, startup_delay=0.78)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)
        calc.start_travel_up()

        # Held for 10 seconds: from 1000.0 to 1010.0
        # Effective travel time = 10.0 - 0.78 = 9.22s -> 9%
        calc.time_set_from_outside = 1010.0
        self.assertEqual(calc.current_position(), 9)

        calc.stop()
        self.assertEqual(calc.last_known_position, 9)
        self.assertFalse(calc.is_traveling())


if __name__ == "__main__":
    unittest.main()
