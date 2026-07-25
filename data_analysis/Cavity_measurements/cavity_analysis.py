import numpy as np
import xarray as xr
import re
import sys
import os
sys.path.append(os.path.abspath("steele-lab-analysis-functions"))
import analysis_functions.core as af
from collections import defaultdict

class cavity_analysis:

    def __init__(self,
                 data,
                 radius: float):
        self.data = data
        self.radius = radius
        self.model = af.ComplexCircle()
    
    def fit_branches(self,
                    bandwidth: float,
                    dict_modes: dict,
                    mode_ids: np.ndarray = None):
        
        freqs = self.data.freq.values
        lengths = self.data.length.values

        self.dict_fits = {}
        mask_np = np.zeros((len(lengths), len(freqs)), dtype=bool)

        if mode_ids is None:
            # Fit all TE modes
            for mode_id, branche in dict_modes.items():
                match = re.match(r'^(T[ME])(\d)(\d)(\d)$', mode_id)
                if match:
                    mode_type = match.group(1)

                if mode_type == 'TE':
                    for (length, f0) in branche:
                        fmin, fmax = f0 - bandwidth, f0 + bandwidth
                        data_fit = self.data.sel(length=length, freq=slice(fmin, fmax))

                        try:
                            fit_result = af.fit_single(self.model,
                                                       data_fit.freq.values,
                                                       data_fit.cpx.values,
                                                       guess = None)
                            self.dict_fits[f"{mode_id}|{length}"] = fit_result

                            lidx = np.where(lengths==length)[0][0]
                            fidx = np.isin(freqs, data_fit.freq.values)
                            mask_np[lidx, fidx] = True
                        except Exception as e:
                            print(f"[{mode_id} | {length:.3f} mm | {f0:.3f} GHz] Fit Error: {e}")
        else:
            for mode_id in mode_ids:
                # Fit given TE modes
                branche = dict_modes[mode_id]
                for (length, f0) in branche:
                    fmin, fmax = f0 - bandwidth/2, f0 + bandwidth/2
                    data_fit = self.data.sel(length = length,
                                             freq = slice(fmin, fmax))
                    
                    try:
                        fit_result = af.fit_single(self.model,
                                                    data_fit.freq.values,
                                                    data_fit.cpx.values,
                                                    guess = None)
                        self.dict_fits[f"{mode_id}|{length}"] = fit_result

                        lidx = np.where(lengths==length)[0][0]
                        fidx = np.isin(freqs, data_fit.freq.values)
                        mask_np[lidx, fidx] = True
                    except Exception as e:
                        print(f"[{mode_id} | {length:.3f} mm | {f0:.3f} GHz] Fit Error: {e}")
        
        self.mask_xr = xr.DataArray(mask_np,
                                    coords = {'length': self.data.length, 'freq': self.data.freq},
                                    dims = ['length', 'freq'])
    
    def plot_masked_branches(self):

        data_masked = self.data.mag.where(self.mask_xr)

        ax = data_masked.plot(cmap = 'RdBu_r',
                              add_colorbar = True).axes
        
        valid_freq = self.mask_xr.any(dim='length')
        valid_length = self.mask_xr.any(dim='freq')

        freqs = self.data.freq.values[valid_freq.values]
        lengths = self.data.length.values[valid_length.values]

        ax.set_xlim(lengths.min(), lengths.max())
        ax.set_ylim(freqs.min(), freqs.max())

    def compute_fit_results(self):

        self.dict_results = defaultdict(lambda: defaultdict(list))

        for key, fit in self.dict_fits.items():
            mode_id, length = key.split("|")

            fit_values = {}
            fit_values['length'] = float(length)

            for name in fit.params.keys():
                fit_values[name] = fit.params[name].value
            
            for name, value in fit_values.items():
                self.dict_results[mode_id][name].append(value)