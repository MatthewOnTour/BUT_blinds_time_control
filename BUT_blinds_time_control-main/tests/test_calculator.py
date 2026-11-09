import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "blinds_controller")))

from calculator import TravelCalculator, PositionType, TravelStatus


class TestTravelCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = TravelCalculator(travel_time_down=30.0, travel_time_up=30.0, startup_delay=0.0)
        self.calc.time_set_from_outside = 1000.0

    def test_initial_state(self):
        self.assertEqual(self.calc.current_position(), 0)
        self.assertFalse(self.calc.is_traveling())
        self.assertTrue(self.calc.is_closed())

    def test_start_travel_up(self):
        self.calc.set_position(0)
        self.calc.start_travel_up()
        self.assertTrue(self.calc.is_traveling())
        self.assertEqual(self.calc.travel_direction, TravelStatus.DIRECTION_UP)

        # After 15 seconds (halfway of 30s)
        self.calc.time_set_from_outside = 1015.0
        self.assertEqual(self.calc.current_position(), 50)
        self.assertFalse(self.calc.position_reached())

        # After 30 seconds
        self.calc.time_set_from_outside = 1030.0
        self.assertEqual(self.calc.current_position(), 100)
        self.assertTrue(self.calc.position_reached())
        self.assertTrue(self.calc.is_open())

    def test_start_travel_down(self):
        self.calc.set_position(100)
        self.calc.start_travel_down()

        # After 15 seconds
        self.calc.time_set_from_outside = 1015.0
        self.assertEqual(self.calc.current_position(), 50)

        # After 30 seconds
        self.calc.time_set_from_outside = 1030.0
        self.assertEqual(self.calc.current_position(), 0)
        self.assertTrue(self.calc.position_reached())
        self.assertTrue(self.calc.is_closed())

    def test_different_up_and_down_times(self):
        calc = TravelCalculator(travel_time_down=20.0, travel_time_up=40.0, startup_delay=0.0)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)
        calc.start_travel_up()

        calc.time_set_from_outside = 1020.0  # 20s of 40s -> 50%
        self.assertEqual(calc.current_position(), 50)

        calc.stop()
        self.assertEqual(calc.last_known_position, 50)

        calc.start_travel_down()
        calc.time_set_from_outside = 1025.0  # 5s of down (total 10s from 50% to 0%) -> 25%
        self.assertEqual(calc.current_position(), 25)

        calc.time_set_from_outside = 1030.0  # 10s of down -> 0%
        self.assertEqual(calc.current_position(), 0)
        self.assertTrue(calc.position_reached())

    def test_startup_delay(self):
        calc = TravelCalculator(travel_time_down=30.0, travel_time_up=30.0, startup_delay=1.0)
        calc.time_set_from_outside = 1000.0
        calc.set_position(0)
        calc.start_travel_up()

        # At 0.5s (within startup delay), position should still be 0
        calc.time_set_from_outside = 1000.5
        self.assertEqual(calc.current_position(), 0)

        # At 16.0s (1.0s delay + 15.0s effective travel -> 50%)
        calc.time_set_from_outside = 1016.0
        self.assertEqual(calc.current_position(), 50)

        # At 31.0s (1.0s delay + 30.0s effective travel -> 100%)
        calc.time_set_from_outside = 1031.0
        self.assertEqual(calc.current_position(), 100)
        self.assertTrue(calc.position_reached())

    def test_travel_to_same_position(self):
        self.calc.set_position(50)
        self.calc.start_travel(50)
        self.assertEqual(self.calc.current_position(), 50)
        self.assertTrue(self.calc.position_reached())
        self.assertFalse(self.calc.is_traveling())

    def test_intermediate_stop(self):
        self.calc.set_position(0)
        self.calc.start_travel_up()
        self.calc.time_set_from_outside = 1010.0  # 10s -> 33%
        self.assertEqual(self.calc.current_position(), 33)
        self.calc.stop()
        self.assertEqual(self.calc.last_known_position, 33)
        self.assertEqual(self.calc.current_position(), 33)
        self.assertFalse(self.calc.is_traveling())

    def test_zero_travel_time_protection(self):
        calc = TravelCalculator(travel_time_down=0.0, travel_time_up=0.0)
        calc.set_position(0)
        calc.start_travel_up()
        self.assertEqual(calc.current_position(), 100)
        self.assertTrue(calc.position_reached())


if __name__ == "__main__":
    unittest.main()
