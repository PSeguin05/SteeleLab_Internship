import numpy as np
import csv

import logging
logging.basicConfig(format = "[%(name)s] %(message)s",
                            level = logging.INFO)

from types import TracebackType
from typing import Type

from zaber_motion import Units
from zaber_motion.ascii import Connection

class zaber_linear_stage:

    # Initialization and context management

    def __init__(self,
                 port: str,
                 label: str = "Zaber Motor",
                 axis_number: int = 1,
                 auto_home: bool = True,
                 auto_close: bool = True,
                 default_velocity: float = None,
                 default_acceleration: float = None,
                 wait_until_idle: bool = True
                 ) -> None:
        
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

        self.connection = Connection.open_serial_port(port_name = self.port)
        self.connection.enable_alerts()

        self.devices = self.connection.detect_devices()
        if len(self.devices) == 0:
            raise RuntimeError(f"No detected device on {self.port}")
        
        self.logger.info(f"{len(self.devices)} device(s) detected")

        self.device = self.devices[0]
        self.axis = self.device.get_axis(self.axis_number)

        if not self.axis.settings.get("driver.enabled"):
            self.axis.driver_enable()
            self.logger.info(f"Driver ENABLE")

        if auto_home:
            self.logger.info(f"Homing...")
            self.axis.home()
            self.logger.info(f"Homed")
        
        self.scope = self.device.oscilloscope
        self.scope.clear()

        self.logger.info(f"READY!")
    
    def __enter__(self
                  ) -> "Zaber_Linear_Stage":
        
        return self

    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_val: BaseException,
                 exc_tb: TracebackType
                 ) -> bool:
        
        if self.auto_close:
            self.close()
        return False
    
    def __repr__(self
                 ) -> str:
        
        return (f"Zaber_Linear_Stage(port={self.port!r}, "
                f"label={self.label!r}, axis={self.axis_number})")
    
    # Internal methods for parameter checking and assertions
    # These functions are not meant to be called directly by the user.
    
    def _check_bounds(self,
                      position: float
                      ) -> None:
        
        position_min = self.axis.settings.get("limit.min", Units.LENGTH_MILLIMETRES)
        position_max = self.axis.settings.get("limit.max", Units.LENGTH_MILLIMETRES)
        if not (position_min <= position <= position_max):
            raise ValueError(f"Position {position} mm out of range [{position_min:.3f}, {position_max:.3f}] mm")
        
    
    def _check_velocity(self,
                        velocity: float
                        ) -> None:
        
        velocity_min = 0
        velocity_max = self.axis.settings.get("maxspeed.max", Units.VELOCITY_MILLIMETRES_PER_SECOND)
        if not (velocity_min <= velocity <= velocity_max):
            raise ValueError(f"Velocity {velocity} mm/s out of range [{velocity_min:.3f}, {velocity_max:.3f}] mm/s")
    
    def _check_acceleration(self,
                            acceleration: float
                            ) -> None:
        
        acceleration_min = 0
        acceleration_max = self.axis.settings.get("accel", Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED)
        if not (acceleration_min <= acceleration <= acceleration_max):
            raise ValueError(f"Acceleration {acceleration} mm/s^2 out of range [{acceleration_min:.3f}, {acceleration_max:.3f}] mm/s^2")
    
    def _check_parameters(self,
                          position: float = None,
                          velocity: float = None,
                          acceleration: float = None
                          ) -> None:
        
        if position is not None:
            self._check_bounds(position)
        if velocity is not None:
            self._check_velocity(velocity)
        if acceleration is not None:
            self._check_acceleration(acceleration)

    def _assert_enabled(self
                        ) -> None:
        
        if not bool(self.axis.settings.get("driver.enabled")):
            raise RuntimeError(f"[{self.label}] Driver is disabled. Call enable() first.")
    
    def _assert_scope_configured(self
                                 ) -> None:
        
        if not self._scope_configured:
            raise RuntimeError(
                f"[{self.label}] Scope not configured. Call scope_config() first."
        )
    
    def _motion_kwargs(self,
                       velocity: float = None,
                       acceleration: float = None,
                       **extra
                       ) -> dict:
        
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
    
    # Basic control methods

    def close(self
              ) -> None:
        
        self.connection.close()
        self.logger.info(f"Connection closed.")
    
    def enable(self
               ) -> None:
        
        self.axis.driver_enable()
        self.logger.info(f"Driver ENABLE")
    
    def disable(self
                ) -> None:
        
        self.axis.driver_disable()
        self.logger.info(f"Driver DISABLE")
    
    # Get information and parameters

    def get_position(self
                     ) -> float:
        
        position = self.axis.get_position(unit = Units.LENGTH_MILLIMETRES)
        self.logger.info(f"Position = {position:.6f} mm")

        return position
    
    def get_params(self
                   ) -> dict:
        
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
    
    # Control methods

    def home(self
             ) -> None:
        
        self._assert_enabled()
        self.logger.info(f"Homing...")
        self.axis.home(wait_until_idle = self.wait)
        self.logger.info(f"Homed.")
    
    def move_absolute(self,
                      position: float,
                      velocity: float = None,
                      acceleration: float = None
                      ) -> None:
        
        self._check_parameters(position = position,
                               velocity = velocity,
                               acceleration = acceleration)
        if acceleration is not None:
            self._check_acceleration(acceleration)
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
        
        self._check_parameters(velocity = velocity,
                               acceleration = acceleration)
        self._assert_enabled()
        self.axis.move_max(**self._motion_kwargs(velocity = velocity,
                                                 acceleration = acceleration
                                                 ))
    
    def move_sin(self,
                 amplitude: float,
                 period: float,
                 count: int = 1
                 ) -> None:
        
        current_position = self.axis.get_position(unit = Units.LENGTH_MILLIMETRES)
        self._check_bounds(current_position + amplitude)
        self._check_bounds(current_position - amplitude)
        self._check_parameters(velocity = (2*np.pi / period) * amplitude,
                               acceleration = ((2*np.pi / period)**2) * amplitude)
        self._assert_enabled()
        self.axis.move_sin(amplitude = amplitude,
                           amplitude_units = Units.LENGTH_MILLIMETRES,
                           period = period,
                           period_units = Units.TIME_SECONDS,
                           count = count,
                           wait_until_idle = self.wait)
    
    def stop(self
             ) -> None:
        
        self.logger.info(f"STOPPING...")
        self.axis.stop(wait_until_idle = self.wait)
        self.logger.info(f"STOPPED")
    
    def wait_until_idle(self
                        ) -> None:
        
        self.axis.wait_until_idle()
    
    def scope_config(self,
                     interval: float = 1e-2,
                     save_velocity: bool = False
                     ) -> None:
        
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
        
        self._assert_scope_configured()
        self.scope.start()
        self.logger.info(f"Scope STARTED")
    
    def scope_stop(self
                   ) -> None:
        
        self._assert_scope_configured()
        self.scope.stop()
        self.logger.info(f"Scope STOPPED")
    
    def scope_save(self,
                   filename: str = "Scope.csv",
                   save_csv: bool = True,
                   return_dict: bool = True
                   ) -> dict:
        
        self._assert_scope_configured()

        if not save_csv and not return_dict:
            self.logger.warning("scope_saving_data() called with save_csv=False and return_dict=False — nothing to do.")

        self.logger.info("Reading scope data...")
        data = self.scope.read()

        position = data[0]
        position_samples = position.get_data(Units.LENGTH_MILLIMETRES)

        times = position.get_sample_times(Units.TIME_SECONDS)

        if self.save_velocity:
            velocity = data[1]
            velocity_samples = velocity.get_data(Units.VELOCITY_MILLIMETRES_PER_SECOND)

        if save_csv:
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