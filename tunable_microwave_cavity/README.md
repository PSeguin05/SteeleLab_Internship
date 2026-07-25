# Tunable microwave cavity

## Description

This package is intended to provide a global set of functions for the tunable microwave cavity.

This project has been developed during Pacôme's internship, in order to build a microwave cavity to filter phase noise of a microwave source. The goal is to achieve ground state cooling for mechanical resonators, by reducing the number of added photons in the GHz cavity.

The project is currently in developing...

More stuff on this project can be found here:

https://gitlab.tudelft.nl/steelelab/internship-pacome.git

**Contact:** 

Since this internship is over and the author left the SteeleLab in July 2026, you can still contact him at [pacome.seguin@ens-lyon.fr](mailto:pacome.seguin@ens-lyon.fr), as long as the author has not completed their studies at the Ecole Normale Supérieure de Lyon (likely by 2028-2029).

**Reference:** 

Automated wide-ranged finely tunable microwave cavity for narrowband phase noise filtering

Joshi, Yash J. and Sauerwein, Nick and Youssefi, Amir and Uhrich, Philipp and Kippenberg, Tobias J.

10.1063/5.0034696

**Disclaimer:** 

All README files and doc strings were generated with the assistance of an LLM and reviewed by the author.


## Workflow
- Step 1: install the package
- Step 2: go through the example notebooks.
- Step 3: If you need more details, take a look to README files available for each function
- Step 4: you can use the cavity!

## Installation

```
git clone https://gitlab.tudelft.nl/steelelab/tunable_microwave_cavity.git
cd tunable_microwave_cavity
pip install -e .
```

**Important:** The name of the package to import functions is `microwave_cavity`.

## Dependencies

In order to use this package, you should also install these packages from SteeleLab :

- `stlab`: https://github.com/steelelab-delft/stlab
- `stlabutils`: https://github.com/steelelab-delft/stlabutils
- `dexplore`: https://gitlab.tudelft.nl/steelelab/data-explorer.git
- `analysis_functions`: https://gitlab.tudelft.nl/steelelab/steele-lab-analysis-functions.git

## Usage

Import the functions you need:
```
from microwave_cavity import zaber_control
from microwave_cavity import cavity_theory
from microwave_cavity import cavity_analysis
from microwave_cavity import automatic_tuning
```

## Overview

- `zaber_control` provides methods for connecting to a Zaber motion device, configuring motion parameters, performing absolute and relative movements, retrieving device information, and acquiring oscilloscope data from the controller.

- `cavity_theory` provides tools to compute the resonant frequencies of transverse electric (TE) and transverse magnetic (TM) modes in a cylindrical cavity as a function of its length. It also includes methods for identifying mode-crossing regions, separating crossing and non-crossing branches, and visualizing the resulting mode maps.

- `cavity_analysis` provides methods for fitting resonant modes identified from cavity simulations, extracting fit parameters from experimental data, performing simple linear regressions on mode trajectories, and visualizing the resulting mode characteristics.

- `automatic_tuning` orchestrates the complete tuning procedure of a tunable microwave cavity. It combines cavity mapping, theoretical mode calculation, resonance fitting, mode selection, and iterative frequency optimization using a Vector Network Analyzer (VNA) and a motorized Zaber translation stage.

