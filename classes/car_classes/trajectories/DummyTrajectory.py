from classes.trajectory_base import TrajectoryBase



class DummyTrajectory(TrajectoryBase):
    def __init__(self):
        """Dummy trajectory implementation to serve as a placeholder, when the trajectory evaluation is also part of the controller imlementaiton class
        """
        super().__init__()


    def evaluate(self, state, i, time, control_step) -> dict:
        # return empy dictto overwrite NotImplementedError
        return {}