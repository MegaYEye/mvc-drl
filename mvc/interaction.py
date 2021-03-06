import numpy as np


def initial_inputs(env):
    obs = env.reset()
    reward = np.zeros((obs.shape[0],), dtype=np.float32)
    done = np.zeros((obs.shape[0],), dtype=np.float32)
    info = {}
    return obs, reward, done, info


def step(env, view, obs, reward, done, info):
    action = view.step(obs, reward, done, info)
    obs, reward, done, info = env.step(action)
    return obs, reward, done, info


def batch_loop(env, view, hook=None):
    obs, reward, done, info = initial_inputs(env)
    while True:
        obs, reward, done, info = step(env, view, obs, reward, done, info)

        if hook is not None:
            hook(view)

        if view.is_finished():
            break


def loop(env, view, hook=None):
    while True:
        obs = env.reset()
        reward = 0.0
        done = False
        info = {}
        while not done:
            obs, reward, done, info = step(env, view, obs, reward, done, info)

            if hook is not None:
                hook(view)

            if view.is_finished():
                return

        view.stop_episode(obs, reward, info)


def batch_interact(env, view, eval_env=None, eval_view=None, hook=None):
    def _hook(view):
        if eval_view is not None and view.should_eval():
            batch_loop(eval_env, eval_view)

        if hook is not None:
            hook(view)

    batch_loop(env, view, _hook)


def interact(env, view, eval_env=None, eval_view=None, hook=None):
    def _hook(view):
        if eval_view is not None and view.should_eval():
            loop(eval_env, eval_view)

        if hook is not None:
            hook(view)

    loop(env, view, _hook)
