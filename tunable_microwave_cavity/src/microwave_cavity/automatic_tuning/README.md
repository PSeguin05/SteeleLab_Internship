# Automated Microwave Cavity Tuning

`automatic_tuning` is a Python class that orchestrates the complete tuning procedure of a tunable microwave cavity, combining a Vector Network Analyzer (VNA) and a motorized Zaber translation stage.

`automatic_tuning` only works with a Keysight FieldFox VNA. This version is probably less up-to-date compared to the PNA version.

`automatic_tuning_PNA` is an adaptation of the base script, such that it works with Keysight PNA.

---

## Overview

The workflow is divided into four sequential steps:

| Step | Description |
|------|-------------|
| 1 | **Cavity mapping** — Sweep the cavity length and record VNA traces |
| 2 | **Mode fitting** — Identify and fit cavity resonance modes |
| 3 | **Starting length estimation** — Estimate the cavity length that yields the target frequency |
| 4 | **Iterative optimization** — Converge the resonance to the target frequency |

---

## Requirements

- `numpy`, `xarray`, `tqdm`
- `dexplore` — data folder management (https://gitlab.tudelft.nl/steelelab/data-explorer.git)
- `analysis_functions.core` — Fitting VNA data (https://gitlab.tudelft.nl/steelelab/steele-lab-analysis-functions.git)
- `stlab` — VNA instrument driver (https://github.com/steelelab-delft/stlab.git)
- Internal modules:
  - `cavity_analysis`
  - `cavity_theory`
  - `zaber_control`

---

## Initialization

```python
tuner = automatic_tuning(
    f0 = 5.0e9, # Target frequency in Hz
    map_metadata = map_metadata, # Mapping configuration dict
    fit_metadata = fit_metadata, # Fitting configuration dict
    opt_metadata = opt_metadata, # Optimization configuration dict
    parameters = parameters, # Global experimental parameters
)
```

### `parameters` dict — required keys

| Key | Description |
|-----|-------------|
| `vna_ip` | IP address of the VNA |
| `zaber_port` | Serial port of the Zaber stage |
| `default_velocity` | Default stage velocity |
| `verb_vna` / `verb_zaber` | Verbosity flags |
| `total_cavity_length` | Total cavity length (mm) |
| `piston_thickness` | Piston thickness (mm) |
| `zaber_zero` | Zaber zero offset (mm) |
| `zaber_min` / `zaber_max` | Stage travel limits (mm) |
| `zaber_accuracy` | Stage positioning accuracy (mm) |
| `cavity_radius` | Cavity radius (mm) |
| `trace` | VNA measurement type (e.g. `"S21"`) |
| `vna_maxpoints` | Maximum VNA points per sweep (only used for FieldFox VNA)|
| `vna_auto_scale` | Auto-scale VNA display (bool) |
| `base_folder` | Root folder for data storage |
| `script_name` | Name of the calling script |

---

## Usage

### Step 1 — Cavity mapping

```python
tuner.cavity_map()
```

Sweeps the cavity length over all positions defined in `map_metadata['cavity_lengths']` and records a VNA trace at each step.

**`map_metadata` keys:**

| Key | Description |
|-----|-------------|
| `cavity_lengths` | Array of cavity lengths to sweep (mm) |
| `center_frequency` | VNA center frequency (Hz) |
| `span` | VNA span (Hz) |
| `points` | Number of frequency points |
| `power` | VNA output power (dBm) |
| `ifbw` | IF bandwidth (Hz) |
| `dataset_name` | HDF5 dataset name |
| `loop_name` | Loop parameter name |

---

### Step 2 — Mode fitting

**`fit_metadata` keys:**

| Key | Description |
|-----|-------------|
| `remove_edelay` | Remove electrical delay before fitting (list). See `analysis_functions` documentation for more details. |
| `span` | Frequency span around the theoretical points to fit the data from the cavity map. |
| `threshold_length` | Used to triger a warning if the starting length of the optimization is to close to the boudaries of the linear stage. |

```python
tuner.plot_cavity_map()                         # Visualize the map
tuner.fit_map(mode_ids=["TE101", "TE102"]) # Fit selected modes
```

`mode_ids` is optional — all available TE modes are fitted by default.

---

### Step 3 — Starting length estimation

```python
tuner.starting_length(mode_ids=["TE101", "TE102"])
# Output example:
# Mode: TE101 | Starting length: 42.314200 mm | Frequency resolution: 12.345 kHz
```

Performs a linear fit of each mode trajectory and estimates the cavity length expected to produce `f0`. Results are stored in `tuner.starting_lengths`.

---

### Step 4 — Optimization

```python
tuner.init_optimization()
tuner.optimization(mode_id="TE101")
```

Iteratively adjusts the cavity length until the measured resonance matches `center_frequency` of `opt_metadata` within the specified tolerance.

Usualy, `center_frequency`should be `f0`, but this option can be useful if one need to adapt the target frequency of few kHz.

The correction applied at each iteration is:

$$\Delta L = G \cdot \frac{f_{\mathrm{target}} - f_{\mathrm{measured}}}{df/dL}$$

where $G$ is the optimization gain.

**`opt_metadata` keys:**

| Key | Description |
|-----|-------------|
| `center_frequency` | Target frequency (Hz) |
| `span` | VNA span during optimization (Hz) |
| `points` | Number of frequency points |
| `power` | VNA output power (dBm) |
| `ifbw` | IF bandwidth (Hz) |
| `circle_fit` | Do a circle fit using `analysis_functions.core` if True. Else, perform an np.argmin to determine the resoannce frequency.(bool) |
| `threshold` | Convergence criterion (Hz) |
| `max_iter` | Maximum number of iterations |
| `max_movement` | Maximum allowed length correction per step (mm) |
| `gain` | Optimization gain $G$ |
| `remove_edelay` | Remove electrical delay before fitting (list). See `analysis_functions` documentation for more details. |
| `dataset_name` | HDF5 dataset name |
| `loop_name` | Loop parameter name |

**Important:** If `circle_fit` is False, be careful with `threshold` and `points`. The threshold cannot be smaller than the resolution of the VNA.

**Optimization results** are stored in `tuner.dict_main_params`:

```python
{
    "freq":   [...],   # Measured resonance frequencies (Hz)
    "length": [...],   # Cavity lengths (mm)
    "kt":     [...],   # Total coupling rates (Hz)
}
```

If `circle_fit` is False, `kt` list will be full of `np.nan`.

---

## Full example

```python
import numpy as np
from microwave_cavity import automatic_tuning

f0 = 5e9

params = {
    "vna_ip": "TCPIP::172.19.20.225",
    "zaber_port": "COM5",
    "default_velocity": 2.0,
    "verb_vna": False,
    "verb_zaber": False,
    "total_cavity_length": 152.0,
    "piston_thickness": 20.0,
    "zaber_zero": 19.0,
    "zaber_min": 0.0,
    "zaber_max": 50.0,
    "zaber_accuracy": 0.001,
    "cavity_radius": 25.0,
    "vna_measure": "S21",
    "vna_maxpoints": 10001,
    "vna_auto_scale": True,
    "base_folder": "/data/cavity/",
    "script_name": "tuning_script.py",
}

map_metadata = {
    "cavity_lengths": np.linspace(63, 113, 100),
    "center_frequency": f0,
    "bandwidth": 100e+06,
    "points": 5001,
    "power": -20,
    "ifbw": 10e+03,
    "dataset_name": "cavity_map",
    "loop_name": "Cavity length (mm)",
}

fit_metadata = {
    "bandwidth": 50e6,
    "remove_edelay": [0, 50, 0, 0],
    "threshold_length": 1.0,
}

opt_metadata = {
    "center_frequency": f0,
    "bandwidth": 10e6,
    "points": 10001,
    "power": -20,
    "ifbw": 10e+03,
    "circle_fit": True,
    "threshold": 5e3,
    "max_iter": 20,
    "max_movement": 1.0,
    "gain": 0.9,
    "remove_edelay": [0, 50, 0, 0],
    "dataset_name": "opt_trace",
    "loop_name": "Cavity length (mm)",
}

# Instantiate
tuner = automatic_tuning(f0, map_metadata, fit_metadata, opt_metadata, params)

# Step 1 — Map
tuner.cavity_map()

# Step 2 — Fit
tuner.plot_cavity_map()
tuner.fit_map()

# Step 3 — Estimate starting lengths
tuner.starting_length()

# Step 4 — Optimize
tuner.init_optimization()
tuner.optimization(mode_id="TE101")

tuner.close_devices()
```

---

## Notes

- The `_segmented_sweep` method automatically splits sweeps that exceed `vna_maxpoints` into multiple segments and merges them transparently. Only useful with FieldFox VNA. Not implemented for PNA (probably useless, PNA is very clever)
- The `FieldfoxPNA` driver is used by default. Adapting to another VNA requires modifying `__init__`, `init_vna`, `_segmented_sweep`, `_vna_measure`, and `_vna_measure_opt`.
- Always call `tuner.close_devices()` at the end of a session to release instrument connections.

## Known limitations / TODO
 
- **Optimization fit results are not persisted.** Currently, only the raw S21 data is saved to disk during optimization. While this is technically sufficient (the data can be re-fitted after the fact), it would be more convenient to directly serialize the fit results (resonance frequency, coupling rates, fit parameters) at each iteration. A dedicated save function for `list_fit_results` and  `dict_main_results` is planned.
- **Acquisition path list should be exported.** `list_full_path` is stored in memory during a session but not saved to disk. Persisting this list would make it much easier to locate a specific optimization iteration after the fact.
