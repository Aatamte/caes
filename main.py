from src.core import Agent, Environment
from src.core import Order, Dialogue, Marketplace
from src.agents.language_model_agents.openai_agent import OAIAgent
from src.agents.population import Population
import numpy as np
import openai


class MyAgent(OAIAgent):
    def __init__(self):
        super(MyAgent, self).__init__()
        self.starting_inventory = {
            "capital": 10000,
            "socks": 100,
            "banana": 10,
            "iphones": 10
        }

    def select_action(self):
        if self.params["is_buyer"]:
            quantity = 1
            price = np.random.randint(85, 100)
        else:
            quantity = -1
            price = np.random.randint(90, 105)

        if np.random.randint(0, 100) > 50:
            return Order(good="banana", price=price, quantity=quantity, agent=self)
        else:
            return None


if __name__ == '__main__':
    openai.api_key = "sk-"
    env = Environment(
        visualization=True,
        save_to_file=True
    )

    buyer_params = {"is_buyer": True}

    seller_params = {"is_buyer": False}

    buyer_population = Population(MyAgent(), 5, buyer_params)
    env.add(buyer_population)

    seller_population = Population(MyAgent(), 5, seller_params)
    env.add(seller_population)

    marketplace = Marketplace()

    env.add(marketplace)

    env.step_delay = 1

    env.max_episodes = 1
    env.max_steps = 50

    # set up the environment
    env.set_up()

    while env.is_running():
        for step in env.iter_steps():
            current_episode = env.current_episode
            env.step()
