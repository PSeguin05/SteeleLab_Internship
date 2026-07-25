# Cavity Theory

A Python class for computing and visualizing theoretical resonant modes of cylindrical microwave cavities.

This README was generated with the assistance of an LLM and reviewed by the author.

## Overview

`cavity_theory` computes the resonance frequencies of TM and TE modes in a cylindrical cavity as a function of its length, identifies mode crossings, and plots mode diagrams. It relies on the zeros of Bessel functions to derive the resonance frequencies.

## Dependencies

```
numpy
matplotlib
scipy
```

## Usage

```python
import numpy as np
from microwave_cavity import cavity_theory

# Define cavity parameters
radius = 25.0          # mm
lengths = np.linspace(63, 113, 100)  # mm
freq_window = [4.0, 12.0]            # GHz

thmodes = cavity_theory(
    radius = radius,
    lengths = lengths,
    freq_window = freq_window,
)

# Compute all modes
thmodes.compute_modes()

# Plot all modes
thmode.plot_modes()
```

### Context manager

```python
with cavity_theory(radius=50.0, lengths=lengths, freq_window=[1.0, 10.0]) as thmodes:
    thmodes.plot_modes()
```

## Constructor

```python
cavity_theory(
    radius,
    lengths = None,
    freq_window = None,
    data = None,
    nmax=5,
    lmax=5,
    mmax=9
)
```

| Parameter | Type | Description |
|---|---|---|
| `radius` | `float` | Cavity radius in mm |
| `lengths` | `np.ndarray` | Array of cavity lengths to sweep (mm) |
| `freq_window` | `np.ndarray` | Frequency range `[fmin, fmax]` in GHz |
| `data` | object | Optional pandas DataFrame with `length` and `freq` columns. Overrides `lengths` and `freq_window` if provided |
| `nmax` | `int` | Maximum azimuthal mode index n (default: 5) |
| `lmax` | `int` | Maximum radial mode index l (default: 5) |
| `mmax` | `int` | Maximum longitudinal mode index m (default: 9) |

> Either `data` **or** both `lengths` and `freq_window` must be provided.

## Methods

### `compute_modes()`

Computes all TM and TE resonant frequencies for the given parameter ranges. Results are stored in `self.dict_modes` as `{mode_label: [(length, freq), ...]}`.

Mode labels follow the convention `TM{n}{l}{m}` or `TE{n}{l}{m}`.

---

### `crossing_modes(threshold_length=2, threshold_freq=50e-3, min_modes=2)`

Identifies points in the mode diagram where at least `min_modes` distinct modes are in proximity, indicating a mode crossing. Results are stored in `self.dict_crossing`.

| Parameter | Description |
|---|---|
| `threshold_length` | Length scale for proximity detection (mm) |
| `threshold_freq` | Frequency scale for proximity detection (GHz) |
| `min_modes` | Minimum number of distinct modes to constitute a crossing |

---

### `non_crossing_modes(threshold_length=2, threshold_freq=50e-3, min_modes=2)`

Complement of `crossing_modes()`: identifies points where modes are isolated (no crossing). Results are stored in `self.dict_non_crossing`.

---

### `plot_modes(crossing=None, inverted_axis=False, colors=['blue', 'red'])`

Plots the mode diagram.

| Parameter | Description |
|---|---|
| `crossing` | `None` → plot all modes; `True` → crossing regions only; `False` → non-crossing regions only |
| `inverted_axis` | If `True`, swaps axes to plot frequency on x and length on y |
| `colors` | `[TE color, TM color]` (default: blue for TE, red for TM) |

## Mode frequency formula

The resonance frequency of mode (n, l, m) is given by:

$$f_{nlm} = \frac{c}{2\pi} \sqrt{\left(\frac{\alpha_{nl}}{R}\right)^2 + \left(\frac{m\pi}{L}\right)^2}$$

Where:
- $\alpha_{nl}$ is the $l$-th zero of $J_n$ (TM modes) or $J_n'$ (TE modes)
- $R$ is the cavity radius
- $L$ is the cavity length
- $c = 3 \times 10^8$ m/s

## Example output

```python
thmodes = cavity_theory(radius=25.0, lengths=np.linspace(63, 113, 100), freq_window=[4.0, 12.0])

thmodes.non_crossing_modes()
thmodes.plot_modes(crossing=False)

plt.xlabel("Length (mm)")
plt.ylabel("Frequency (GHz)")
plt.title("Non crossing modes")

plt.show()
```