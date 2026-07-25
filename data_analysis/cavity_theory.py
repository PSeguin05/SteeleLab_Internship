import numpy as np
import matplotlib.pyplot as plt

import re

from scipy.special import jn_zeros, jnp_zeros
from scipy.spatial import cKDTree

class cavity_modes:

    def __init__(self,
                 radius: float, # mm
                 lengths: np.ndarray = None, # mm
                 freq_window: np.ndarray = None, # GHz
                 data = None,
                 nmax: int = 4,
                 lmax: int = 4,
                 mmax: int = 9):
        
        self.radius = radius
        self.lengths = lengths
        if freq_window is not None:
            self.fmin = freq_window[0]
            self.fmax = freq_window[1]
        self.data = data
        self.nmax = nmax
        self.lmax = lmax
        self.mmax = mmax

    def omega_nlm(self,
                  n: int, l: int, m: int,
                  length: float,
                  Tmode: str) -> float:
    
        if Tmode == "TM":
            alpha = jn_zeros(n, l)[-1]

        elif Tmode == "TE":
            alpha = jnp_zeros(n, l)[-1]
        
        else:
            raise ValueError("Mode must be either 'TM' or 'TE'")
        
        return 3.0e8 * np.sqrt((alpha / (self.radius * 1e-3))**2 + (m * np.pi / length)**2)
    
    def compute_modes(self):
        
        if self.data is not None:
            lengths = self.data.length.values # mm
            freqs = self.data.freq.values # GHz
            fmin, fmax = np.min(freqs), np.max(freqs)
        else:
            lengths = self.lengths
            fmin, fmax = self.fmin, self.fmax
        
        self.dict_modes = {}
        
        for n in range(0, self.nmax + 1):
            for l in range(1, self.lmax + 1):
                TM_0 = []
                for length in lengths:
                    f0 = self.omega_nlm(n, l, 0, length*1e-3, "TM") / (2 * np.pi) * 1e-9
                    if fmin <= f0 and f0 <= fmax:
                        TM_0.append((length, f0))
                self.dict_modes[f"TM{n}{l}{0}"] = TM_0

                for m in range(1, 10):
                    TM_m, TE_m = [], []
                    for length in lengths:
                        f0 = self.omega_nlm(n, l, m, length*1e-3, "TM") / (2 * np.pi)* 1e-9
                        if fmin <= f0 and f0 <= fmax:
                            TM_m.append((length, f0))

                        f0 = self.omega_nlm(n, l, m, length*1e-3, "TE") / (2 * np.pi) * 1e-9
                        if fmin <= f0 and f0 <= fmax:
                            TE_m.append((length, f0))
                    self.dict_modes[f"TM{n}{l}{m}"] = TM_m
                    self.dict_modes[f"TE{n}{l}{m}"] = TE_m
    
    def crossing_modes(self,
                       threshold_length = 2,
                       threshold_freq = 50e-3,
                       min_modes = 2):
    
        branches = []
        mode_ids = []
        original_branches = []
        
        for mode_id, branche in self.dict_modes.items():
            for (length, freq) in branche:
                branches.append([length / threshold_length,
                                freq / threshold_freq])
                mode_ids.append(mode_id)
                original_branches.append((length, freq))
        
        branches = np.array(branches)
        n = len(branches)
        
        tree = cKDTree(branches)
        neighbors = tree.query_ball_point(branches, r=1.0)
        
        crossing_indices = set()
        
        for i in range(n):
            branches_in_contact = set()
            
            for j in neighbors[i]:
                if j == i:
                    continue
                branches_in_contact.add(mode_ids[j])
            
            branches_in_contact.add(mode_ids[i])
            
            if len(branches_in_contact) >= min_modes:
                crossing_indices.add(i)
        
        self.dict_crossing = {mode: [] for mode in self.dict_modes}
        
        for idx in crossing_indices:
            mode = mode_ids[idx]
            self.dict_crossing[mode].append(original_branches[idx])
    
    def non_crossing_modes(self,
                           threshold_length = 2,
                           threshold_freq = 50e-3,
                           min_modes = 2):
    
        branches = []
        mode_ids = []
        original_branches = []
        
        for mode_id, branche in self.dict_modes.items():
            for (length, freq) in branche:
                branches.append([length / threshold_length,
                                freq / threshold_freq])
                mode_ids.append(mode_id)
                original_branches.append((length, freq))
        
        branches = np.array(branches)
        n = len(branches)
        
        tree = cKDTree(branches)
        neighbors = tree.query_ball_point(branches, r=1.0)
        
        non_crossing_indices = set()
        
        for i in range(n):
            branches_in_contact = set()
            
            for j in neighbors[i]:
                if j == i:
                    continue
                branches_in_contact.add(mode_ids[j])
            
            branches_in_contact.add(mode_ids[i])
            
            if len(branches_in_contact) < min_modes:
                non_crossing_indices.add(i)
        
        # Reconstruction dictionnaire
        self.dict_noncrossing = {mode: [] for mode in self.dict_modes}
        
        for idx in non_crossing_indices:
            mode = mode_ids[idx]
            self.dict_noncrossing[mode].append(original_branches[idx])
    
    def plot_modes(self,
                   crossing: bool = None,
                   inverted_axis: bool = False,
                   colors = ['blue', 'red']):

        if crossing is None:
            used_dict = self.dict_modes
        else:
            if crossing:
                used_dict = self.dict_crossing
            else:
                used_dict = self.dict_noncrossing

        for mode_id, branche in used_dict.items():
            match = re.match(r'^(T[ME])(\d)(\d)(\d)$', mode_id)
            if match:
                typ = match.group(1)
                n = int(match.group(2))
                l = int(match.group(3))
                m = int(match.group(4))
            if typ=='TE':
                color=colors[0]
            else:
                color=colors[1]
                
            for j, (length, f0) in enumerate(branche):
                if inverted_axis:
                    plt.scatter(f0, length, color=color, marker='.', s=1)
                    if j == len(branche) - 1:
                        plt.text(f0,
                                length, 
                                f"{mode_id}",
                                fontsize=7,
                                color=color,
                                rotation=45) 
                else:
                    plt.scatter(length, f0, color=color, marker='.', s=1)
                    if j == len(branche) - 1:
                        plt.text(length+1,
                                f0, 
                                f"{mode_id}",
                                fontsize=7,
                                color=color,
                                rotation=0) 

