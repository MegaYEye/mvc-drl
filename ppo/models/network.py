class Network:
    def infer(self, **kwargs):
        for key in self._infer_arguments():
            assert key in kwargs, key + ' does not exist in the arguments'
        return self._infer(*kwargs)

    def update(self, **kwargs):
        for key in self._update_arguments():
            assert key in kwargs, key + ' does not exist in the arguments'
        return self._update(*kwargs)

    def _infer(self, **kwargs):
        raise NotImplementedError()

    def _update(self, **kwargs):
        raise NotImplementedError()

    def _infer_arguments(self):
        raise NotImplementedError()

    def _update_arguments(self):
        raise NotImplementedError()


class PPONetwork(Network):
    def __init__(self,
                 function,
                 state_shape,
                 num_envs,
                 num_actions,
                 time_horizon,
                 grad_clip,
                 lr):
        self._build(function state_shape, num_envs num_actions,
                    time_horizon, grad_clip, lr)

    def _infer(self, **kwargs):
        feed_dict = {
            self.step_obs_ph: kwargs['obs_t'],
        }
        sess = tf.get_default_session()
        ops = [self.action, self.log_policy, self.step_value]
        return sess.run(ops, feed_dict=feed_dict)

    def _update(self, **kwargs):
        feed_dict = {
            self.train_obs_ph: kwargs['obs_t'],
            self.actions_ph: kwargs['actions_t'],
            self.returns_ph: kwargs['returns_t'],
            self.advantages_ph: kwargs['advantages_t'],
            self.old_log_probs_ph: kwargs['log_probs_t']
        }
        sess = tf.get_default_session()
        return sess.run([self.loss, self.optimize_expr], feed_dict=feed_dict)[0]

    def _build(self,
               function,
               state_shape,
               num_envs,
               num_actions,
               time_horizon,
               grad_clip,
               lr):
        batch_size = nenvs * time_horizon
        with tf.variable_scope('ppo', reuse=tf.AUTO_REUSE):
            # placeholers
            step_obs_ph = self.step_obs_ph = tf.placeholder(
                tf.float32, [nenvs] + state_shape, name='step_obs')
            # for recurrent version extension
            train_obs_ph = self.train_obs_ph = tf.placeholder(
                tf.float32, [batch_size] + state_shape, name='train_obs')
            returns_ph = self.returns_t = tf.placeholder(
                tf.float32, [None], name='returns')
            advantages_ph = self.advantages_ph = tf.placeholder(
                tf.float32, [None], name='advantages')
            actions_ph = self.actions_ph = tf.placeholder(
                tf.float32, [batch_size, num_actions], name='action')
            old_log_probs_ph = self.old_log_probs_ph = tf.placeholder(
                tf.float32, [batch_size, num_actions], name='old_log_prob')

            # network outputs for inference
            step_dist, self.step_value = function(step_obs_ph)
            # network outputs for training
            train_dist, train_value = model(train_obs_ph)

            # network weights
            network_vars = tf.get_collection(
                tf.GraphKeys.TRAINABLE_VARIABLES, scope)

            # loss
            advantages = tf.reshape(advantages_ph, [-1, 1])
            returns = tf.reshape(returns_ph, [-1, 1])
            with tf.variable_scope('value_loss'):
                value_loss = tf.reduce_mean(tf.square(returns - train_value))
                value_loss *= value_factor
            with tf.variable_scope('entropy'):
                entropy = tf.reduce_mean(train_dist.entropy())
                entropy *= entropy_factor
            with tf.variable_scope('policy_loss'):
                log_prob = train_dist.log_prob(actions_ph)
                ratio = tf.exp(log_prob - old_log_probs_ph)
                ratio = tf.reduce_mean(ratio, axis=1, keep_dims=True)
                surr1 = ratio * advantages
                surr2 = tf.clip_by_value(
                    ratio, 1.0 - epsilon, 1.0 + epsilon) * advantages
                surr = tf.minimum(surr1, surr2)
                policy_loss = tf.reduce_mean(surr)
            self.loss = value_loss - policy_loss - entropy

            # gradients
            gradients = tf.gradients(self.loss, network_vars)
            clipped_gradients, _ = tf.clip_by_global_norm(gradients, grad_clip)
            # update
            grads_and_vars = zip(clipped_gradients, network_vars)
            optimizer = tf.train.AdamOptimizer(lr, epsilon=1e-5)
            self.optimize_expr = optimizer.apply_gradients(grads_and_vars)

            # action
            self.action = step_dist.sample(1)[0]
            self.log_policy = step_dist.log_prob(action)

    def _infer_arguments(self):
        return ['obs_t']

    def _update_arguments(self):
        return [
            'obs_t', 'actions_t', 'log_probs_t', 'returns_t', 'advantages_t'
        ]
