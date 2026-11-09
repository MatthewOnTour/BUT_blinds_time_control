"""Calculator for time-based cover positions."""
import time
from enum import Enum


class PositionType(Enum):
    """Enum class for different type of calculated positions."""
    UNKNOWN = 1
    CALCULATED = 2
    CONFIRMED = 3


class TravelStatus(Enum):
    """Enum class for travel status."""
    DIRECTION_UP = 1
    DIRECTION_DOWN = 2
    STOPPED = 3


class TravelCalculator:
    """Class for calculating the current position of a cover based on travel time."""

    def __init__(self, travel_time_down: float, travel_time_up: float, startup_delay: float = 0.0):
        """Initialize TravelCalculator class."""
        self.position_type = PositionType.UNKNOWN
        self.position_closed = 0
        self.position_open = 100
        self.last_known_position = self.position_closed

        self.travel_time_down = max(0.0, float(travel_time_down))
        self.travel_time_up = max(0.0, float(travel_time_up))
        self.startup_delay = max(0.0, float(startup_delay))

        self.travel_to_position = self.position_closed
        self.travel_started_time = 0.0
        self.travel_direction = TravelStatus.STOPPED

        self.time_set_from_outside = None

    def clamp(self, position: int | float) -> int:
        """Clamp position to [position_closed, position_open]."""
        return int(round(max(self.position_closed, min(self.position_open, position))))

    def set_position(self, position: int):
        """Set known position of cover."""
        clamped_pos = self.clamp(position)
        self.last_known_position = clamped_pos
        self.travel_to_position = clamped_pos
        self.travel_direction = TravelStatus.STOPPED
        self.position_type = PositionType.CONFIRMED

    def stop(self):
        """Stop traveling and freeze position."""
        self.last_known_position = self.current_position()
        self.travel_to_position = self.last_known_position
        self.position_type = PositionType.CONFIRMED
        self.travel_direction = TravelStatus.STOPPED

    def start_travel(self, travel_to_position: int):
        """Start traveling to position."""
        target = self.clamp(travel_to_position)
        self.stop()
        self.travel_started_time = self.current_time()
        self.travel_to_position = target

        if target == self.last_known_position:
            self.travel_direction = TravelStatus.STOPPED
            self.position_type = PositionType.CONFIRMED
            return

        self.position_type = PositionType.CALCULATED
        self.travel_direction = (
            TravelStatus.DIRECTION_UP
            if target > self.last_known_position
            else TravelStatus.DIRECTION_DOWN
        )

    def start_travel_up(self):
        """Start traveling up to fully open (100%)."""
        self.start_travel(self.position_open)

    def start_travel_down(self):
        """Start traveling down to fully closed (0%)."""
        self.start_travel(self.position_closed)

    def current_position(self) -> int:
        """Return current (calculated or known) position."""
        if self.position_type == PositionType.CALCULATED:
            return self._calculate_position()
        return self.last_known_position

    def is_traveling(self) -> bool:
        """Return if cover is actively traveling."""
        if self.travel_direction == TravelStatus.STOPPED:
            return False
        return not self.position_reached()

    def position_reached(self) -> bool:
        """Return if cover has reached designated position."""
        if self.travel_direction == TravelStatus.STOPPED:
            return True
        return self.current_position() == self.travel_to_position

    def is_open(self) -> bool:
        """Return if cover is (fully) open."""
        return self.current_position() == self.position_open

    def is_closed(self) -> bool:
        """Return if cover is (fully) closed."""
        return self.current_position() == self.position_closed

    def travel_time_between(self, from_pos: int, to_pos: int, include_startup: bool = True) -> float:
        """Calculate the travel time in seconds between two positions."""
        rel = self.clamp(to_pos) - self.clamp(from_pos)
        base_time = self._calculate_travel_time(rel)
        if base_time > 0 and include_startup:
            return base_time + self.startup_delay
        return base_time

    def remaining_travel_time(self) -> float:
        """Calculate the remaining time in seconds to reach designated position."""
        if self.travel_direction == TravelStatus.STOPPED:
            return 0.0

        rel = self.travel_to_position - self.last_known_position
        total_travel_time = self._calculate_travel_time(rel)
        if total_travel_time == 0:
            return 0.0

        elapsed_time = self.current_time() - self.travel_started_time
        effective_elapsed_time = max(0.0, elapsed_time - self.startup_delay)
        remaining = total_travel_time - effective_elapsed_time
        return max(0.0, remaining)

    def _calculate_position(self) -> int:
        """Return calculated position."""
        if self.travel_direction == TravelStatus.STOPPED:
            return self.last_known_position

        elapsed_time = self.current_time() - self.travel_started_time
        if elapsed_time < self.startup_delay:
            return self.last_known_position

        effective_elapsed_time = elapsed_time - self.startup_delay
        relative_position = self.travel_to_position - self.last_known_position
        travel_time = self._calculate_travel_time(relative_position)

        if travel_time <= 0:
            return self.travel_to_position

        if effective_elapsed_time >= travel_time:
            return self.travel_to_position

        progress = effective_elapsed_time / travel_time
        position = self.last_known_position + relative_position * progress
        return self.clamp(position)

    def _calculate_travel_time(self, relative_position: int) -> float:
        """Calculate time to travel to relative position."""
        if relative_position == 0:
            return 0.0

        travel_direction = (
            TravelStatus.DIRECTION_UP
            if relative_position > 0
            else TravelStatus.DIRECTION_DOWN
        )
        travel_time_full = (
            self.travel_time_up
            if travel_direction == TravelStatus.DIRECTION_UP
            else self.travel_time_down
        )
        travel_range = self.position_open - self.position_closed

        if travel_range <= 0 or travel_time_full <= 0:
            return 0.0

        return travel_time_full * abs(relative_position) / travel_range

    def current_time(self) -> float:
        """Get current time. May be modified from outside (for unit tests)."""
        if self.time_set_from_outside is not None:
            return self.time_set_from_outside
        return time.time()

    def __eq__(self, other):
        """Equal operator."""
        if not isinstance(other, TravelCalculator):
            return False
        return self.__dict__ == other.__dict__
