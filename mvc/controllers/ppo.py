import numpy as np

from mvc.models.metrics import Metrics
from mvc.models.rollout import Rollout
from mvc.models.networks.base_network import BaseNetwork
from mvc.controllers.base_controller import BaseController


class PPOController(BaseController):
    def __init__(self,
                 network,
                 rollout,
                 metrics,
                 num_envs,
                 time_horizon,
                 epoch,
                 batch_size,
                 gamma,
                 lam,
                 final_steps=10 ** 6,
                 log_interval=None,
                 save_interval=10 ** 5,
                 eval_interval=10 ** 5):
        assert isinstance(network, BaseNetwork)
        assert isinstance(rollout, Rollout)
        assert isinstance(metrics, Metrics)

        self.network = network
        self.rollout = rollout
        self.metrics = metrics
        self.num_envs = num_envs
        self.time_horizon = time_horizon
        self.epoch = epoch
        self.batch_size = batch_size
        self.gamma = gamma
        self.lam = lam

        self.metrics.register('step', 'single')
        self.metrics.register('loss', 'queue')
        self.metrics.register('reward', 'queue')

        log_interval = time_horizon if not log_interval else log_interval
        super().__init__(metrics, final_steps, log_interval,
                         save_interval, eval_interval)

    def step(self, obs, reward, done, info):
        # infer action, policy, value
        output = self.network.infer(obs_t=obs)
        # store trajectory
        self.rollout.add(obs, output.action, reward,
                         output.value, output.log_prob, done)

        # record metrics
        self.metrics.add('step', self.num_envs)
        for i in range(self.num_envs):
            if done[i] == 1.0:
                self.metrics.add('reward', info[i]['reward'])

        return output.action

    def should_update(self):
        return self.rollout.size() - 1 == self.time_horizon

    def update(self):
        assert self.should_update()

        # create batch from stored trajectories
        batches = self._batches()

        # flush stored trajectories
        self.rollout.flush()

        # update parameter
        losses = []
        for _ in range(self.epoch):
            for batch in batches:
                loss = self.network.update(**batch)
                losses.append(loss)
        mean_loss = np.mean(losses)

        # record metrics
        self.metrics.add('loss', mean_loss)

        return mean_loss

    def log(self):
        step = self.metrics.get('step')
        self.metrics.log_metric('reward', step)
        self.metrics.log_metric('loss', step)

    def stop_episode(self, obs, reward, info):
        pass

    def _batches(self):
        traj = self.rollout.fetch(self.gamma, self.lam)

        # flatten
        data_size = self.time_horizon * self.num_envs
        state_shape = traj['obs_t'].shape[2:]
        flat_obs_t = np.reshape(traj['obs_t'], (data_size,) + state_shape)
        flat_actions_t = np.reshape(traj['actions_t'], (data_size, -1))
        flat_log_probs_t = np.reshape(traj['log_probs_t'], (data_size, -1))
        flat_returns_t = np.reshape(traj['returns_t'], (-1,))
        flat_advantages_t = np.reshape(traj['advantages_t'], (-1,))
        flat_values_t = np.reshape(traj['values_t'], (-1,))

        # create batch data
        indices = np.random.permutation(np.arange(data_size))
        batches = []
        for i in range(data_size // self.batch_size):
            index = indices[self.batch_size * i:self.batch_size * (i + 1)]
            batch = {
                'obs_t': flat_obs_t[index],
                'actions_t': flat_actions_t[index],
                'log_probs_t': flat_log_probs_t[index],
                'returns_t': flat_returns_t[index],
                'advantages_t': flat_advantages_t[index],
                'values_t': flat_values_t[index]
            }
            batches.append(batch)

        return batches
