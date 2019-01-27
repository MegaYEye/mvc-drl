import numpy as np

from mvc.models.metrics import Metrics
from mvc.models.buffer import Buffer
from mvc.models.networks.base_network import BaseNetwork
from mvc.controllers.base_controller import BaseController


class DDPGController(BaseController):
    def __init__(self,
                 network,
                 buffer,
                 metrics,
                 num_actions,
                 batch_size,
                 final_steps=10 ** 6,
                 log_interval=1000,
                 save_interval=10 ** 5,
                 eval_interval=10 ** 5):
        assert isinstance(network, BaseNetwork)
        assert isinstance(buffer, Buffer)
        assert isinstance(metrics, Metrics)

        self.network = network
        self.buffer = buffer
        self.metrics = metrics
        self.num_actions = num_actions
        self.batch_size = batch_size

        self.metrics.register('step', 'single')
        self.metrics.register('critic_loss', 'queue')
        self.metrics.register('actor_loss', 'queue')
        self.metrics.register('reward', 'queue')

        super().__init__(metrics, final_steps, log_interval,
                         save_interval, eval_interval)

    def step(self, obs, reward, done, info):
        # infer action
        output = self.network.infer(obs_t=np.array([obs]))
        # store trajectory
        self.buffer.add(obs, output.action[0], reward, 0.0)
        # record metrics
        self.metrics.add('step', 1)
        return output.action[0]

    def should_update(self):
        return self.buffer.size() + 1 > self.batch_size

    def update(self):
        assert self.should_update()

        # sample batch from replay buffer
        batch = self.buffer.fetch(self.batch_size)

        # update
        critic_loss, actor_loss = self.network.update(**batch)

        # record metrics
        self.metrics.add('critic_loss', critic_loss)
        self.metrics.add('actor_loss', actor_loss)

        return critic_loss, actor_loss

    def log(self):
        step = self.metrics.get('step')
        self.metrics.log_metric('reward', step)
        self.metrics.log_metric('critic_loss', step)
        self.metrics.log_metric('actor_loss', step)

    def stop_episode(self, obs, reward, info):
        # make dummy action
        action = np.zeros((self.num_actions,), dtype=np.float32)
        # store trajectory
        self.buffer.add(obs, action, reward, 1.0)
        # record metrics
        self.metrics.add('reward', info['reward'])
