import numpy as np
import logging
from src.agents.base_agent import Agent
from src.environment.artifacts.artifact import Artifact, ArtifactController
#from src.visualization.app import Visualizer
from src.new_visualization.visualizer import Visualizer
import h5py
import names
import asyncio
import random
import dearpygui.dearpygui as dpg


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


class UnsupportedItemType(Exception):
    """Exception raised when an unsupported item is added to the environment."""


def generate_random_adjacency_matrix(size):
    # Generate a random adjacency matrix with values from 0 to max_line_thickness
    adjacency_matrix = [[random.randint(0, 1) for _ in range(size)] for _ in range(size)]

    # Since adjacency matrix is symmetric, we copy the lower triangle to the upper triangle
    for i in range(size):
        for j in range(i+1, size):
            adjacency_matrix[i][j] = adjacency_matrix[j][i]

    return adjacency_matrix


class Environment:
    def __init__(
        self,
        name: str = "default environment",
        record_environment: bool = False,
        enable_visualization: bool = False,
        verbose: int = 0,
        seed: int = None
    ):
        """
        Initialize the environment.

        :param name: Name of the environment
        :param record_environment: Whether to record the environment
        :param verbose: Verbosity level
        :param seed: Seed for random number generation
        :param filename: Name of the file to record the environment
        """
        self.name = name
        self.verbose = verbose
        self.seed = seed
        self.enable_visualization = enable_visualization

        self.should_stop_simulation = False
        self.is_first_step = True

        self.current_step = 0
        self.max_steps = 100

        self.current_episode = 0
        self.max_episodes = 1

        # artifacts
        self.artifact_controller = ArtifactController()

        # agent attributes
        self.agents = []
        self.agent_names = []
        self.n_agents = 0
        self.agent_idx = 0
        self.agent_name_lookup = {}
        self.agent_id_lookup = {}

        # logger
        console_handler.setLevel(logging.CRITICAL)
        logger.addHandler(console_handler)

        self.should_record = record_environment

        if self.should_record:
            self.recorder = RecordedEnvironment("env_record.hdf5")

        if self.enable_visualization:
            self.visualizer = Visualizer(self)

    def add_agent(self, agent: Agent):
        """
        Add a new agent to the environment.

        :param agent: An Agent object
        """
        agent.id = self.agent_idx
        self.agent_idx += 1
        if agent.name in [a.name for a in self.agents]:
            agent.name = names.get_first_name()
        self.agent_names.append(agent.name)
        self.agents.append(agent)
        self.agent_name_lookup[agent.name] = agent
        self.n_agents = len(self.agents)

    def add_artifact(self, artifact: Artifact):
        """
        Add a new artifact to the environment.

        :param artifact: An Artifact object
        """
        self.artifact_controller.add_artifact(artifact)

    def add(self, item):
        """
        Add a new item (agent, artifact, or list) to the environment.

        :param item: Item to be added
        """
        if isinstance(item, Artifact):
            self.add_artifact(item)
        elif isinstance(item, Agent):
            self.add_agent(item)
        elif isinstance(item, list):
            for it in item:
                self.add(it)
        else:
            raise UnsupportedItemType()

    def _initialize(self):
        pass

    def reset(self) -> [np.ndarray, dict]:
        """
        Resets the environment
        """
        if not self.agents:
            raise ValueError("agents must be passed through the <set_agents> function before  "
                             "the first episode is run")
        self.current_step = 0
        self.current_episode += 1

        # reset each agent
        for agent in self.agents:
            agent.reset()

        # reset artifacts
        self.artifact_controller.reset(self)

        if self.enable_visualization:
            self.visualizer.reset(self)

        return 0

    def record_step(func):
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.recorder.save_step(env=self)
            return result
        return wrapper

    def update_simulation_state(self):
        self.current_step += 1
        if self.current_step >= self.max_steps:
            self.current_episode += 1
            self.current_step = 0
        if self.current_episode >= self.max_episodes:
            self.should_stop_simulation = True

    def step(self) -> [np.ndarray, list, list]:
        # after all actions are processed
        self.artifact_controller.execute(self.agents)

        # insert observations for the agents
        self.artifact_controller.insert_observations(self.agents)

        for agent in self.agents:
            agent.step()

        if self.enable_visualization:
            self.visualizer.step()

        # logic for steps
        should_continue = self.artifact_controller.should_continue()
        self.update_simulation_state()
        return should_continue

    def run(self):
        if self.enable_visualization:
            self.reset()
            asyncio.run(self.visualizer.game_loop(self))
        else:
            for episode in range(self.max_episodes):
                self.reset()
                for step in range(self.max_steps):
                    pass

    def action_logs(self):
        return self.artifact_controller.action_logs

    def is_running(self):
        if self.should_stop_simulation:
            del self.visualizer
            return False
        return dpg.is_dearpygui_running()

    def iter_steps(self):
        return range(0, self.max_steps)

    def iter_episodes(self):
        return range(0, self.max_episodes)

    def close(self):
        self.recorder.close()

    def __repr__(self):
        newline = '\n'
        return \
f"""
                        Environment
Episode: {self.current_episode} / {self.max_steps}
Step: {self.current_step} / {self.max_steps}
                        Artifacts 
{str(self.artifact_controller)}
                        Agents
{newline.join([f"{idx}. "+ str(agent.name) for idx, agent in enumerate(self.agents)])}
"""


def env_to_dict(env: Environment):
    return {
        "step": env.current_step,
        "max_steps": env.max_steps,
        "episode": env.current_episode,
        "max_episodes": env.max_episodes,
    }


class RecordedEnvironment:
    def __init__(self, filename):
        self.file = h5py.File(filename, 'w')

    def save_agent(self, agent):
        try:
            agent_group = self.file[str(agent.id)]
        except KeyError:
            agent_group = self.file.create_group(str(agent.id))
        print(agent.inventory.values())
        print(agent.observations)
        action_ds = agent_group.create_dataset(
            f'{agent.name}_{len(agent_group)}',
            data=np.array(list(agent.inventory.values())))
        action_ds.attrs['action'] = agent.action_queue
        for idx, item in enumerate(agent.inventory.inventory.keys()):
            action_ds.attrs[f'item_{idx}'] = item

    def save_environment(self, env):
        try:
            env_group = self.file["environment"]
        except KeyError:
            env_group = self.file.create_group("environment")

        env_ds = env_group.create_group(f"env_{len(env_group)}")
        for key, value in env_to_dict(env).items():
            env_ds.create_dataset(key, data=value)

    def save_step(self, env: Environment):
        self.save_environment(env)

    def close(self):
        self.file.close()

    def print_items(self):
        def print_attrs(name, obj):
            print(name)
            for key, val in obj.attrs.items():
                print("    %s: %s" % (key, val))
            if isinstance(obj, h5py.Dataset):  # check if the object is a dataset
                print("    value:", obj[()])

        with h5py.File("env_record.hdf5", "r") as f:
            f.visititems(print_attrs)


if __name__ == '__main__':
    # Initialize environment
    env = Environment(enable_visualization=False)

    env.run()
