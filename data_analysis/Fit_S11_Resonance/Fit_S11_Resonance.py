import numpy as np

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import pandas as pd

from scipy.optimize import curve_fit, least_squares

import logging
logging.basicConfig(format = "[%(name)s] %(message)s",
                            level = logging.INFO)

from types import TracebackType
from typing import Type

class Fit_S11_Resonance:

    def __init__(self,
                 freq: np.ndarray,
                 amp_dB: np.ndarray,
                 phase_deg: np.ndarray,
                 real: np.ndarray,
                 imag: np.ndarray,
                 label: str = "Fit S11"
                 ) -> None:
        
        self.freq = freq
        self.amp_dB = amp_dB
        self.phase_deg = phase_deg
        self.real = real
        self.imag = imag
        self.label = label
        self.logger = logging.getLogger(self.label)

        self.amp_lin = (10**(self.amp_dB / 20))**2
        self.phase_rad = np.deg2rad(self.phase_deg)

        self._amplitude_fit_done = False
        self._phase_fit_done = False
        self._delay_fit_done = False
        self._corrected_circle_done = False
        self._circle_fit_done = False

        self.logger.info(f"READY!")
    
    def __enter__(self
                  ) -> "Fit_S11_Resonance":
        return self
    
    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_val: BaseException,
                 exc_tb: TracebackType
                 ) -> bool:
        return False
    
    def __repr__(self
               ) -> str:
        return (f"Fit_S11_Resonance: label={self.label!r}")
    
    def plot_signal_data(self,
                         title: str = "$S_{11}$",
                         unwrap: bool = True
                         ) -> None:
        
        fig = plt.figure(figsize=(12, 8))
        gs = gridspec.GridSpec(2, 4)

        # Plot amplitude (dB scale)
        ax_amp = fig.add_subplot(gs[0,:2])
        ax_amp.scatter(self.freq, self.amp_dB, color='blue', marker='.', s=2)
        ax_amp.set_xlabel("Frequency (GHz)")
        ax_amp.set_ylabel("Amplitude (dB)")
        ax_amp.grid(True)

        # Plot phase (in degrees)
        ax_phase = fig.add_subplot(gs[1,:2])
        if unwrap:
            ax_phase.scatter(self.freq, np.unwrap(self.phase_deg, period=360), color='blue', marker='.', s=2) 
        else:
            ax_phase.plot(self.freq, self.phase_deg, color='blue', marker='.', s=2)
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel("Phase (degrees)")
        ax_phase.grid(True)

        # Plot IQ diagram
        ax_IQ = fig.add_subplot(gs[:,2:])
        ax_IQ.scatter(self.real, self.imag, color='blue', marker='.', s=2)
        ax_IQ.set_aspect('equal')
        ax_IQ.set_xlabel("$\\rm{Re}(S_{11})$")
        ax_IQ.set_ylabel("$\\rm{Im}(S_{11})$")
        ax_IQ.grid(True)

        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def linear_amplitude_model(self,
                               freq: np.ndarray,
                               freq_r: float,
                               Q_tot: float,
                               Q_c: float,
                               phi: float,
                               a: float
                               ) -> np.ndarray:
    
        beta = Q_tot / Q_c
        gamma = 2 * Q_tot * ((freq - freq_r) / freq_r)
        
        return (a**2) * (1 - 4 * beta * (np.cos(phi) + gamma * np.sin(phi) - beta) * (1 / (1 + gamma**2)))
    
    def phase_radians_model(self,
                            freq: np.ndarray,
                            freq_r: float,
                            Q_tot: float,
                            Q_c: float,
                            phi: float,
                            alpha: float,
                            tau: float
                            ) -> np.ndarray:
    
        beta = Q_tot / Q_c
        gamma = 2 * Q_tot * ((freq - freq_r) / freq_r)
        
        return np.unwrap(alpha
                         - 2 * np.pi * freq * tau
                         + np.arctan2(gamma - 2 * beta * np.sin(phi), 1 - 2 * beta * np.cos(phi)) 
                         - np.arctan2(gamma, 1))
    
    def fit_linear_amplitude(self,
                             p0: list = None
                             ) -> None:
        
        if p0 is None:
            offset = (self.amp_lin[0] + self.amp_lin[-1])/2
            depth = offset - np.min(self.amp_lin)
            half_amp = offset - depth / 2

            idx = np.where(self.amp_lin < half_amp)[0]
            bandwidth = self.freq[idx[-1]] - self.freq[idx[0]]

            freq_r_guess = self.freq[np.argmin(self.amp_lin)]
            Q_tot_guess = freq_r_guess / bandwidth
            a_guess = np.sqrt(offset)

            Q_c_guess = 2 * Q_tot_guess / (1 + (np.sqrt(np.min(self.amp_lin)) / a_guess))
            phi_guess = 0

            p0 = [freq_r_guess, Q_tot_guess, Q_c_guess, phi_guess, a_guess]
        
        popt, pcov = curve_fit(self.linear_amplitude_model, self.freq, self.amp_lin, p0=p0)

        freq_r, Q_tot, Q_c, phi, a = popt

        self.dict_amp_fit = {'freq_r': freq_r,
                             'Q_tot': Q_tot,
                             'Q_c': Q_c,
                             'phi': phi,
                             'a': a,
                             'cov_matrix': pcov}
        
        self._amplitude_fit_done = True
    
    def fit_electrical_delay(self,
                             ) -> None:
        
        n_edge = len(self.freq) // 10
        idx_edge_left = np.arange(0, len(self.freq)//10)
        idx_edge_right = np.arange(len(self.freq) - n_edge, len(self.freq))
        
        polynom_left = np.polyfit(self.freq[idx_edge_left], self.phase_rad[idx_edge_left], deg = 1)
        polynom_right = np.polyfit(self.freq[idx_edge_right], self.phase_rad[idx_edge_right], deg = 1)
        
        alpha = (polynom_left[1] + polynom_right[1]) / 2
        tau = - ((polynom_left[0] + polynom_right[0]) / 2) / (2*np.pi)

        self.dict_delay_fit = {'alpha': alpha,
                               'tau': tau}
        
        self._delay_fit_done = True
    
    def corrected_circle(self,
                         ) -> dict:
        
        if not self._amplitude_fit_done:
            raise RuntimeError(f"[{self.label}] Make amplitude fit before!")
        if not self._delay_fit_done:
            raise RuntimeError(f"[{self.label}] Make electrical delay fit before!")
    
        S11_raw = self.real + 1j*self.imag

        a = self.dict_amp_fit['a']
        alpha = self.dict_delay_fit['alpha']
        tau = self.dict_delay_fit['tau']
        
        correction = a * np.exp(1j*alpha) * np.exp(-2*1j*np.pi*self.freq*tau)
        
        S11_corrected = S11_raw / correction

        self.dict_correction = {'real_corrected': S11_corrected.real,
                                'imag_corrected': S11_corrected.imag,
                                'real' : self.real,
                                'imag': self.imag,
                                'a': a,
                                'alpha': alpha,
                                'tau': tau}
        
        self._corrected_circle_done = True
    
    def fit_IQ_circle(self
                      ) -> None:
        
        real_corrected = self.dict_correction['real_corrected']
        imag_corrected = self.dict_correction['imag_corrected']
        
        A = np.column_stack((2*real_corrected, 2*imag_corrected, np.ones_like(real_corrected)))
        b = real_corrected**2 + imag_corrected**2
        
        c, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
        
        x_center, y_center = c[0], c[1]
        
        radius = np.sqrt(c[2] + x_center**2 + y_center**2)

        self.dict_circle_fit = {'center': (x_center, y_center),
                                'radius': radius,
                                'residuals': residuals,
                                'rank': rank,
                                's': s}
        
        self._circle_fit_done = True
    
    def fit_phase_radians(self
                          ) -> None:
        
        if not self._amplitude_fit_done:
            raise RuntimeError(f"[{self.label}] Make amplitude fit before!")
        if not self._delay_fit_done:
            raise RuntimeError(f"[{self.label}] Make electrical delay fit before!")
        if not self._circle_fit_done:
            raise RuntimeError(f"[{self.label}] Make IQ circle fit before!")
        
        phase_unwrap = np.unwrap(self.phase_rad)
        x_center, y_center = self.dict_circle_fit['center']

        freq_r_guess = self.dict_amp_fit['freq_r']
        Q_tot_guess = self.dict_amp_fit['Q_tot']
        Q_c_guess = self.dict_amp_fit['Q_tot'] / self.dict_circle_fit['radius']
        phi_guess = np.arctan2(- y_center, 1 - x_center)
        alpha_guess = self.dict_delay_fit['alpha']
        tau_guess = self.dict_delay_fit['tau']

        p0 = [freq_r_guess, Q_tot_guess, Q_c_guess, phi_guess, alpha_guess, tau_guess]

        popt, pcov = curve_fit(self.phase_radians_model, self.freq, phase_unwrap, p0=p0)

        freq_r, Q_tot, Q_c, phi, alpha, tau = popt

        self.dict_phase_fit = {'freq_r': freq_r,
                               'Q_tot': Q_tot,
                               'Q_c': Q_c,
                               'phi': phi,
                               'alpha': alpha,
                               'tau': tau,
                               'cov_matrix': pcov}
        
        self._phase_fit_done = True
    
    def fit_S11_signal(self
                       ) -> None:
        
        self.fit_linear_amplitude()
        self.fit_electrical_delay()
        self.corrected_circle()
        self.fit_IQ_circle()
        self.fit_phase_radians()
    
    def plot_fit_amplitude(self
                           ) -> None:

        if not self._amplitude_fit_done:
            raise RuntimeError(f"[{self.label}] Make amplitude fit before!")
        
        freq_r = self.dict_amp_fit['freq_r']
        Q_tot = self.dict_amp_fit['Q_tot']
        Q_c = self.dict_amp_fit['Q_c']
        phi = self.dict_amp_fit['phi']
        a = self.dict_amp_fit['a']
        
        plt.figure(figsize=(10, 6))
        plt.scatter(self.freq, self.amp_lin,
                    color='blue', marker='.', s=2,
                    label='Data')
        plt.plot(self.freq, self.linear_amplitude_model(self.freq, freq_r, Q_tot, Q_c, phi, a),
                 color='red', linestyle='--',
                 label = 'Fit')
        plt.axvline(freq_r, linestyle='--', color='green', label=f"{freq_r:.3f} GHz")
        plt.title(f"Fit amplitude $S_{{11}}$" 
                  f"\n $f_{{res}}$ = {freq_r:.3f} GHz" 
                  f"\n $Q_{{tot}}$ = {Q_tot:.3f}"
                  f" | $\kappa_{{tot}}$ = {freq_r * 1e3 / Q_tot} MHz")
        
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Amplitude")

        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
    
    def plot_fit_delay(self
                       ) -> None:
        
        if not self._delay_fit_done:
            raise RuntimeError(f"[{self.label}] Make electrical delay fit before!")
        
        alpha = self.dict_delay_fit['alpha']
        tau = self.dict_delay_fit['tau']
        
        plt.figure(figsize=(10,6))
        plt.scatter(self.freq, self.phase_rad,
                    color='blue', marker='.', s=2,
                    label='Data')
        plt.plot(self.freq, np.polyval([-2*np.pi*tau, alpha], self.freq),
                 color='red', linestyle='--',
                 label='Fit')
        
        plt.xlabel('Frequency (GHz)')
        plt.ylabel('Phase (rad)')

        plt.title(f"Fit electric delay" 
                  f"\n $\\alpha$ = {alpha:.3f} rad"
                  f"\n $\\tau$ = {tau:.3f} ns")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def plot_corrected_circle(self
                              ) -> None:
        
        if not self._corrected_circle_done:
            raise RuntimeError(f"[{self.label}] Make correction circle before!")
        
        a = self.dict_correction['a']
        alpha = self.dict_correction['alpha']
        tau = self.dict_correction['tau']
        
        plt.figure(figsize=(10,6))
        plt.scatter(self.real, self.imag,
                    color='black', marker='.', s=2,
                    label='Data')
        plt.scatter(self.dict_correction['real_corrected'], self.dict_correction['imag_corrected'],
                    color='orange', marker='.', s=2,
                    label='Corrected data')
        
        plt.xlabel('$\\rm{Re}(S_{11})$')
        plt.ylabel('$\\rm{Im}(S_{11})$')

        plt.title(f"Corrected circle" 
                  f"\n $a$ = {a:.3f}"
                  f"\n $\\alpha$ = {alpha:.3f} rad"
                  f"\n $\\tau$ = {tau:.3f} ns")
        
        plt.legend()
        plt.grid()
        plt.axis("equal")
        plt.tight_layout()
        plt.show()
    
    def plot_fit_circle(self
                        ) -> None:
        
        if not self._circle_fit_done:
            raise RuntimeError(f"[{self.label}] Make IQ circle fit before!")
        
        x_center, y_center = self.dict_circle_fit['center']
        radius = self.dict_circle_fit['radius']

        real_corrected = self.dict_correction['real_corrected']
        imag_corrected = self.dict_correction['imag_corrected']

        theta = np.linspace(0, 2*np.pi, len(self.freq))
        real_fit = x_center + radius * np.cos(theta)
        imag_fit = y_center + radius * np.sin(theta)
        
        plt.figure(figsize=(10,6))
        plt.scatter(self.real, self.imag,
                    color='black', marker='.', s=2,
                    label='Data')
        plt.scatter(real_corrected, imag_corrected,
                    color='blue', marker='.', s=2,
                    label='Corrected data')
        plt.plot(real_fit, imag_fit,
                 color='red', linestyle='--',
                 label='Fit')
        plt.scatter([x_center], [y_center],
                    marker='x', color='green',
                    label='Center')
        
        plt.xlabel('$\\rm{Re}(S_{11})$')
        plt.ylabel('$\\rm{Im}(S_{11})$')

        plt.title(f"Fit circle IQ plane"
                  f"\n Radius = {radius:.3f}"
                  f"\n Center = ({x_center:.3f},{y_center:.3f})")
        
        plt.legend()
        plt.grid()
        plt.axis("equal")
        plt.tight_layout()
        plt.show()
    
    def plot_fit_phase(self
                       ) -> None:
        
        if not self._phase_fit_done:
            raise RuntimeError(f"[{self.label}] Make phase fit before!")
        
        freq_r = self.dict_phase_fit['freq_r']
        Q_tot = self.dict_phase_fit['Q_tot']
        Q_c = self.dict_phase_fit['Q_c']
        phi = self.dict_phase_fit['phi']
        alpha = self.dict_phase_fit['alpha']
        tau = self.dict_phase_fit['tau']
        
        plt.figure(figsize=(10, 6))
        plt.scatter(self.freq, self.phase_deg,
                    color='black', marker='.', s=2,
                    label='Data')
        plt.scatter(self.freq, np.unwrap(self.phase_deg),
                    color='blue', marker='.', s=2,
                    label='Unwrapped data')
        plt.plot(self.freq, np.rad2deg(self.phase_radians_model(self.freq, freq_r, Q_tot, Q_c, phi, alpha, tau)),
                 color='red', linestyle='--',
                 label='Fit')
        plt.axvline(freq_r, linestyle='--', color='green', label=f"{freq_r:.3f} GHz")
        
        plt.title(f"Fit phase $S_{{11}}$"
                  f"\n $f_{{res}}$ = {freq_r:.3f} GHz"
                  f"\n $Q_{{tot}}$ = {Q_tot:.3f}"
                  f"\n $\\tau$ = {tau:.3f} ns")
        
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Phase (degrees)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
    
    def plot_all(self
                 ) -> None:
        
        if not self._amplitude_fit_done:
            raise RuntimeError(f"[{self.label}] Make amplitude fit before!")
        if not self._delay_fit_done:
            raise RuntimeError(f"[{self.label}] Make delay fit before!")
        if not self._corrected_circle_done:
            raise RuntimeError(f"[{self.label}] Make corrected circle before!")
        if not self._circle_fit_done:
            raise RuntimeError(f"[{self.label}] Make circle fit before!")
        if not self._phase_fit_done:
            raise RuntimeError(f"[{self.label}] Make phase fit before!")
        
        fig = plt.figure(figsize=(12, 8))
        gs = gridspec.GridSpec(2, 5)

        # Amplitude plot
        freq_r = self.dict_amp_fit['freq_r']
        Q_tot = self.dict_amp_fit['Q_tot']
        Q_c = self.dict_amp_fit['Q_c']
        phi = self.dict_amp_fit['phi']
        a = self.dict_amp_fit['a']

        ax_amp = fig.add_subplot(gs[0,:3])
        
        ax_amp.scatter(self.freq, self.amp_dB,
                       color='blue', marker='.', s=2,
                       label='Data')
        ax_amp.plot(self.freq, 10 * np.log10(self.linear_amplitude_model(self.freq, freq_r, Q_tot, Q_c, phi, a)),
                    color='red', linestyle='--',
                    label='Fit')
        
        ax_amp.axvline(freq_r, linestyle='--', color='green', label=f"{freq_r:.3f} GHz")
        
        ax_amp.set_xlabel("Frequency (GHz)")
        ax_amp.set_ylabel("Amplitude (dB)")
        ax_amp.grid(True)
        ax_amp.legend()
        ax_amp.set_title(f"Fit amplitude $S_{{11}}$" 
                         f"\n $f_{{res}}$ = {freq_r:.6f} GHz" 
                         f"\n $Q_{{tot}}$ = {Q_tot:.1f}"
                         f" | $\kappa_{{tot}}$ = {freq_r * 1e3 / Q_tot:.3f} MHz")
        
        # Phase plot
        freq_r = self.dict_phase_fit['freq_r']
        Q_tot = self.dict_phase_fit['Q_tot']
        Q_c = self.dict_phase_fit['Q_c']
        phi = self.dict_phase_fit['phi']
        alpha = self.dict_phase_fit['alpha']
        tau = self.dict_phase_fit['tau']

        ax_phase = fig.add_subplot(gs[1,:3])

        ax_phase.scatter(self.freq, self.phase_deg,
                         color='black', marker='.', s=2,
                         label='Data')
        ax_phase.scatter(self.freq, np.unwrap(self.phase_deg, period=360),
                         color='blue', marker='.', s=2,
                         label='Unwrapped data')
        ax_phase.plot(self.freq, np.rad2deg(self.phase_radians_model(self.freq, freq_r, Q_tot, Q_c, phi, alpha, tau)),
                      color='red', linestyle='--',
                      label='Fit')
        ax_phase.axvline(freq_r, linestyle='--', color='green', label=f"{freq_r:.3f} GHz")
        
        ax_phase.set_xlabel("Frequency (GHz)")
        ax_phase.set_ylabel("Phase (degrees)")
        ax_phase.grid(True)
        ax_phase.legend()
        ax_phase.set_title(f"Fit phase $S_{{11}}$"
                           f"\n $f_{{res}}$ = {freq_r:.6f} GHz"
                           f"\n $Q_{{tot}}$ = {Q_tot:.1f}"
                           f" | $\kappa_{{tot}}$ = {freq_r * 1e3 / Q_tot:.3f} MHz"
                           f"\n $\\tau$ = {tau:.3f} ns")
        
        # IQ plot
        x_center, y_center = self.dict_circle_fit['center']
        radius = self.dict_circle_fit['radius']

        theta = np.linspace(0, 2*np.pi, len(self.freq))
        real_fit = x_center + radius * np.cos(theta)
        imag_fit = y_center + radius * np.sin(theta)

        ax_IQ = fig.add_subplot(gs[:,3:])

        ax_IQ.scatter(self.real, self.imag,
                      color='black', marker='.', s=2,
                      label="Data")
        ax_IQ.scatter(self.dict_correction['real_corrected'], self.dict_correction['imag_corrected'],
                      color='blue', marker='.', s=2,
                      label='Corrected data')
        ax_IQ.plot(real_fit, imag_fit,
                   color='red', linestyle='--',
                   label='Fit')
        ax_IQ.scatter([x_center], [y_center],
                      color='green', marker='x',
                      label="Center")
        
        ax_IQ.set_aspect('equal')
        ax_IQ.set_xlabel("$\\rm{Re}(S_{11})$")
        ax_IQ.set_ylabel("$\\rm{Im}(S_{11})$")
        ax_IQ.grid(True)
        ax_IQ.legend(loc='upper right')
        ax_IQ.set_title(f"Fit circle IQ plane"
                        f"\n Radius = {radius:.3f}"
                        f"\n Center = ({x_center:.3f},{y_center:.3f})")
        
        dict_result = self.results()

        freq_r = dict_result['freq_r']

        Q_tot = dict_result['Q_tot']
        kappa_tot = dict_result['kappa_tot']

        Q_c = dict_result['Q_c']
        kappa_c = dict_result['kappa_c']

        Q_i = dict_result['Q_i']
        kappa_i = dict_result['kappa_i']

        tau = dict_result['tau']
        
        plt.suptitle(f"Fit S11 Resonance"
                     f"\n $f_{{res}}$ = {freq_r:.6f} GHz"
                     f"\n $Q_{{tot}}$ = {Q_tot:.1f}"
                     f" | $\kappa_{{tot}} / 2\pi$ = {kappa_tot:.3f} MHz" 
                     f"\n $Q_{{c}}$ = {Q_c:.1f}"
                     f" | $\kappa_{{c}} / 2\pi$ = {kappa_c:.3f} MHz" 
                     f"\n $Q_{{i}}$ = {Q_i:.1f}"
                     f" | $\kappa_{{i}} / 2\pi$ = {kappa_i:.3f} MHz" 
                     f"\n $\\tau$ = {tau:.3f} ns")
        
        plt.tight_layout()
        plt.show()
    
    def results(self
               ) -> dict:
        
        if not self._amplitude_fit_done:
            raise RuntimeError(f"[{self.label}] Make amplitude fit before!")
        if not self._delay_fit_done:
            raise RuntimeError(f"[{self.label}] Make delay fit before!")
        if not self._corrected_circle_done:
            raise RuntimeError(f"[{self.label}] Make corrected circle before!")
        if not self._circle_fit_done:
            raise RuntimeError(f"[{self.label}] Make circle fit before!")
        if not self._phase_fit_done:
            raise RuntimeError(f"[{self.label}] Make phase fit before!")
        
        freq_r = self.dict_phase_fit['freq_r']

        Q_tot = self.dict_amp_fit['Q_tot'] ## CAHNGE THAT ####
        kappa_tot = freq_r * 1e3 / Q_tot

        radius = self.dict_circle_fit['radius']

        Q_c = Q_tot / radius
        kappa_c = freq_r * 1e3 / Q_c

        Q_i = 1 / (1/Q_tot - 1/Q_c)
        kappa_i = freq_r / Q_i

        tau = self.dict_phase_fit['tau']

        self.dict_results = {'freq_r': freq_r,
                            'Q_tot': Q_tot, 'kappa_tot': kappa_tot,
                            'Q_c': Q_c, 'kappa_c': kappa_c,
                            'Q_i': Q_i, 'kappa_i': kappa_i,
                            'tau': tau}
        
        return self.dict_results
    
    def print_results(self
                     ) -> None:
        
        dict_results = self.results()
        
        print(f"=== Resonance ==="
              f"\n f_res = {dict_results['freq_r']:.6f} GHz"
              f"\n")
        print(f"=== Quality factors ==="
              f"\n Q_tot = {dict_results['Q_tot']:.1f}"
              f"\n Q_i = {dict_results['Q_i']:.1f}"
              f"\n Q_c = {dict_results['Q_c']:.1f}"
              f"\n")
        
        print(f"=== Kappas ==="
              f"\n 'kappa' means 'kappa / 2pi'"
              f"\n kappa_tot = {dict_results['kappa_tot']:.3f} MHz"
              f"\n kappa_i = {dict_results['kappa_i']:.3f} MHz"
              f"\n kappa_c = {dict_results['kappa_c']:.3f} MHz"
              f"\n")
        
        print(f"=== Electrical delay ==="
              f"\n tau = {dict_results['tau']:.3f} ns"
              f"\n")
