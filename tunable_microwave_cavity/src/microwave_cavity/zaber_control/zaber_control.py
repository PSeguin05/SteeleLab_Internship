import numpy as np
import csv

import logging
logging.basicConfig(format = "[%(name)s] %(message)s",
                            level = logging.INFO)

from types import TracebackType
from typing import Type

from zaber_motion import Units
from zaber_motion.ascii import Connection

class zaber_control:
    """
    High-level interface for controlling a Zaber linear stage.

    This class provides methods for connecting to a Zaber motion device,
    configuring motion parameters, performing absolute and relative
    movements, retrieving device information, and acquiring oscilloscope
    data from the controller.

    The class supports Python context management, allowing automatic
    connection cleanup when used within a ``with`` statement.

    Parameters
    ----------
    port : str
        Serial port used to communicate with the device.
    label : str, default="Zaber"
        Name used for logging messages.
    axis_number : int, default=1
        Axis number to control on the detected device.
    auto_home : bool, default=False
        If True, automatically perform a homing sequence during
        initialization.
    auto_close : bool, default=True
        If True, automatically close the connection when exiting a
        context manager.
    default_velocity : float, default=1
        Default motion velocity in mm/s.
    default_acceleration : float, optional
        Default motion acceleration in mm/s^2.
    wait_until_idle : bool, default=True
        If True, motion commands block until completion.
    verb : bool, default=True
        If True, display informational log messages.

    Attributes
    ----------
    connection : Connection
        Active Zaber serial connection.
    device : Device
        First detected Zaber device.
    axis : Axis
        Controlled motion axis.
    scope : Oscilloscope
        Oscilloscope interface associated with the device.
    logger : logging.Logger
        Logger used for status messages.
    """

    def __init__(self,
                 port: str,
                 label: str = "Zaber",
                 axis_number: int = 1,
                 auto_home: bool = False,
                 auto_close: bool = True,
                 default_velocity: float = 1,
                 default_acceleration: float = None,
                 wait_until_idle: bool = True,
                 verb: bool = True
                 ) -> None:
        """
        Initialize the connection to a Zaber motion controller and prepare
        the selected axis for operation.
        """
        
        self.port = port
        self.label = label
        self.axis_number = axis_number
        self.wait = wait_until_idle
        self.save_velocity = False
        self.auto_close = auto_close
        self.default_velocity = default_velocity
        self.default_acceleration = default_acceleration
        self._scope_configured = False
        self.logger = logging.getLogger(self.label)
        self.verb = verb

        self.connection = Connection.open_serial_port(port_name = self.port)
        self.connection.enable_alerts()

        self.devices = self.connection.detect_devices()
        if len(self.devices) == 0:
            raise RuntimeError(f"No detected device on {self.port}")
        
        if self.verb:
            self.logger.info(f"{len(self.devices)} device(s) detected")

        self.device = self.devices[0]
        self.axis = self.device.get_axis(self.axis_number)

        if not self.axis.settings.get("driver.enabled"):
            self.axis.driver_enable()
            if self.verb:
                self.logger.info(f"Driver ENABLE")

        if auto_home:
            if self.verb:
                self.logger.info(f"Homing...")
            self.axis.home()
            if self.verb:
                self.logger.info(f"Homed")
        
        self.scope = self.device.oscilloscope
        self.scope.clear()

        self.logger.info(f"READY!")
    
    def __enter__(self
                  ) -> "zaber_control":
        """
        Enter the context manager.

        Returns
        -------
        zaber_control
            Current instance of the controller.
        """
        
        return self

    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_val: BaseException,
                 exc_tb: TracebackType
                 ) -> bool:
        """
        Exit the context manager.

        Closes the connection automatically if `auto_close` is enabled.

        Parameters
        ----------
        exc_type : Type[BaseException]
            Type of the exception raised inside the context block.
        exc_val : BaseException
            Exception instance.
        exc_tb : TracebackType
            Traceback information associated with the exception.

        Returns
        -------
        bool
            Always returns `False` so that exceptions are propagated.
        """
        
        if self.auto_close:
            self.close()
        return False
    
    def __repr__(self
                 ) -> str:
        """
        Return a string representation of the controller.

        Returns
        -------
        str
            Human-readable description of the controller configuration.
        """
        
        return (f"Zaber_Linear_Stage(port={self.port!r}, "
                f"label={self.label!r}, axis={self.axis_number})")
    
    # ---------------------------------------------------------------------
    # Internal utility methods
    # ---------------------------------------------------------------------

    # This functions are not meant to be called directly by the user.
    
    def _check_bounds(self,
                      position: float
                      ) -> None:
        """
        Verify that a position lies within the allowed travel range.

        Parameters
        ----------
        position : float
            Target position in millimeters.

        Raises
        ------
        ValueError
            If the requested position is outside the stage limits.
        """
        
        position_min = self.axis.settings.get("limit.min", Units.LENGTH_MILLIMETRES)
        position_max = self.axis.settings.get("limit.max", Units.LENGTH_MILLIMETRES)
        if not (position_min <= position <= position_max):
            raise ValueError(f"Position {position} mm out of range [{position_min:.3f}, {position_max:.3f}] mm")
        
    
    def _check_velocity(self,
                        velocity: float
                        ) -> None:
        """
        Verify that a velocity is within the allowed range.

        Parameters
        ----------
        velocity : float
            Velocity in mm/s.

        Raises
        ------
        ValueError
            If the velocity exceeds the allowed limits.
        """
        
        velocity_min = 0
        velocity_max = self.axis.settings.get("maxspeed.max", Units.VELOCITY_MILLIMETRES_PER_SECOND)
        if not (velocity_min <= velocity <= velocity_max):
            raise ValueError(f"Velocity {velocity} mm/s out of range [{velocity_min:.3f}, {velocity_max:.3f}] mm/s")
    
    def _check_acceleration(self,
                            acceleration: float
                            ) -> None:
        """
        Verify that an acceleration is within the allowed range.

        Parameters
        ----------
        acceleration : float
            Acceleration in mm/s^2.

        Raises
        ------
        ValueError
            If the acceleration exceeds the allowed limits.
        """
        
        acceleration_min = 0
        acceleration_max = self.axis.settings.get("accel", Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED)
        if not (acceleration_min <= acceleration <= acceleration_max):
            raise ValueError(f"Acceleration {acceleration} mm/s^2 out of range [{acceleration_min:.3f}, {acceleration_max:.3f}] mm/s^2")
    
    def _check_parameters(self,
                          position: float = None,
                          velocity: float = None,
                          acceleration: float = None
                          ) -> None:
        """
        Validate motion parameters before executing a movement command.

        Parameters
        ----------
        position : float, optional
            Target position in millimeters.
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s^2.
        """
        
        if position is not None:
            self._check_bounds(position)
        if velocity is not None:
            self._check_velocity(velocity)
        if acceleration is not None:
            self._check_acceleration(acceleration)

    def _assert_enabled(self
                        ) -> None:
        """
        Ensure that the motor driver is enabled.

        Raises
        ------
        RuntimeError
            If the driver is disabled.
        """
        
        if not bool(self.axis.settings.get("driver.enabled")):
            raise RuntimeError(f"[{self.label}] Driver is disabled. Call enable() first.")
    
    def _assert_scope_configured(self
                                 ) -> None:
        """
        Ensure that the oscilloscope has been configured.

        Raises
        ------
        RuntimeError
            If the oscilloscope is not configured.
        """
        
        if not self._scope_configured:
            raise RuntimeError(
                f"[{self.label}] Scope not configured. Call scope_config() first."
        )
    
    def _motion_kwargs(self,
                       velocity: float = None,
                       acceleration: float = None,
                       **extra
                       ) -> dict:
        """
        Build a keyword-argument dictionary for motion commands.

        Parameters
        ----------
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s².
        **extra
            Additional arguments forwarded to the motion command.

        Returns
        -------
        dict
            Dictionary containing motion parameters and units.
        """
        
        kwargs = {"wait_until_idle": self.wait, **extra}
        if velocity is not None:
            kwargs["velocity"] = velocity
            kwargs["velocity_unit"] = Units.VELOCITY_MILLIMETRES_PER_SECOND
        elif self.default_velocity is not None:
            kwargs["velocity"] = self.default_velocity
            kwargs["velocity_unit"] = Units.VELOCITY_MILLIMETRES_PER_SECOND

        if acceleration is not None:
            kwargs["acceleration"] = acceleration
            kwargs["acceleration_unit"] = Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED
        elif self.default_acceleration is not None:
            kwargs["acceleration"] = self.default_acceleration
            kwargs["acceleration_unit"] = Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED

        return kwargs
    
    # ---------------------------------------------------------------------
    # Device management
    # ---------------------------------------------------------------------

    def close(self
              ) -> None:
        """
        Close the connection to the device.
        """
        
        self.connection.close()
        self.logger.info(f"Connection closed.")
    
    def enable(self
               ) -> None:
        """
        Enable the motor driver.
        """
        
        self.axis.driver_enable()
        self.logger.info(f"Driver ENABLE")
    
    def disable(self
                ) -> None:
        """
        Disable the motor driver.
        """
        
        self.axis.driver_disable()
        self.logger.info(f"Driver DISABLE")
    
    # ---------------------------------------------------------------------
    # Information retrieval
    # ---------------------------------------------------------------------

    def get_position(self
                     ) -> float:
        """
        Retrieve the current stage position.

        Returns
        -------
        float
            Current position in millimeters.
        """
        
        position = self.axis.get_position(unit = Units.LENGTH_MILLIMETRES)
        if self.verb:
            self.logger.info(f"Position = {position:.6f} mm")

        return position
    
    def get_params(self
                   ) -> dict:
        """
        Retrieve stage operating parameters and limits.

        Returns
        -------
        dict
            Dictionary containing position, velocity, and acceleration
            limits together with their default values.
        """
        
        position_min = self.axis.settings.get("limit.min", Units.LENGTH_MILLIMETRES)
        position_accuracy = 0.02
        position_max = self.axis.settings.get("limit.max", Units.LENGTH_MILLIMETRES)
        self.logger.info(f"Positioning accuracy: {position_accuracy} mm")
        self.logger.info(f"Position range: [{position_min:.6f}, {position_max:.6f}] mm")

        # From the specifications (corresponds to the speed resolution)
        velocity_min = 0.000029
        if self.default_velocity is None:
            default_velocity = self.axis.settings.get("maxspeed", Units.VELOCITY_MILLIMETRES_PER_SECOND)
        else:
            default_velocity = self.default_velocity
        # Official max speed :
        # velocity_max = self.axis.settings.get("maxspeed.max", Units.VELOCITY_MILLIMETRES_PER_SECOND)
        # Returns 30.48 mm/s, but official specifications set the maximum speed to 26 mm/s
        velocity_max = 26
        self.logger.info(f"Default speed: {default_velocity:.6f} mm/s")
        self.logger.info(f"Velocity range: [{velocity_min:.6f}, {velocity_max:.6f}] mm/s")

        acceleration_min = 0
        if self.default_acceleration is None:
            default_acceleration = self.axis.settings.get("accel", Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED)
        else:
            default_acceleration = self.default_acceleration
        # There is no specific settings for maximum acceleration
        # Staying below 100 mm/s^2 is more than enough
        acceleration_max = 100
        self.logger.info(f"Default acceleration: {default_acceleration:.6f} mm/s^2")
        self.logger.info(f"Acceleration range: [{acceleration_min:.6f}, {acceleration_max:.6f}] mm/s^2")

        return {position_min: position_min,
                position_accuracy: position_accuracy,
                position_max: position_max,
                velocity_min: velocity_min,
                default_velocity: default_velocity,
                velocity_max: velocity_max,
                acceleration_min: acceleration_min,
                default_acceleration: default_acceleration,
                acceleration_max: acceleration_max}
    
    # ---------------------------------------------------------------------
    # Motion control
    # ---------------------------------------------------------------------

    def home(self
             ) -> None:
        """
        Perform a homing sequence.

        The stage moves to its reference position and resets its coordinate
        system.
        """
        
        self._assert_enabled()
        if self.verb:
            self.logger.info(f"Homing...")
        self.axis.home(wait_until_idle = self.wait)
        if self.verb:
            self.logger.info(f"Homed.")
    
    def move_absolute(self,
                      position: float,
                      velocity: float = None,
                      acceleration: float = None
                      ) -> None:
        """
        Move the stage to an absolute position.

        Parameters
        ----------
        position : float
            Target position in millimeters.
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s².
        """
        
        self._check_parameters(position = position,
                               velocity = velocity,
                               acceleration = acceleration)
        self._assert_enabled()
        self.axis.move_absolute(**self._motion_kwargs(velocity = velocity,
                                                      acceleration = acceleration,
                                                      position = position,
                                                      unit = Units.LENGTH_MILLIMETRES))
    
    def move_relative(self,
                      delta_position: float,
                      velocity: float = None,
                      acceleration: float = None
                      ) -> None:
        """
        Move the stage relative to its current position.

        Parameters
        ----------
        delta_position : float
            Relative displacement in millimeters.
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s².
        """
        
        current_position = self.axis.get_position(unit = Units.LENGTH_MILLIMETRES)
        self._check_parameters(position = current_position + delta_position,
                               velocity = velocity,
                               acceleration = acceleration)
        self._assert_enabled()
        self.axis.move_relative(**self._motion_kwargs(velocity = velocity,
                                                      acceleration = acceleration,
                                                      position = delta_position,
                                                      unit = Units.LENGTH_MILLIMETRES))
    
    def move_min(self,
                 velocity: float = None,
                 acceleration: float = None
                 ) -> None:
        """
        Move the stage to its minimum travel limit.

        Parameters
        ----------
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s².
        """
        
        self._check_parameters(velocity = velocity,
                               acceleration = acceleration)
        self._assert_enabled()
        self.axis.move_min(**self._motion_kwargs(velocity = velocity,
                                                 acceleration = acceleration
                                                 ))
    
    def move_max(self,
                 velocity: float = None,
                 acceleration: float = None
                 ) -> None:
        """
        Move the stage to its maximum travel limit.

        Parameters
        ----------
        velocity : float, optional
            Motion velocity in mm/s.
        acceleration : float, optional
            Motion acceleration in mm/s².
        """
        
        self._check_parameters(velocity = velocity,
                               acceleration = acceleration)
        self._assert_enabled()
        self.axis.move_max(**self._motion_kwargs(velocity = velocity,
                                                 acceleration = acceleration
                                                 ))
    
    def wait_until_idle(self
                        ) -> None:
        """
        Block execution until all motion commands have completed.
        """
        
        self.axis.wait_until_idle()
    
    # ---------------------------------------------------------------------
    # Oscilloscope acquisition
    # ---------------------------------------------------------------------
    
    def scope_config(self,
                     interval: float = 1e-2,
                     save_velocity: bool = False
                     ) -> None:
        """
        Configure the controller oscilloscope.

        Parameters
        ----------
        interval : float, default=1e-2
            Sampling interval in seconds.
        save_velocity : bool, default=False
            If True, record both position and velocity signals.
        """
        
        self.time_interval_scope = interval
        self.save_velocity = save_velocity
        self.scope.clear()
        self.scope.add_channel(self.axis_number, "pos")

        if self.save_velocity:
            self.scope.add_channel(self.axis_number, "vel")

        self.scope.set_timebase(interval = self.time_interval_scope,
                                unit = Units.TIME_SECONDS)
        
        max_time = self.scope.get_max_buffer_size() * self.time_interval_scope

        if self.save_velocity:
            max_time = max_time / 2
        self.logger.info(f"Scope maximum duration = {max_time:.3f} s")
        
        self.scope.set_delay(0)

        self._scope_configured = True

    def scope_start(self
                    ) -> None:
        """
        Start oscilloscope acquisition.
        """
        
        self._assert_scope_configured()
        self.scope.start()
        if self.verb:
            self.logger.info(f"Scope STARTED")
    
    def scope_stop(self
                   ) -> None:
        
        """
        Stop oscilloscope acquisition.
        """
        
        self._assert_scope_configured()
        self.scope.stop()
        if self.verb:
            self.logger.info(f"Scope STOPPED")
    
    def scope_save(self,
                   filename: str = "Scope.csv",
                   save_csv: bool = True,
                   return_dict: bool = True
                   ) -> dict:
        """
        Retrieve and optionally save oscilloscope data.

        Parameters
        ----------
        filename : str, default="Scope.csv"
            Name of the CSV file used to save acquired data.
        save_csv : bool, default=True
            If True, save the acquisition to a CSV file.
        return_dict : bool, default=True
            If True, return the acquisition data as a dictionary.

        Returns
        -------
        dict
            Dictionary containing acquisition metadata and sampled signals.

            The returned dictionary contains at least:

            - ``time`` : sampling times (s)
            - ``timebase`` : oscilloscope timebase (s)
            - ``frequency`` : sampling frequency (Hz)
            - ``delay`` : acquisition delay (s)
            - ``position`` : position samples (mm)

            If velocity acquisition was enabled, the dictionary also
            contains:

            - ``velocity`` : velocity samples (mm/s)

        Notes
        -----
        The oscilloscope configuration is cleared after data retrieval.
        """
        
        self._assert_scope_configured()

        if not save_csv and not return_dict:
            if self.verb:
                self.logger.warning("scope_saving_data() called with save_csv=False and return_dict=False — nothing to do.")

        if self.verb:
            self.logger.info("Reading scope data...")
        data = self.scope.read()

        position = data[0]
        position_samples = position.get_data(Units.LENGTH_MILLIMETRES)

        times = position.get_sample_times(Units.TIME_SECONDS)

        if self.save_velocity:
            velocity = data[1]
            velocity_samples = velocity.get_data(Units.VELOCITY_MILLIMETRES_PER_SECOND)

        if save_csv:
            if self.verb:
                self.logger.info(f"Saving CSV file...")
            if self.save_velocity:
                header = ["Time (s)", "Position (mm)", "Velocity (mm/s)"]
                rows = zip(times, position_samples, velocity_samples)
            else:
                header = ["Time (s)", "Position (mm)"]
                rows = zip(times, position_samples)

            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(header)
                writer.writerows(rows)
            
            if self.verb:
                self.logger.info(f"CSV file saved: {filename}")
        
        self._scope_configured = False

        if return_dict:
            result = {"time": np.asarray(times),
                  "timebase": position.get_timebase(Units.TIME_SECONDS),
                  "frequency": position.get_frequency(Units.FREQUENCY_HERTZ),
                  "delay": position.get_delay(Units.TIME_SECONDS),
                  "position": np.asarray(position_samples)}
        
            if self.save_velocity:
                result["velocity"] = np.asarray(velocity_samples)

            return result