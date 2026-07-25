# Cavity Analysis

A Python class for fitting and analyzing resonant modes of cylindrical microwave cavities from experimental S-parameter data.

This README was generated with the assistance of an LLM and reviewed by the author.

## Overview

`cavity_analysis` takes measured data (complex transmission/reflection as a function of frequency and cavity length) and fits each resonant mode branch using a circle model in the complex plane. It then extracts physical parameters such as resonance frequency $f_0$ and total linewidth $\kappa_t$, and provides several visualization tools.

This class is designed to work alongside `cavity_theory`, which provides the theoretical mode predictions used as input to the fitting routine.

## Dependencies

```
numpy
matplotlib
xarray
scipy
analysis_functions # SteeleLab internal library
```

`analysis_functions` can be found here: https://gitlab.tudelft.nl/steelelab/steele-lab-analysis-functions.git

## Usage

```python
import numpy as np
from microwave_cavity import cavity_analysis
from microwave_cavity import cavity_theory

# Load your xarray Dataset with dims: length (mm), freq (GHz), cpx, mag
data = ...  # xr.Dataset

# Get theoretical mode predictions
thmodes = cavity_theory(radius=25.0, data=data)
thmodes.compute_modes()

# Run analysis
analysis = cavity_analysis(data=data, radius=25.0)

# Fit all TE mode branches
analysis.fit_branches(bandwidth=50e-3, dict_modes=thmodes.dict_modes)

# Extract fit parameters
analysis.compute_fit_results()

# Plot
analysis.plot_data_results(x='f0', y='kt', s=5)
```

## Constructor

```python
cavity_analysis(data, radius)
```

| Parameter | Type | Description |
|---|---|---|
| `data` | `xr.Dataset` | Measured dataset with coordinates `freq` (GHz), `length` (mm) and variables `cpx` (complex signal) and `mag` (magnitude) |
| `radius` | `float` | Cavity radius in mm |

## Methods

### `fit_branches(bandwidth, dict_modes, mode_ids=None)`

Fits a circle model to each point of the specified mode branches in the complex plane.

| Parameter | Type | Description |
|---|---|---|
| `bandwidth` | `float` | Frequency window (GHz) centered on each mode frequency used for fitting |
| `dict_modes` | `dict` | Mode dictionary from `cavity_theory.dict_modes`, `dict_crossing`, or `dict_non_crossing` |
| `mode_ids` | `list` or `None` | If `None`, fits all TE modes. Otherwise, fits only the listed mode labels (e.g. `['TE011', 'TE012']`) |

Fit results are stored in `self.dict_fits` as `{"{mode_id}|{length}": fit_result}`.
A boolean mask `self.mask_xr` (xarray DataArray) is also built to track which (length, freq) points were fitted.

Failed fits are caught and printed without interrupting the loop.

---

### `plot_masked_branches(ax=None, **kwargs)`

Plots the magnitude data masked to only show the fitted frequency windows, using a `RdBu_r` colormap. Axes are automatically zoomed to the fitted region.

---

### `compute_fit_results()`

Parses `self.dict_fits` and organizes fit parameter values into `self.dict_results`, a nested dict structured as:

```python
self.dict_results[mode_id][param_name] = [value_at_length_1, value_at_length_2, ...]
```

Always includes `'length'` as a key alongside the fitted model parameters (e.g. `'f0'`, `'kt'`, ...).

---

### `linear_fit_modes(mode_ids=None)`

Fits a linear polynomial (degree 1) to the $f_0$ vs. length relationship for each mode. Usefull whenthe observation bandwith is small (< 50 MHz), such as modes can be approximated with linear fits.

This function is mainly used for the automatic tuning of the cavity: `automatic_tuning`

| Parameter | Description |
|---|---|
| `mode_ids` | List of mode labels to fit. If `None`, fits all modes in `dict_results` |

Results are stored in `self.dict_polynoms` as `{mode_id: np.poly1d coefficients}`.

---

### `plot_data_results(x, y, ax=None, **kwargs)`

Plot the data with the requested x-axis and y-axis. There are three possibilities for `x` and `y`: `"length"`, `"f0"` and `"kt"`. All data are in GHz

## Data format

The input `data` is expected to be an `xr.Dataset` with at minimum:

```
Dimensions:  (length: N, freq: M)
Coordinates:
  * length   (mm)
  * freq     (GHz)
Data variables:
    cpx      (length, freq)  complex128  — complex S-parameter
    mag      (length, freq)  float64     — magnitude (e.g. |S21| in dB)
```

## Example workflow

```python
import matplotlib.pyplot as plt
from microwave_cavity import cavity_theory
from microwave_cavity import cavity_analysis

data = ...  # load your xr.Dataset

# Theory
thmodes = cavity_theory(radius=25.0, data=data)
thmodes.crossing_modes()

# Analysis — fit only crossing TE modes
analysis = cavity_analysis(data=data, radius=50.0)

analysis.fit_branches(bandwidth=0.05, dict_modes=ct.dict_crossing)

analysis.compute_fit_results()
analysis.linear_fit_modes()

analysis.plot_masked_branches()
plt.show()

analysis.plot_data_results(x='f0', y='kt', s=5)
plt.show()
```