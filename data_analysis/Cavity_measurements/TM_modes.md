---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.15.2
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

```python
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import Normalize
import dexplore as dx 
import xarray as xr
import os
import sys
import glob
import stlabutils
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import pprint
import lmfit

sys.path.append(os.path.abspath("steele-lab-analysis-functions"))
import analysis_functions.core as af

from lmfit import Model, Parameters
import matplotlib.ticker as ticker
from scipy.constants import hbar
```

# blablabla

```python
dx.refresh_bokeh()
```

```python
base_folder = '/home/jovyan/steelelab/measurement_data/4KDIY/Pacome/Overcoupling_TM_Modes'
```

```python
file_folder = '2026-06-12_16.26.06_0009_VNA_Measure'
full_path = base_folder + '/' + file_folder
h5_files = sorted(glob.glob(full_path + '/*.h5'))

data = xr.load_dataset(h5_files[0])

dx.interactive_linecut(data, initial_datavar=2)
dx.interactive_linecut_and_colormap(data, initial_var=2)
#dx.plot_colormap(data, dataset=2)
data

translator = {'Frequency (Hz)':['freq', 'GHz', 1e9],
              'Cavity length (mm)':['length', 'mm', 1]}

data = af.format_data_xarray(
    data=data, 
    tool='VNA',
    translator=translator,
    remove_edelay=[0,100,0,0])

fig, ax = plt.subplots(2, 1,figsize=(10,4))
ax[0].plot(data.freq.values, data.mag.values)
ax[1].plot(data.freq.values, data.arg.values, color='orange')
ax[1].set_xlabel('Frequency [GHz]')
ax[1].set_ylabel('Phase [rad]')
ax[0].set_ylabel('Amplitude [dB]')
fig.suptitle('0009')
fig.tight_layout()
```

```python
file_folder = '2026-06-12_16.27.45_0010_VNA_Measure'
full_path = base_folder + '/' + file_folder
h5_files = sorted(glob.glob(full_path + '/*.h5'))

data = xr.load_dataset(h5_files[0])

dx.interactive_linecut(data, initial_datavar=2)
dx.interactive_linecut_and_colormap(data, initial_var=2)
#dx.plot_colormap(data, dataset=2)
data

translator = {'Frequency (Hz)':['freq', 'GHz', 1e9],
              'Cavity length (mm)':['length', 'mm', 1]}

data = af.format_data_xarray(
    data=data, 
    tool='VNA',
    translator=translator,
    remove_edelay=[0,100,0,0])

fig, ax = plt.subplots(2, 1,figsize=(10,4))
ax[0].plot(data.freq.values, data.mag.values)
ax[1].plot(data.freq.values, data.arg.values, color='orange')
ax[1].set_xlabel('Frequency [GHz]')
ax[1].set_ylabel('Phase [rad]')
ax[0].set_ylabel('Amplitude [dB]')
fig.suptitle('0010')
fig.tight_layout()
```

```python
file_folder = '2026-06-12_16.56.42_0025_VNA_Measure'
full_path = base_folder + '/' + file_folder
h5_files = sorted(glob.glob(full_path + '/*.h5'))

data = xr.load_dataset(h5_files[0])

dx.interactive_linecut(data, initial_datavar=2)
dx.interactive_linecut_and_colormap(data, initial_var=2)
#dx.plot_colormap(data, dataset=2)
data

translator = {'Frequency (Hz)':['freq', 'GHz', 1e9],
              'Cavity length (mm)':['length', 'mm', 1]}

data = af.format_data_xarray(
    data=data, 
    tool='VNA',
    translator=translator,
    remove_edelay=[0,100,0,0])

fig, ax = plt.subplots(2, 1,figsize=(10,4))
ax[0].plot(data.freq.values, data.mag.values)
ax[1].plot(data.freq.values, data.arg.values, color='orange')
ax[1].set_xlabel('Frequency [GHz]')
ax[1].set_ylabel('Phase [rad]')
ax[0].set_ylabel('Amplitude [dB]')
fig.suptitle('0025')
fig.tight_layout()
```
