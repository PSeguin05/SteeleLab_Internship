import numpy as np
import matplotlib.pyplot as plt

from scipy.special import jn_zeros, jnp_zeros
from scipy.spatial import cKDTree

import re

from types import TracebackType
from typing import Type

class cavity_theory:
    """
    Electromagnetic mode theory for a cylindrical cavity.

    This class provides tools to compute the resonant frequencies of
    transverse electric (TE) and transverse magnetic (TM) modes in a
    cylindrical cavity as a function of its length. It also includes
    methods for identifying mode-crossing regions, separating crossing
    and non-crossing branches, and visualizing the resulting mode maps.

    Parameters
    ----------
    radius : float
        Cavity radius in millimeters.
    lengths : ndarray, optional
        Array of cavity lengths in millimeters.
        Required if `data` is not provided.
    freq_window : ndarray, optional
        Frequency window `[fmin, fmax]` in GHz used to filter the
        computed modes.
        Required if `data` is not provided.
    data : object, optional
        Dataset containing at least the attributes
        `length.values` and `freq.values`.
        If provided, cavity lengths and frequency limits are extracted
        automatically from the dataset.
    nmax : int, default=5
        Maximum azimuthal mode index `n`.
    lmax : int, default=5
        Maximum radial mode index `l`.
    mmax : int, default=9
        Maximum longitudinal mode index `m`.

    Attributes
    ----------
    dict_modes : dict
        Dictionary containing all computed cavity modes.
    dict_crossing : dict
        Dictionary containing only mode points associated with crossings.
    dict_non_crossing : dict
        Dictionary containing only mode points outside crossing regions.
    """

    def __init__(self,
                 radius: float, # mm
                 lengths: np.ndarray = None, # mm
                 freq_window: np.ndarray = None, # GHz
                 data = None,
                 nmax: int = 5,
                 lmax: int = 5,
                 mmax: int = 9):
        """
        Initialize a cylindrical cavity model.
        """
        
        self.radius = radius
        self.lengths = lengths
        if freq_window is not None:
            self.fmin = freq_window[0]
            self.fmax = freq_window[1]
        self.data = data
        if self.data is None:
            if self.lengths is None:
                raise ValueError("Either lengths or data must be provided")
            if freq_window is None:
                raise ValueError("Either freq_window or data must be provided")
        self.nmax = nmax
        self.lmax = lmax
        self.mmax = mmax

        self._compute_modes_done = False
        self._crossing_modes_done = False
        self._non_crossing_modes_done = False
    
    def __enter__(self
                  ) -> "cavity_theory":
        """
        Enter the context manager.

        Returns
        -------
        cavity_theory
            Current instance of the class.
        """

        return self
    
    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_val: BaseException,
                 exc_tb: TracebackType
                 ) -> bool:
        """
        Exit the context manager.

        Parameters
        ----------
        exc_type : Type[BaseException]
            Type of the exception raised within the context block.
        exc_val : BaseException
            Exception instance.
        exc_tb : TracebackType
            Traceback information associated with the exception.

        Returns
        -------
        bool
            Always returns `False` so that exceptions are propagated.
        """
                 
        return False
    
    def __repr__(self
                 ) -> str:
        """
        Return a string representation of the object.

        Returns
        -------
        str
            String describing the main cavity parameters.
        """

        return (f"cavity_theory(radius={self.radius} mm,\n"
                f"lengths={self.lengths} mm,\n"
                f"freq_window=({self.fmin}, {self.fmax}) GHz,\n" 
                f"nmax={self.nmax}, lmax={self.lmax}, mmax={self.mmax})")

    def omega_nlm(self,
                  n: int,
                  l: int,
                  m: int,
                  length: float,
                  Tmode: str) -> float:
        """
        Compute the angular frequency of a cavity mode.

        Parameters
        ----------
        n : int
            Azimuthal mode index.
        l : int
            Radial mode index.
        m : int
            Longitudinal mode index.
        length : float
            Cavity length in meters.
        Tmode : {"TM", "TE"}
            Electromagnetic mode type.

        Returns
        -------
        float
            Angular frequency of the mode in rad/s.

        Raises
        ------
        ValueError
            If `Tmode` is neither `"TM"` nor `"TE"`.

        Notes
        -----
        The resonant frequency is computed using the zeros of the Bessel
        functions (TM modes) or their derivatives (TE modes).
        """
    
        if Tmode == "TM":
            alpha = jn_zeros(n, l)[-1]

        elif Tmode == "TE":
            alpha = jnp_zeros(n, l)[-1]
        
        else:
            raise ValueError("Mode must be either 'TM' or 'TE'")
        
        return 3.0e8 * np.sqrt((alpha / (self.radius * 1e-3))**2 + (m * np.pi / length)**2)
    
    def compute_modes(self):
        """
        Compute all TE and TM cavity modes within the specified frequency
        window.

        Resonant frequencies are evaluated for all combinations of mode
        indices `(n, l, m)` within the limits defined by `nmax`, `lmax`,
        and `mmax`.

        Results
        -------
        dict_modes : dict
            Dictionary whose keys are mode identifiers
            (e.g. ``TM110`` or ``TE213``) and whose values are lists of
            `(length, frequency)` pairs.

        Notes
        -----
        Frequencies are expressed in GHz.
        """
        
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
        self._compute_modes_done = True
    
    def crossing_modes(self,
                       threshold_length = 2,
                       threshold_freq = 50e-3,
                       min_modes = 2):
        """
        Identify points belonging to mode crossings.

        Two points are considered neighbors when their normalized distance
        in the `(length, frequency)` space is smaller than one.

        Parameters
        ----------
        threshold_length : float, default=2
            Length normalization scale in mm.
        threshold_freq : float, default=50e-3
            Frequency normalization scale in GHz.
        min_modes : int, default=2
            Minimum number of distinct modes locally present for a point
            to be classified as part of a crossing.

        Results
        -------
        dict_crossing : dict
            Dictionary containing points associated with mode crossings.
        """
        
        if not self._compute_modes_done:
            self.compute_modes()
    
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

        self._crossing_modes_done = True
    
    def non_crossing_modes(self,
                           threshold_length = 2,
                           threshold_freq = 50e-3,
                           min_modes = 2):
        """
        Identify points that do not belong to mode crossings.

        Parameters
        ----------
        threshold_length : float, default=2
            Length normalization scale in mm.
        threshold_freq : float, default=50e-3
            Frequency normalization scale in GHz.
        min_modes : int, default=2
            Minimum number of distinct modes defining a crossing region.

        Results
        -------
        dict_non_crossing : dict
            Dictionary containing points located outside crossing regions.
        """
        
        if not self._compute_modes_done:
            self.compute_modes()
    
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
        self.dict_non_crossing = {mode: [] for mode in self.dict_modes}
        
        for idx in non_crossing_indices:
            mode = mode_ids[idx]
            self.dict_non_crossing[mode].append(original_branches[idx])
        
        self._non_crossing_modes_done = True
    
    def plot_modes(self,
                   crossing: bool = None,
                   inverted_axis: bool = False,
                   colors = ['blue', 'red'],
                   used_dict: dict = None,
                   ax = None,
                   **kwargs):
        """
        Plot the computed mode branches.

        Parameters
        ----------
        crossing : bool or None, default=None
            - `None`: plot all computed modes.
            - `True`: plot only crossing points.
            - `False`: plot only non-crossing points.
        inverted_axis : bool, default=False
            If True, swap the frequency and length axes.
        colors : list of str, default=['blue', 'red']
            Colors used for TE and TM modes, respectively.
        used_dict : dict, optional
            Dictionary of modes to plot. If not provided, it is selected
            automatically according to the value of `crossing`.

        Notes
        -----
        Mode identifiers are displayed at the end of each plotted branch.
        """

        if ax is None:
            fig, ax = plt.subplots()

        if crossing is None:
            if not self._compute_modes_done:
                self.compute_modes()
            used_dict = self.dict_modes
        else:
            if crossing:
                if not self._crossing_modes_done:
                    self.crossing_modes()
                used_dict = self.dict_crossing
            else:
                if not self._non_crossing_modes_done:
                    self.non_crossing_modes()
                used_dict = self.dict_non_crossing

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
                    ax.scatter(f0, length, color=color, **kwargs)
                    if j == len(branche) - 1:
                        ax.text(f0,
                                length, 
                                f"{mode_id}",
                                fontsize=7,
                                color=color,
                                rotation=45) 
                else:
                    ax.scatter(length, f0, color=color, **kwargs)
                    if j == len(branche) - 1:
                        ax.text(length+1,
                                f0, 
                                f"{mode_id}",
                                fontsize=7,
                                color=color,
                                rotation=0)