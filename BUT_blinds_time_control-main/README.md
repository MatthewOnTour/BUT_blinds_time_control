# Blinds Controller (Enhanced Time-Based Cover)

[![Validate with hassfest](https://github.com/YanBad/BUT_blinds_time_control/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/YanBad/BUT_blinds_time_control/actions/workflows/hassfest.yaml)
[![HACS Validation](https://github.com/YanBad/BUT_blinds_time_control/actions/workflows/validate.yaml/badge.svg)](https://github.com/YanBad/BUT_blinds_time_control/actions/workflows/validate.yaml)

A reliable, feature-rich custom integration for Home Assistant that provides precise time-based control for motorized blinds, roller shutters, and external venetian blinds (Raffstoren) that lack native physical position sensors.

Fork of the original [BUT_blinds_time_control](https://github.com/MatthewOnTour/BUT_blinds_time_control) with major stability fixes, dead-time (Totzeit) and stop-delay (Nachlaufzeit) compensation, and hardware-accurate push-button behavior.

---

## Key Features

* **Standard Cover Controls**: Full support for Open, Close, Stop, and Set Position (0% – 100%).
* **Tilt / Slat Support**: Optional support for tilting venetian blind slats (0% – 100%), with automatic slat coordination during full travel.
* **Dead Time (Totzeit) & Stop Delay (Nachlaufzeit) Compensation**:
  * **Dead Time (`dead_time`, default 0.78s)**: Motor controllers often have an internal response delay between relay click and the motor actually starting to move.
  * **Stop Delay (`stop_delay`, default 0.15s)**: When the relay turns off, the motor coasts for ~0.1s – 0.3s before coming to a complete standstill.
  * **Exact Timing Formula**:
    $$\text{Relay-ON Time} = T_{\text{desired\_move}} + \text{dead\_time} - \text{stop\_delay}$$
    *(e.g., to move for $1.0\text{s}$, the relay is energized for $1.0 + 0.78 - 0.15 = 1.63\text{s}$!)*
  * For manual wall button holds, the net delay ($\text{dead\_time} - \text{stop\_delay}$) is subtracted so that position tracking accurately reflects only the exact time the motor was moving.
* **Lockout Time / Sperrzeit Protection (Default: 0.2s)**:
  * Hardware motors often treat tiny pulses (e.g. ~0.1s) as a signal to run continuously to the end position.
  * Home Assistant will **never** send a command shorter than `sperrzeit`, preventing accidental full-travel pulses when micro-adjustments are commanded.
  * Physical button presses $\le \text{sperrzeit}$ (e.g. 0.1s) are correctly recognized as intentional full-travel pulses and tracked all the way to 0% or 100%.
  * Tapping any button while moving immediately stops the motion.
* **Echo / Feedback Loop Prevention**: State changes triggered by Home Assistant service commands are tracked and suppressed so they do not falsely trigger external switch handlers.
* **End-Stop Over-Travel & Drift Elimination**: Optional extra run time (`overtravel_time`, default 1.0s) when reaching 0% or 100% to guarantee the motor reaches its internal limit switch, firmly confirming the position and preventing cumulative timing errors.
* **Configurable Interlock Delay**: Protects motor windings and relay contacts by enforcing a safety pause (default 0.2s) when reversing direction.
* **State Restoration**: Remembers the exact position and tilt after a Home Assistant restart.
* **Manual Recalibration**: Built-in services to set known position or tilt directly.
* **Multi-Language UI**: Fully localized in English and German.

---

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations**, click the three dots in the top right, and select **Custom repositories**.
3. Add the repository URL `https://github.com/YanBad/BUT_blinds_time_control` and select category **Integration**.
4. Click **Install** on the `Blinds control` card.
5. Restart Home Assistant.

### Manual Installation

1. Download or copy the `custom_components/blinds_controller` directory.
2. Place it into your Home Assistant configuration folder: `<config>/custom_components/blinds_controller/`.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings -> Devices & Services**.
2. Click **Add Integration** and search for **Blinds control**.
3. Fill in the configuration options:

| Setting | Description | Default |
| :--- | :--- | :--- |
| **Name** | Custom name for your cover entity. | `Living Room Blinds` |
| **Switch Entity UP** | Switch or relay entity controlling UP movement. | *(Required)* |
| **Switch Entity DOWN** | Switch or relay entity controlling DOWN movement. | *(Required)* |
| **Travel Time UP** | Actual motor travel time in seconds for a full open cycle. | `30.0` |
| **Travel Time DOWN** | Actual motor travel time in seconds for a full close cycle. | `30.0` |
| **Dead Time (Totzeit)** | Internal delay before the motor engages (measured at ~0.78s). Added to movements. | `0.78` |
| **Stop Delay (Nachlaufzeit)** | Time the motor coasts after relay turn-off until standstill (0.1s – 0.3s). Subtracted from relay time. | `0.15` |
| **Lockout Time (Sperrzeit)** | Commands $\le$ this duration are blocked by HA to prevent triggering full-travel pulses. Physical taps $\le$ this trigger full travel. | `0.2` |
| **End-Stop Overtravel** | Extra runtime on 0% and 100% to ensure physical limit switch contact and recalibrate position. | `1.0` |
| **Interlock Delay** | Safety delay when switching directions to protect relays and motor. | `0.2` |
| **Tilt Time OPEN** | Time in seconds to tilt from closed to open (`0.0` disables tilt). | `0.0` |
| **Tilt Time CLOSE** | Time in seconds to tilt from open to closed (`0.0` disables tilt). | `0.0` |
| **Send STOP at End** | Automatically sends a STOP (turn off) command once target position is reached. | `true` |

All options can be adjusted anytime by clicking **Configure** on the integration card.

---

## Services

### `blinds_controller.set_known_position`
Manually set the current position of the blinds without moving the motor. Useful if the blinds were moved manually or during maintenance.
```yaml
service: blinds_controller.set_known_position
target:
  entity_id: cover.living_room_blinds
data:
  position: 100
```

### `blinds_controller.set_known_tilt_position`
Manually set the current tilt position of the slats without moving the motor.
```yaml
service: blinds_controller.set_known_tilt_position
target:
  entity_id: cover.living_room_blinds
data:
  position: 50
```

---

## License

This project is licensed under the MIT License - see the `LICENSE.md` file for details.
