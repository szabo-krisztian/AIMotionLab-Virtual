from typing import Union
from classes.controller_base import ControllerBase
import numpy as np


class InputTimeSeriesController(ControllerBase):
    def __init__(self, d: Union[list, np.ndarray, None] = None, delta: Union[list, np.ndarray, None] = None):
        """Controller implementation to apply a time series of predefined control inputs to the car, for open loop simulation and control

        Args:
            d (Union[list, np.ndarray, None], optional): Motor PWM reference. Defaults to None
            delta (Union[list, np.ndarray, None], optional): Steering angle. Defaults to None.
        """

        # set timeseries data
        self.d_series=d
        self.delta_series=delta

        # iterator
        self.i=0


    def reload_timeseries(self, d:  Union[list, np.ndarray], delta:  Union[list, np.ndarray]):
        """Reloads the control input timeseries data

        Args:
            d (Union[list, np.ndarray, None], optional): Motor PWM reference.
            delta (Union[list, np.ndarray, None], optional): Steering angle. 
        """

        # set timeseries data
        self.d_series=d
        self.delta_series=delta

        # iterator
        self.i=0


    def compute_control(self, state: dict, setpoint: dict, time, **kwargs) -> np.array:
        """Method for calculating the control input, based on the current state and setpoints

        Args:
            state (dict): Dict containing the state variables
            setpoint (dict): Setpoint determined by the trajectory object
            time (float): Current simuator time

        Returns:
            np.array: Computed control inputs [d, delta]
        """

        # return zero inputs is the timeseries has been successfully executed
        if self.i>len(self.d_series)-1:
            return np.zeros(2)


        u=np.array([self.d_series[self.i], self.delta_series[self.i]])
        self.i+=1

        return u

     