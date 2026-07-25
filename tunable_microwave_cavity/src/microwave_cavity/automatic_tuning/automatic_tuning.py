import numpy as np

from tqdm import tqdm
import math
import glob

import xarray as xr

from types import TracebackType
from typing import Type

from dexplore.data_folder import DataFolder
from stlab.devices.FieldfoxPNA import FieldfoxPNA
import analysis_functions.core as af

from ..cavity_analysis import cavity_analysis
from ..cavity_theory import cavity_theory
from ..zaber_control import zaber_control

class automatic_tuning:
    """
    Automated cavity tuning workflow.

    This class orchestrates the complete tuning procedure of a tunable
    microwave cavity. It combines cavity mapping, theoretical mode
    calculation, resonance fitting, mode selection, and iterative
    frequency optimization using a Vector Network Analyzer (VNA) and a
    motorized Zaber translation stage.

    The workflow is divided into four main steps:

    1. Acquisition of a cavity frequency map.
    2. Identification and fitting of cavity modes.
    3. Determination of suitable starting lengths.
    4. Iterative optimization toward a target resonance frequency.

    Parameters
    ----------
    f0 : float
        Target resonance frequency in Hz.
    map_metadata : dict
        Configuration parameters used for cavity mapping measurements.
    fit_metadata : dict
        Configuration parameters used for resonance fitting and mode
        extraction.
    opt_metadata : dict
        Configuration parameters used during the optimization process.
    parameters : dict
        Global experimental parameters including instrument addresses,
        cavity geometry, stage calibration constants, and acquisition
        settings.

    Attributes
    ----------
    f0 : float
        Target resonance frequency in Hz.
    map_metadata : dict
        Parameters used during cavity mapping.
    fit_metadata : dict
        Parameters used during mode fitting and analysis.
    opt_metadata : dict
        Parameters used during frequency optimization.
    parameters : dict
        Global experimental configuration.
    devices : dict
        Dictionary containing instrument instances.
    dfol : DataFolder
        Data storage manager used for measurement acquisition.
    data_xr : xarray.Dataset
        Formatted cavity map dataset.
    thmodes : cavity_theory
        Theoretical cavity mode calculator.
    analysis : cavity_analysis
        Experimental cavity analysis object.
    starting_lengths : dict
        Estimated cavity lengths corresponding to the target frequency
        for each available mode.
    dict_main_params : dict
        Optimization history containing measured frequencies, cavity
        lengths, and coupling rates.
    list_data_opt : list
        List of datasets acquired during optimization.
    list_fit_results : list
        List of resonance fit results obtained during optimization.
    list_full_path : list
        List of acquisition directories created during optimization.
    """

    # ---------------------------------------------------------------------
    # Initialization and device management
    # ---------------------------------------------------------------------

    def __init__(self,
                 f0: float,
                 map_metadata: dict,
                 fit_metadata: dict,
                 opt_metadata: dict,
                 parameters: dict,):
        """
        Initialize the automatic tuning workflow.

        Parameters
        ----------
        f0 : float
            Target resonance frequency in Hz.
        map_metadata : dict
            Mapping acquisition parameters.
        fit_metadata : dict
            Resonance fitting parameters.
        opt_metadata : dict
            Optimization parameters.
        parameters : dict
            Experimental configuration and instrument settings.

        Notes
        -----
        This function may need some changes if another VNA is used.
        """
        
        
        self.f0 = f0
        self.map_metadata = map_metadata
        self.fit_metadata = fit_metadata
        self.opt_metadata = opt_metadata
        self.parameters = parameters
    
        self.devices = {}

        self.devices['VNA'] = FieldfoxPNA(self.parameters['vna_ip'],
                                          reset = True,
                                          verb = self.parameters['verb_vna'],
                                          mode = 'NA')

        self.devices['Zaber'] = zaber_control(port = self.parameters['zaber_port'],
                                              label = "Zaber",
                                              axis_number = 1,
                                              auto_home = False,
                                              auto_close = True,
                                              default_velocity = self.parameters['default_velocity'],
                                              wait_until_idle = True,
                                              verb = self.parameters['verb_zaber'])
    
    def __enter__(self
                  ) -> "automatic_tuning":
        """
        Enter the context manager.

        Returns
        -------
        automatic_tuning
            Current instance of the class.
        """

        return self
    
    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_val: BaseException,
                 exc_tb: TracebackType
                 ) -> bool:
        """
        Exit the context manager and close all connected devices.

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
        self.close_devices()
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

        return (f"automatic_tuning(f0={self.f0} mm,\n mapping metadata: {self.map_metadat},\n fitting metadata: {self.fit_metadata},\n optimization metadata: {self.opt_metadata})")
    
    def init_vna(self):
        """
        Initialize the Vector Network Analyzer connection.

        Notes
        -----
        This function may need some changes if another VNA is used.
        """

        self.devices['VNA'] = FieldfoxPNA(self.parameters['vna_ip'],
                                          reset = True,
                                          verb = self.parameters['verb_vna'],
                                          mode = 'NA')
    
    def init_zaber(self):
        """
        Initialize the Zaber translation stage connection.
        """
        
        self.devices['Zaber'] = zaber_control(port = self.parameters['zaber_port'],
                                              label = "Zaber",
                                              axis_number = 1,
                                              auto_home = False,
                                              auto_close = True,
                                              default_velocity = self.parameters['default_velocity'],
                                              wait_until_idle = True,
                                              verb = self.parameters['verb_zaber'])
    
    def _init_dfol(self):
        """
        Initialize the data storage folder used for measurements.
        """

        self.dfol = DataFolder(self.parameters['base_folder'],
                               script_full_path = self.parameters['base_folder'] + self.parameters['script_name'])
    
    def close_devices(self):
        """
        Close all active instrument connections.
        """

        self.devices['VNA'].close()
        self.devices['Zaber'].close()


    # ---------------------------------------------------------------------
    # Step 1 - Cavity mapping
    # ---------------------------------------------------------------------

    def _check_cavity_lengths(self):
        """
        Verify that all requested cavity lengths lie within the mechanical
        limits of the tuning system.

        Raises
        ------
        ValueError
            If at least one requested cavity length is outside the allowed
            range.
        """

        cavity_length = self.parameters['total_cavity_length']
        piston_thickness = self.parameters['piston_thickness']
        zaber_zero = self.parameters['zaber_zero']

        position_zero = cavity_length - piston_thickness - zaber_zero

        cavity_min = position_zero - self.parameters['zaber_max']
        cavity_max = position_zero - self.parameters['zaber_min']

        if np.min(self.map_metadata['cavity_lengths']) < cavity_min or np.max(self.map_metadata['cavity_lengths']) > cavity_max:
            raise ValueError(f'Cavity lengths out of range: Max range = [{cavity_min:.6f}, {cavity_max:.6f}] mm')

    def _convert_zaber(self):
        """
        Convert cavity lengths into corresponding Zaber stage positions.

        Notes
        -----
        The conversion depends on the cavity geometry and calibration
        parameters stored in ``parameters``.
        """

        cavity_length = self.parameters['total_cavity_length']
        piston_thickness = self.parameters['piston_thickness']
        zaber_zero = self.parameters['zaber_zero']

        position_zero = cavity_length - piston_thickness - zaber_zero

        self.zaber_positions = position_zero - self.map_metadata['cavity_lengths']
    
    def _segmented_sweep(self,
                         metadata: dict):
        """
        Perform a segmented VNA sweep.

        If the requested number of frequency points exceeds the maximum
        number supported by the instrument, the sweep is divided into
        multiple contiguous segments and the results are merged into a
        single dataset.

        Parameters
        ----------
        metadata : dict
            Sweep configuration containing at least the center frequency,
            bandwidth, and number of points.

        Returns
        -------
        dict
            Dictionary containing the merged VNA trace.
        
        Notes
        -----
        This function may need some changes if another VNA is used.
        """
        
        # If nb_points < nb_max
        if metadata['points'] <= self.parameters['vna_maxpoints']:
            self.devices['VNA'].SetCenter(metadata['center_frequency'])
            self.devices['VNA'].SetSpan(metadata['bandwidth'])
            self.devices['VNA'].SetPoints(metadata['points'])
            
            return self.devices['VNA'].MeasureScreen()
        
        # If nb_points > nb_max
        n_segments = math.ceil(metadata['points'] / self.parameters['vna_maxpoints'])

        full_freq = np.linspace(metadata['center_frequency'] - metadata['bandwidth']/2,
                                metadata['center_frequency'] + metadata['bandwidth']/2,
                                metadata['points'])
        
        split_idx = np.linspace(0, metadata['points'],
                                n_segments + 1,
                                dtype = int)
        
        merged_data = None

        for i in range(n_segments):
            idx_start = split_idx[i]
            idx_stop = split_idx[i+1]

            freq_segment = full_freq[idx_start:idx_stop]

            seg_start = freq_segment[0]
            seg_stop = freq_segment[-1]
            seg_nbpoints = len(freq_segment)

            # Configure VNA
            self.devices['VNA'].SetCenter((seg_start + seg_stop) / 2)
            self.devices['VNA'].SetSpan(seg_stop - seg_start)
            self.devices['VNA'].SetPoints(seg_nbpoints)

            data = self.devices['VNA'].MeasureScreen()

            # Merged
            if merged_data is None:
                merged_data = data
            else:
                for key in data.keys():
                    merged_data[key] = np.concatenate((merged_data[key], data[key][1:]))

        return merged_data
    
    def _vna_measure(self):
        """
        Acquire a complete cavity map.

        The cavity length is swept over all requested positions while a VNA
        trace is recorded at each position and stored in an HDF5 dataset.

        Notes
        -----
        The measurement configuration is taken from ``map_metadata``.

        This function may need some changes if another VNA is used.
        """

        self._init_dfol()

        dataset_name = self.map_metadata['dataset_name']
        loop_name = self.map_metadata['loop_name']

        self._check_cavity_lengths()
        self._convert_zaber()

        self.devices['VNA'].write('CALC:PAR:COUN 1')
        self.devices['VNA'].write('INST:SEL "NA"')
        self.devices['VNA'].write(f"CALC:PAR1:DEF {self.parameters['trace']}")
        self.devices['VNA'].SetPower(self.map_metadata['power'])
        self.devices['VNA'].SetIFBW(self.map_metadata['ifbw'])

        for i, position in enumerate(tqdm(self.zaber_positions)):

            self.devices['Zaber'].move_absolute(position = position)
            print(f"Cavity length: {self.map_metadata['cavity_lengths'][i]:.6f} mm")
            
            data = self._segmented_sweep(metadata = self.map_metadata)
            if self.parameters['vna_auto_scale']:
                self.devices['VNA'].write("DISP:WIND:TRAC1:Y:AUTO")

            # Create the dataset if it doesn't exist
            if dataset_name not in self.dfol.datasets.keys():
                data_names = list(data.keys())[1:]
                sweep_name = list(data.keys())[0]
                sweep_values = data[sweep_name]
                self.dfol.create_stlab_dataset(
                    dataset_name,
                    data_names,
                    sweep_name,
                    sweep_values,
                    loop_name,
                    self.map_metadata['cavity_lengths'],)
            
            # Insert the latest trace into the dataset
            self.dfol.datasets[dataset_name].attrs.update(self.map_metadata)
            self.dfol.add_stlab_trace(dataset_name, data, i)
    
    # Run the cavity mapping and save the data in a HDF5 file
    
    def cavity_map(self,
                   map_metadata: dict = None):
        """
        Run a complete cavity mapping measurement.

        Parameters
        ----------
        map_metadata : dict, optional
            Mapping parameters overriding the current configuration.

        Notes
        -----
        Measurement results are automatically saved to disk.
        """

        if map_metadata is not None:
            self.map_metadata = map_metadata

        print('Cavity mapping...')
        print(f"Center frequency: {self.map_metadata['center_frequency'] * 1e-09:.9f} GHz")
        print(f"VNA bandwidth: {self.map_metadata['bandwidth'] * 1e-06:.6f} MHz")

        self._vna_measure()

        print('Cavity mapping done.')
    

    # ---------------------------------------------------------------------
    # Step 2 - Mode fitting
    # ---------------------------------------------------------------------

    def _import_map_data(self,
                         full_path: str = None):
        """
        Load a cavity map and initialize analysis objects.

        Parameters
        ----------
        full_path : str, optional
            Directory containing the HDF5 cavity map. If not provided,
            the most recently acquired dataset is used.

        Notes
        -----
        This method initializes:

        - ``data_xr``
        - ``thmodes``
        - ``analysis``

        and computes the theoretical cavity modes.
        """
        
        if full_path is None:
            full_path = self.dfol.folder_full_path

        h5_files = sorted(glob.glob(full_path + '/*.h5'))

        self.data = xr.load_dataset(h5_files[0])

        translator = {'Frequency (Hz)':['freq', 'GHz', 1e9],
                      'Cavity length (mm)':['length', 'mm', 1]}
        
        self.data_xr = af.format_data_xarray(
            data = self.data,
            tool = 'VNA',
            translator = translator,
            remove_edelay = self.fit_metadata['remove_edelay']
            )
        
        self.thmodes = cavity_theory(
            radius = self.parameters['cavity_radius'],
            data = self.data_xr)
        
        self.analysis = cavity_analysis(
            data = self.data_xr,
            radius = self.parameters['cavity_radius']
        )

        self.thmodes.compute_modes()
    
    def _plot_map(self,
                 plot_theory: bool = True):
        """
        Display the cavity map.

        Parameters
        ----------
        plot_theory : bool, default=True
            If True, overlay theoretical cavity modes.
        """
        
        self.data_xr.mag.plot(cmap='RdBu_r')

        if plot_theory:
            self.thmodes.plot_modes(
                crossing = None,
                colors = ['blue', 'green'])

    def _fit_branches(self,
                      mode_ids: list = None,
                      plot_mask: bool = False):
        """
        Fit resonances along selected cavity mode branches.

        Parameters
        ----------
        mode_ids : list, optional
            List of mode identifiers to fit.
            If omitted, all available TE modes are fitted.
        plot_mask : bool, default=False
            If True, display the fitted regions of the map.
        """
        
        self.analysis.fit_branches(
            bandwidth = self.fit_metadata['bandwidth'] * 1e-09, # GHz
            dict_modes = self.thmodes.dict_modes,
            mode_ids = mode_ids
        )

        if plot_mask:
            self.analysis.plot_masked_branches()
    
    def _compute_results(self,
                         plot: bool = True):
        """
        Compute and optionally visualize fitted mode parameters.

        Parameters
        ----------
        plot : bool, default=True
            If True, generate summary plots of the fitted results.
        """
        
        self.analysis.compute_fit_results()

        if plot:
            self.analysis.plot_data_results()
    
    def plot_cavity_map(self,
                        map_path: str = None,
                        plot_theory: bool = True,
                        fit_metadata: dict = None):
        """
        Load and display a cavity map.

        Parameters
        ----------
        map_path : str, optional
            Path to a previously acquired cavity map.
        plot_theory : bool, default=True
            If True, overlay theoretical cavity modes.
        fit_metadata : dict, optional
            Fitting configuration overriding the current settings.
        """
        
        if fit_metadata is not None:
            self.fit_metadata = fit_metadata

        self._import_map_data(full_path = map_path)
        self._plot_map(plot_theory = plot_theory)
    
    def fit_map(self,
                mode_ids: list = None,
                plot_mask: bool = False,
                plot_results: bool = True):
        """
        Fit resonances in a cavity map and compute fit results.

        Parameters
        ----------
        mode_ids : list, optional
            Modes to process.
        plot_mask : bool, default=False
            If True, display fitted regions.
        plot_results : bool, default=True
            If True, display summary plots.
        """
        
        self._fit_branches(mode_ids = mode_ids,
                           plot_mask = plot_mask)
        self._compute_results(plot = plot_results)

    # ---------------------------------------------------------------------
    # Step 3 - Starting length estimation
    # ---------------------------------------------------------------------

    def _check_starting_length(self,
                               length: float,
                               mode_id: str):
        """
        Validate a candidate starting length for optimization.

        Parameters
        ----------
        length : float
            Estimated cavity length in millimeters.
        mode_id : str
            Mode identifier.

        Raises
        ------
        ValueError
            If the estimated length is outside the allowed cavity range.

        Warns
        -----
        UserWarning
            If the estimated length is close to a mechanical limit.
        """
        
        cavity_length = self.parameters['total_cavity_length']
        piston_thickness = self.parameters['piston_thickness']
        zaber_zero = self.parameters['zaber_zero']

        position_zero = cavity_length - piston_thickness - zaber_zero

        cavity_min = position_zero - self.parameters['zaber_max']
        cavity_max = position_zero - self.parameters['zaber_min']

        if length < cavity_min or length > cavity_max:
            raise ValueError(f'[{mode_id}] ERROR: Starting length out of range: Max range = [{cavity_min:.6f}, {cavity_max:.6f}]')
        
        if np.abs(length - cavity_min) < self.fit_metadata['threshold_length']:
            print(f'[{mode_id}] WARNING: Starting length close to the minimum length of the cavity (min={cavity_min:.6f}): {length:.6f}')

        if np.abs(length - cavity_max) < self.fit_metadata['threshold_length']:
            print(f'[{mode_id}] WARNING: Starting length close to the maximum length of the cavity (max={cavity_max:.6f}): {length:.6f}')

    def starting_length(self,
                        mode_ids: list = None,
                        print_results: bool = True):
        """
        Estimate cavity lengths corresponding to the target frequency.

        A linear fit of each mode trajectory is used to determine the cavity
        length expected to produce the target frequency ``f0``.

        Parameters
        ----------
        mode_ids : list, optional
            Modes for which the calculation should be performed.
        print_results : bool, default=True
            If True, display the estimated lengths.

        Results
        -------
        starting_lengths : dict
            Dictionary mapping mode identifiers to estimated cavity lengths.
        """

        self.analysis.linear_fit_modes(mode_ids = mode_ids)
        self.starting_lengths = {}

        for mode_id, polynom in self.analysis.dict_polynoms.items():
            # Warning: polynom initially in GHz
            polynom = polynom * 1e+09
            length = (self.f0 - polynom[1]) / polynom[0]
            self._check_starting_length(length,
                                        mode_id)

            self.starting_lengths[mode_id] = length

            if print_results:
                print(f"Mode: {mode_id} | Starting length: {length:.6f} mm | Frequency resolution: {np.abs(polynom[0]) * self.parameters['zaber_accuracy'] * 1e-3:.3f} kHz")

    # ---------------------------------------------------------------------
    # Step 4 - Frequency optimization
    # ---------------------------------------------------------------------

    def _check_movement(self,
                        length: float):
        """
        Verify that a cavity length is mechanically reachable.

        Parameters
        ----------
        length : float
            Cavity length in millimeters.

        Raises
        ------
        ValueError
            If the requested position lies outside the cavity range.
        """
        
        cavity_length = self.parameters['total_cavity_length']
        piston_thickness = self.parameters['piston_thickness']
        zaber_zero = self.parameters['zaber_zero']

        position_zero = cavity_length - piston_thickness - zaber_zero

        cavity_min = position_zero - self.parameters['zaber_max']
        cavity_max = position_zero - self.parameters['zaber_min']

        if length < cavity_min or length > cavity_max:
            raise ValueError(f'Cavity lengths out of range. Starting point probably to close to the cavity limits')
    
    def _convert_length(self,
                        length: float):
        """
        Convert a cavity length into a Zaber stage position.

        Parameters
        ----------
        length : float
            Cavity length in millimeters.

        Returns
        -------
        float
            Corresponding Zaber position in millimeters.
        """
        
        cavity_length = self.parameters['total_cavity_length']
        piston_thickness = self.parameters['piston_thickness']
        zaber_zero = self.parameters['zaber_zero']

        position_zero = cavity_length - piston_thickness - zaber_zero

        return position_zero - length
        
    def _vna_measure_opt(self,
                         length):
        """
        Acquire a VNA trace at a given cavity length during optimization.

        Parameters
        ----------
        length : float
            Cavity length in millimeters.

        Notes
        -----
        The measurement is stored in a dedicated dataset and added to the
        optimization history.

        This function may need some changes if another VNA is used.
        """
        
        self._init_dfol()
        self.list_full_path.append(self.dfol.folder_full_path)
        

        dataset_name = self.opt_metadata['dataset_name']
        loop_name = self.opt_metadata['loop_name']

        self.devices['VNA'].write('CALC:PAR:COUN 1')
        self.devices['VNA'].write('INST:SEL "NA"')
        self.devices['VNA'].write(f"CALC:PAR1:DEF {self.parameters['trace']}")
        self.devices['VNA'].SetPower(self.opt_metadata['power'])
        self.devices['VNA'].SetIFBW(self.opt_metadata['ifbw'])
        
        data = self._segmented_sweep(metadata = self.opt_metadata)
        if self.parameters['vna_auto_scale']:
            self.devices['VNA'].write("DISP:WIND:TRAC1:Y:AUTO")

        # Create the dataset if it doesn't exist
        if dataset_name not in self.dfol.datasets.keys():
            data_names = list(data.keys())[1:]
            sweep_name = list(data.keys())[0]
            sweep_values = data[sweep_name]
            self.dfol.create_stlab_dataset(
                dataset_name,
                data_names,
                sweep_name,
                sweep_values,
                loop_name,
                [length],)
        
        # Insert the latest trace into the dataset
        self.dfol.datasets[dataset_name].attrs.update(self.opt_metadata)
        self.dfol.add_stlab_trace(dataset_name, data, 0)

    def _fit_S21(self):
        """
        Fit the most recently acquired optimization trace if opt_metadata['circle_fit'] is True.
        Else, return the resonance frequency using argmin() of the magnitude of S21.

        If the fit fails, automatically switch to the second method for this specific iteration.

        The resonance frequency and total coupling rate are extracted from
        the measured S21 response and appended to the optimization history.

        """

        full_path = self.list_full_path[-1]
        h5_files = sorted(glob.glob(full_path + '/*.h5'))

        data_opt = xr.load_dataset(h5_files[0])

        translator = {'Frequency (Hz)':['freq', 'GHz', 1e9],
                      'Cavity length (mm)':['length', 'mm', 1]}
        
        data_xr_opt = af.format_data_xarray(data = data_opt,
                                            tool = 'VNA',
                                            translator = translator,
                                            remove_edelay = self.opt_metadata['remove_edelay'])
        
        self.list_data_opt.append(data_xr_opt)
        
        if self.opt_metadata['circle_fit']:

            try:
                data_xr_opt = data_xr_opt.isel(length=0)
                fit_result = af.fit_single(self.model,
                                        data_xr_opt.freq.values,
                                        data_xr_opt.cpx.values,
                                        guess = None)

                self.list_fit_results.append(fit_result)
                self.dict_main_params['freq'].append(fit_result.params['f0'].value * 1e+09)
                self.dict_main_params['kt'].append(fit_result.params['kt'].value * 1e+09)

            except Exception as e:
                print(f"[{self.dict_main_params['length'][-1]:.6f} mm] Fit Error: {e}")
                print(f"Take minimum value of |S21| as resonance frequency. No value for kt")
                f0 = data_xr_opt.isel(freq=data_xr_opt.mag.argmin('freq')).freq.values
                self.dict_main_params['freq'].append(f0)
                self.dict_main_params['kt'].append(np.nan)
                self.list_fit_results.append(None)
            
            print(f"Frequency: {self.dict_main_params['freq'][-1]*1e-9:.9f} GHz | kt: {self.dict_main_params['kt'][-1]*1e-6:.6f} MHz")

        else:
            f0 = data_xr_opt.isel(freq=data_xr_opt.mag.argmin('freq')).freq.values
            self.dict_main_params['freq'].append(f0)
            self.dict_main_params['kt'].append(np.nan)

            print(f"Frequency: {self.dict_main_params['freq'][-1]*1e-9:.9f} GHz")

    
    def _init_optimization(self):
        """
        Initialize optimization data structures.

        This method creates a new resonator model and resets all stored
        optimization results, including:

        - frequency history,
        - cavity length history,
        - coupling-rate history,
        - fitted datasets,
        - fit results if opt_metadat['cirlce_fit'] is True,
        - acquisition paths.
        """

        self.dict_main_params = {'freq': [],
                                    'length': [],
                                    'kt': []}
        self.list_data_opt = []
        self.list_full_path = []

        if self.opt_metadata['circle_fit']:
            self.model = af.ComplexCircle()
            self.list_fit_results = []
    
    def optimization(self, 
                     mode_id: str,
                     reset: bool = True,
                     opt_metadata: dict = None):
        """
        Optimize the cavity resonance frequency.

        An iterative correction algorithm adjusts the cavity length until
        the measured resonance frequency matches the target frequency
        within a specified tolerance.

        Parameters
        ----------
        mode_id : str
            Identifier of the cavity mode used for optimization.
        reset : bool, default=True
            If True, start from the estimated starting length associated
            with the selected mode. Otherwise, continue from the most
            recently optimized length.
        opt_metadata : dict, optional
            Optimization settings overriding the current configuration.

        Notes
        -----
        At each iteration:

        1. The cavity is moved to the current length.
        2. A VNA trace is acquired.
        3. The resonance is fitted if opt_metadata['circle_fit'] is True. Else, take
            the minimum of the resonance.
        4. The frequency error is computed.
        5. A new cavity length is estimated from the mode slope.

        The correction applied at each iteration is

        .. math::

            \\Delta L = G \\frac{f_{\\mathrm{target}} - f_{\\mathrm{measured}}}
            {df/dL}

        where ``G`` is the optimization gain.

        Raises
        ------
        ValueError
            If the requested displacement exceeds the maximum allowed
            movement or if a resonance fit fails.

        Results
        -------
        dict_main_params : dict
            Dictionary containing the complete optimization history:

            - ``freq`` : measured frequencies (Hz)
            - ``length`` : cavity lengths (mm)
            - ``kt`` : fitted coupling rates (Hz)
        """
        
        if opt_metadata is not None:
            self.opt_metadata = opt_metadata

        iter = 0
        done = False
        self.mode_id_opt = mode_id

        if reset:
            self._init_optimization()
            length = self.starting_lengths[mode_id]
            print(f'Go to {mode_id}: length = {length:.6f} mm')
        else:
            length = self.dict_main_params['length'][-1]
            print(f'Return to the last optimized length: {length:.6f} mm')
        
        self.dict_main_params['length'].append(length)
        self._check_movement(length)
        position = self._convert_length(length)
        self.devices['Zaber'].move_absolute(position = position)
        
        polynom = self.analysis.dict_polynoms[mode_id] * 1e+09

        while not done and iter < self.opt_metadata['max_iter']:

            iter +=1
            print('')
            print('#################')
            print(f"Iteration {iter} | Length: {length:.6f} mm")

            self._vna_measure_opt(length = length)
            self._fit_S21()

            freq_error = self.opt_metadata['center_frequency'] - self.dict_main_params['freq'][-1]
            print(f"Frequency error: {freq_error * 1e-3:.3f} kHz | {100 * (np.abs(freq_error) / self.opt_metadata['center_frequency']):.6f} %")

            if np.abs(freq_error) < self.opt_metadata['threshold']:
                print('')
                print("CONVERGED!")
                print(f"Frequency: {self.dict_main_params['freq'][-1] * 1e-9:.9f} GHz")
                print(f"Frequency error: {freq_error * 1e-3:.3f} kHz | {100 * (np.abs(freq_error) / self.opt_metadata['center_frequency']):.6f} %")
                print(f"kt: {self.dict_main_params['kt'][-1] * 1e-6:.6f} MHz")
                print(f"Length: {self.dict_main_params['length'][-1]:.6f} mm")
                done = True
            
            delta_length = self.opt_metadata['gain'] * freq_error / polynom[0]
            print(f'Delta length: {delta_length * 1e+03:.3f} um')

            if np.abs(delta_length) > self.opt_metadata['max_movement']:
                raise ValueError(f'Delta L is too large: {delta_length:.6f} mm, check the parameters. STOP.')
            
            length = length + delta_length
            self._check_movement(length)
            self.dict_main_params['length'].append(length)
            position = self._convert_length(length = length)
            self.devices['Zaber'].move_absolute(position = position)

        if not done:
            print('')
            print("NOT CONVERGED.")
            print(f"Max iter: {self.opt_metadata['max_iter']}")
            print(f"Last optimization:")
            print(f"Frequency: {self.dict_main_params['freq'][-1] * 1e-9:.9f} GHz")
            print(f"Frequency error: {freq_error * 1e-3:.3f} kHz | {100 * (np.abs(freq_error) / self.opt_metadata['center_frequency']):.6f} %")
            print(f"kt: {self.dict_main_params['kt'][-1] * 1e-6:.6f} MHz")
            print(f"Length: {self.dict_main_params['length'][-1]:.6f} mm")

    #############
    ### TO DO ###
    #############

    # A function to save all the results from the fits during the optimization
    # Fornow, only the raw data of S21 are saved
    # Theoreticaly, it is enough since we can re-fitted the data to have all the results
    # but it is easier if all the fits all stored somewhere
    # Also, saved the path list is very useful to find a particular iteration of the optimization