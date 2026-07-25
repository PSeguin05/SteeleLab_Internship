# Zaber Control — Python Controller

A Python class to control **Zaber linear motor stages** over a serial connection. It wraps the [Zaber Motion Library](https://software.zaber.com/motion-library/docs/tutorials/install/py) to provide a clean, safe, high-level interface for homing, absolute/relative motion, sinusoidal motion, and built-in oscilloscope data capture.

This README was generated with the assistance of an LLM and reviewed by the author.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Class Reference](#class-reference)
  - [Constructor](#constructor-__init__)
  - [Connection Management](#connection-management)
  - [Driver Control](#driver-control)
  - [Motion Control](#motion-control)
  - [Oscilloscope](#oscilloscope)
- [Attribute Reference](#attribute-reference)
- [Console Output](#console-output)
- [Typical Workflows](#typical-workflows)
- [Notes & Gotchas](#notes--gotchas)

---

## Requirements

| Dependency | Purpose |
|---|---|
| `zaber-motion` | Official Zaber Python SDK |
| `numpy` | Array conversion in `scope_save()` result |
| `csv` | Built-in — CSV file writing |
| `logging` | Built-in — structured log output |

The class relies on the following imports:

```python
import csv
import logging
import numpy as np
from typing import Type
from types import TracebackType

from zaber_motion.ascii import Connection
from zaber_motion import Units
```

---

## Installation

```bash
pip install zaber-motion
```

Connect your Zaber stage to a USB/serial port and identify its port name:

| OS | Example port |
|---|---|
| Windows | `COM3`, `COM5`, … |
| Linux | `/dev/ttyUSB0` |
| macOS | `/dev/cu.usbserial-…` |

---

## Quick Start

```python
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import time

from zaber_control import zaber_control
# (or you can paste the zaber_control class here)

# Recommended: use the context manager so the port is always released
with zaber_control(port="COM5", label="Zaber Motor") as zaber:
    zaber.move_absolute(25.0)
    zaber.move_relative(5.0)
    pos = zaber.get_position()
```

---

## Class Reference

### Constructor `__init__`

```python
zaber_control(
    port: str,
    label: str = "Zaber",
    axis_number: int = 1,
    auto_home: bool = True,
    auto_close: bool = True,
    default_velocity: float = 1,
    default_acceleration: float = None,
    wait_until_idle: bool = True,
    verb: bool = True
)
```

Opens the serial connection, detects the device, enables the driver if needed, optionally homes the axis, optionally automatically close the connection when leaving a `with` statement, and prepares the onboard oscilloscope.

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `port` | `str` | — | Serial port name. **Required.** |
| `label` | `str` | `"Zaber Motor"` | Name used in every log message. Useful when controlling multiple stages simultaneously. |
| `axis_number` | `int` | `1` | Axis index on the device (1-based). Use `1` for single-axis devices. |
| `auto_home` | `bool` | `False` | If `True`, the stage homes immediately on construction. |
| `auto_close` | `bool` | `True` | If `True`, automatically close the connection when leaving a `with` statement. |
| `default_velocity` | `float` | `1` | Set a default velocity for every functions. If `None`, automatically use the internal default velocity. |
| `default_acceleration` | `float` | `None` | Set a default acceleration for every functions. If `None`, automatically use the internal default acceleration. |
| `wait_until_idle` | `bool` | `True` | If `True`, every motion command blocks until the stage is idle. Set `False` for non-blocking calls. |
| `verb` | `bool` | `True` | If `True`, show every log. |

**Important:** if `auto_home` is `True`, it will perform a homing at the **internal default speed** of the motor, even if you set an default_velocity, which is **6 mm/s**. 

#### Raises

| Exception | Condition |
|---|---|
| `RuntimeError` | No Zaber device found on the specified port. |
| `ConnectionFailedException` | Serial connection cannot be opened. |
| `InvalidArgumentException` | Axis number invalid for the detected device. |
| `CommandFailedException` | A device command fails during init or homing. |

#### Example

```python
# Single stage, blocking motion
zaber = zaber_control(port="COM5", label="Zaber Motor")
```

---

### Connection Management

#### `close()`

```python
zaber.close()
```

Closes the serial connection and releases the COM port. Always call this when done — or use the `with` statement to have it called automatically.

#### Context manager (`with` statement) — recommended

```python
with zaber_control(port="COM5", label="Zaber Motor") as zaber:
    zaber.move_absolute(30.0)
# If auto_close = True, zaber.close() is called here automatically, even if an exception occurred
```

`__enter__` returns the instance; `__exit__` calls `close()` if `auto_close=True` and lets any exception propagate normally.

---

### Driver Control

The motor driver must be **enabled** before any motion command. It can be **disabled** to cut current to the coils when the stage is idle, reducing heat and power consumption.

#### `enable()`

```python
zaber.enable()
```

Enables the motor driver. Must be called before any motion if the driver is off.

#### `disable()`

```python
zaber.disable()
```

Disables the motor driver. The stage holds its last position in firmware but coils are de-energised.

---

### Motion Control

All positions are in **mm**, velocities in **mm/s**, accelerations in **mm/s²**. Blocking behaviour is controlled by `wait_until_idle` set at construction.

Every motion method automatically:
- checks that the target position is within the stage travel limits (`_check_bounds`)
- checks that the target velocity is within the stage limits (`_check_velocity`)
- checks that the target acceleration is within the stage limits (`_check_acceleration`)
- checks that the motor driver is enabled (`_assert_enabled`)

The three first checks all called together with `_check_parameters`

**Important:** You are not supposed to call these guards yourself.

---

#### `home()`

```python
zaber.home()
```

Moves the stage to its reference (home) position. Blocks if `wait_until_idle=True`.

**Raises:** `RuntimeError` if the driver is disabled.

**Important:** Homing at the **internal default speed** of the motor, even if you set an default_velocity, which is **6 mm/s**. 

---

#### `get_position()`

```python
pos = zaber.get_position()  # → float (mm)
```

Returns and logs the current axis position in millimetres.

**Returns:** `float` — position in mm.

---

#### `get_params()`

```python
params = zaber.get_params()  # → dict
```

Returns and prints the main motion parameters and limits of the controlled axis.

**Returns:** `dict` — parameters.

| Parameter | Value |
|---|---|
| Minimum position | 0.000 000 mm |
| Positioning accuracy | 0.020 000 mm |
| Maximum position | 50.800 016 mm |
| Minimum velocity | 0.000 029 mm/s|
| Default velocity | 5.999 866 mm/s |
| Maximum velocity | 26.000 000 mm/s |
| Default acceleration | 59.589 386 mm/s^2 |
| Maximum acceleration | 100.000 000 mm/s^2 |

Default values are used if no specific velocity or acceleration is provided, or if `default_velocity=None`, `default_acceleration=None`, in `move_absolute`, `move_relative`, `move_min` and `move_max`.

The minimum velocity corresponds to the speed resolution of the motor (from the official specifications)

**Important:** The maximum velocity from axis settings is 30.480 000 mm/s. However, the official specifications recommend staying below 26.000 000 mm/s. 

**Important:** There is no official value for the maximum acceleration. The author decided that 100.000 000 mm/s^2 is more than enough in order to avoid any loss of precision. You can change this limit yourself in the function `get_params`: `acceleration_max = 100`.

---

#### `move_absolute(position, velocity=None, acceleration=None)`

```python
zaber.move_absolute(
    position,            # target position in mm
    velocity=None,       # optional, mm/s
    acceleration=None    # optional, mm/s²
)
```

Moves to an **absolute** position from the home reference.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `position` | `float` | — | Target position in mm. **Required.** |
| `velocity` | `float` | `None` | Max speed in mm/s. Uses device default if omitted, or default_velocity if not `None`. |
| `acceleration` | `float` | `None` | Ramp acceleration in mm/s². Uses device default if omitted, or default_acceleration if not `None`.. |

**Raises:** `ValueError` if out of range; `RuntimeError` if driver disabled.

```python
zaber.move_absolute(20.0)
zaber.move_absolute(20.0, velocity=2.0, acceleration=1.0)
```

---

#### `move_relative(delta_position, velocity=None, acceleration=None)`

```python
zaber.move_relative(
    delta_position,      # displacement in mm (negative = toward home)
    velocity=None,
    acceleration=None
)
```

Moves **relative** to the current position. The resulting absolute position is bounds-checked before motion starts.

**Raises:** `ValueError` if resulting position out of range; `RuntimeError` if driver disabled.

```python
zaber.move_relative(5.0)    # 5 mm forward
zaber.move_relative(-2.5)   # 2.5 mm backward
```

---

#### `move_min(velocity=None, acceleration=None)`

Moves to the **minimum travel limit**.

**Raises:** `RuntimeError` if driver disabled.

---

#### `move_max(velocity=None, acceleration=None)`

Moves to the **maximum travel limit**.

**Raises:** `RuntimeError` if driver disabled.

---

#### `wait_until_idle()`

```python
zaber.wait_until_idle()
```

Blocks until the axis reports idle. Useful when `wait_until_idle=False` is set at construction and you need to synchronise at a specific point:

```python
stazaberge = zaber_control(port="COM5", wait_until_idle=False)
zaber.enable()
zaber.move_absolute(40.0)   # returns immediately
# ... do other work ...
zaber.wait_until_idle()     # block here until motion finishes
```

---

### Oscilloscope

The Zaber device has an onboard **oscilloscope** that samples position (and optionally velocity) at a configurable rate. No external hardware needed.

**Workflow:**

```
scope_config() → scope_start() → [motion] → scope_stop() → scope_save()
```

After `scope_save()`, the configuration flag resets — call `scope_config()` again before the next acquisition.

`_assert_scope_configured()` checks that the oscilloscope has been configured when calling `scope_start()`, `scope_stop()`and `scope_save()`.

**Important:** You never need to call this guard yourself.

---

#### `scope_config(interval=1e-2, save_velocity=False)`

```python
zaber.scope_config(
    interval=1e-2,        # sampling period in seconds
    save_velocity=False   # also record velocity channel
)
```

Configures the oscilloscope. **Must be called before `scope_start()`.**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `interval` | `float` | `0.01` | Time between samples in seconds. |
| `save_velocity` | `bool` | `False` | If `True`, adds a velocity channel (halves max recordable duration). |

Prints the maximum recordable duration based on device buffer and interval.

The oscilloscope can save a maximum of 6144 points:

| Interval | Maximum duration (1 channel) |
|---|---|
| $10^{-3}$ s | $6.144$ s |
| $10^{-2}$ s | $\approx$ 1 min |
| $10^{-1}$ s | $\approx$ 10 min |
| 1 s | $\approx$ 1h42 |
| 10 s | $\approx$ 17h |
| 1 min | $\approx$ 102h |

**Important:** If `save_velocity=True` (i.e. 2 channels), the maximum duration is devided by two!

```python
zaber.scope_config(interval=5e-3, save_velocity=True)
# [X-Axis] Scope maximum duration = 5.120 s
```

---

#### `scope_start()`

```python
zaber.scope_start()
```

Starts acquisition. Call just **before** the motion to record.

**Raises:** `RuntimeError` if `scope_config()` was not called.

---

#### `scope_stop()`

```python
zaber.scope_stop()
```

Stops acquisition. Call **after** motion completes or to end early.

**Raises:** `RuntimeError` if `scope_config()` was not called.

---

#### `scope_save(filename="Scope.csv", save_csv=True, return_dict=True)`

```python
data = zaber.scope_save(
    filename="Scope.csv",   # output file path
    save_csv=True,          # write CSV file
    return_dict=True        # return data as dict
)
```

Reads the oscilloscope buffer, optionally writes a CSV, optionally returns the data.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `filename` | `str` | `"Scope.csv"` | Output file path. |
| `save_csv` | `bool` | `True` | Write data to CSV. |
| `return_dict` | `bool` | `True` | Return data as a dictionary. |

**Returns** (when `return_dict=True`):

| Key | Type | Unit | Description |
|---|---|---|---|
| `"time"` | `np.ndarray` | s | Sample timestamps |
| `"position"` | `np.ndarray` | mm | Position samples |
| `"velocity"` | `np.ndarray` | mm/s | Velocity samples (only if `save_velocity=True` in `scope_config`) |
| `"timebase"` | `float` | s | Sampling interval |
| `"frequency"` | `float` | Hz | Sampling frequency |
| `"delay"` | `float` | s | Acquisition delay |

**CSV format (position only):**
```
Time (s),Position (mm)
0.000,0.000000
0.005,0.523412
```

**CSV format (with velocity):**
```
Time (s),Position (mm),Velocity (mm/s)
0.000,0.000000,0.000000
0.005,0.523412,52.341200
```

**Raises:** `RuntimeError` if `scope_config()` was not called.

> After this call, `_scope_configured` resets to `False`. You must call `scope_config()` again before the next acquisition.

---

## Attribute Reference

| Attribute | Type | Description |
|---|---|---|
| `port` | `str` | Serial port name. |
| `label` | `str` | Label used in log messages. |
| `axis_number` | `int` | Axis index (1-based). |
| `wait` | `bool` | Blocking behaviour for motion commands. |
| `save_velocity` | `bool` | Set by `scope_config()`. `True` if velocity channel is active. |
| `time_interval_scope` | `float` | Sampling interval set by `scope_config()`. |
| `connection` | `Connection` | Active Zaber serial connection. |
| `devices` | `list` | All devices detected on the port. |
| `device` | `Device` | First detected device (`devices[0]`). |
| `axis` | `Axis` | Axis object used for all motion commands. |
| `scope` | `Oscilloscope` | Device oscilloscope object. |
| `logger` | `Logger` | Python logger named after `label`. |
| `_scope_configured` | `bool` | Internal — `True` after `scope_config()`, reset after `scope_save()`. |

---

## Console Output

With the default `basicConfig` format, a full session looks like (if `verb=True`):

```
[Zaber Motor] 1 device(s) detected
[Zaber Motor] Driver ENABLE
[Zaber Motor] Homing...
[Zaber Motor] Homed
[Zaber Motor] READY!
[Zaber Motor] Driver ENABLE
[Zaber Motor] Position = 0.000000 mm
[Zaber Motor] Scope maximum duration = 10.240 s
[Zaber Motor] Scope STARTED
[Zaber Motor] Scope STOPPED
[Zaber Motor] Reading scope data...
[Zaber Motor] Saving CSV file...
[Zaber Motor] CSV file saved: run1.csv
[Zaber Motor] Driver DISABLE
[Zaber Motor] Connection closed.
```

To silence all info messages:
```python
zaber.verb = False
```

---

## Typical Workflows

### 1 — Simple point-to-point move

```python
with zaber_control(port="COM5", label="Zaber Motor") as zaber:
    zaber.move_absolute(30.0)
    zaber.get_position()
```

### 2 — Record a motion profile to CSV

```python
with zaber_control(port="COM5", label="Zaber Motor") as zaber:
    zaber.scope_config(interval=5e-3, save_velocity=True)
    zaber.scope_start()
    zaber.move_absolute(20.0, velocity=5.0, acceleration=2.0)
    zaber.scope_stop()
    data = zaber.scope_save("profile_run1.csv")

import matplotlib.pyplot as plt
plt.plot(data["time"], data["position"])
plt.xlabel("Time (s)")
plt.ylabel("Position (mm)")
plt.show()
```

### 3 — Get data without saving a file

```python
with zaber_control(port="COM5", label="Zaber Motor") as zaber:
    zaber.scope_config(interval=1e-3)
    zaber.scope_start()
    zaber.move_absolute(30.0)
    zaber.scope_stop()
    data = zaber.scope_save(save_csv=False, return_dict=True)

print(data["frequency"], "Hz")
print(data["position"].mean(), "mm mean")
```

---

## Notes & Gotchas

- **Enable before moving.** All motion methods (`home`, `move_absolute`, `move_relative`, `move_min`, `move_max`) call `_assert_enabled()` internally and raise `RuntimeError` immediately if the driver is off.
- **Oscilloscope resets after `scope_save()`.** The `_scope_configured` flag goes back to `False`. Call `scope_config()` again before the next acquisition.
- **Velocity channel halves buffer time.** When `save_velocity=True`, the device shares its buffer between two channels. Always check the logged duration after `scope_config()`.
- **`wait_until_idle=False` is your responsibility.** Issuing a second move before the first finishes may cause unexpected behaviour. Use `wait_until_idle()` to synchronise explicitly.