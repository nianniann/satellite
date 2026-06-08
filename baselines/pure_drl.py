"""
Baseline 4 — Pure DRL (DQN)：
  消融对比。state、reward 与 Lyapunov 一致，但用 DQN 学切换策略。
  论文中用来证明：在星历完全可预测的场景下，DRL 并不比 Lyapunov 好（甚至更差）。
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from config import CFG, CKPT_DIR, get_device
from optimizer.lyapunov_solver import (
    build_state_vector, synthesize_gateway_loads,
)
from orbit.topology import TopologySnapshot


class QNet(nn.Module):
    def __init__(self, state_dim: int, num_actions: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            nn.Linear(hidden_dim, num_actions),
        )

    def forward(self, x):
        return self.net(x)


@dataclass
class Transition:
    s: np.ndarray
    a: int
    r: float
    s_next: np.ndarray
    done: bool


class ReplayBuffer:
    def __init__(self, capacity: int = 5000):
        self.buf = deque(maxlen=capacity)

    def push(self, t: Transition):
        self.buf.append(t)

    def sample(self, batch: int):
        idx = random.sample(range(len(self.buf)), batch)
        S = np.array([self.buf[i].s for i in idx], dtype=np.float32)
        A = np.array([self.buf[i].a for i in idx], dtype=np.int64)
        R = np.array([self.buf[i].r for i in idx], dtype=np.float32)
        Sn = np.array([self.buf[i].s_next for i in idx], dtype=np.float32)
        D = np.array([self.buf[i].done for i in idx], dtype=np.float32)
        return S, A, R, Sn, D

    def __len__(self):
        return len(self.buf)


def _step_reward(topo: TopologySnapshot, loads: np.ndarray, t_idx: int,
                 cur_gw: int, new_gw: int,
                 alpha: float, beta: float, gamma_switch: float,
                 interruption_horizon_sec: float = 5.0) -> float:
    rem = topo.remaining_visibility(t_idx)
    vis = topo.visible[t_idx]
    interrupt = (not vis[new_gw]) or (rem[new_gw] < interruption_horizon_sec)
    is_switch = int(new_gw != cur_gw)
    cost = alpha * (1.0 if interrupt else 0.0) + beta * loads[t_idx, new_gw] + gamma_switch * is_switch
    return -cost


def train_dqn(topos: list[TopologySnapshot], loads_list: list[np.ndarray],
              epochs: int = 30, batch_size: int = 64,
              gamma: float = 0.95, lr: float = 1e-3,
              eps_start: float = 1.0, eps_end: float = 0.05,
              eps_decay: float = 0.995,
              alpha: float = None, beta: float = None,
              tag: str = "dqn", verbose: bool = True) -> dict:
    alpha = alpha if alpha is not None else CFG.alpha
    beta = beta if beta is not None else CFG.beta
    gamma_switch = 0.5

    device = get_device()
    n_act = topos[0].num_gateways
    state_dim = 4 * n_act + n_act
    q = QNet(state_dim, n_act).to(device)
    tgt = QNet(state_dim, n_act).to(device)
    tgt.load_state_dict(q.state_dict())
    opt = torch.optim.AdamW(q.parameters(), lr=lr)
    crit = nn.SmoothL1Loss()
    buf = ReplayBuffer(20000)
    eps = eps_start
    history = []

    from tqdm import tqdm as _tqdm
    pbar = _tqdm(range(epochs), desc=f"DQN[{tag}]", disable=not verbose)
    for ep in pbar:
        ep_reward = 0.0
        for topo, loads in zip(topos, loads_list):
            cur_gw = int(np.argmax(topo.remaining_visibility(0))) if topo.remaining_visibility(0).max() > 0 else 0
            for t in range(topo.num_steps - 1):
                s = build_state_vector(topo, t, loads, cur_gw)
                if random.random() < eps:
                    a = random.randrange(n_act)
                else:
                    with torch.no_grad():
                        a = int(q(torch.from_numpy(s).unsqueeze(0).to(device)).argmax(-1).item())
                r = _step_reward(topo, loads, t + 1, cur_gw, a,
                                 alpha, beta, gamma_switch)
                s_next = build_state_vector(topo, t + 1, loads, a)
                done = (t + 1 == topo.num_steps - 1)
                buf.push(Transition(s, a, r, s_next, done))
                cur_gw = a
                ep_reward += r

                if len(buf) >= batch_size:
                    S, A, R, Sn, D = buf.sample(batch_size)
                    S = torch.from_numpy(S).to(device)
                    A = torch.from_numpy(A).to(device)
                    R = torch.from_numpy(R).to(device)
                    Sn = torch.from_numpy(Sn).to(device)
                    D = torch.from_numpy(D).to(device)
                    q_sa = q(S).gather(1, A.unsqueeze(1)).squeeze(1)
                    with torch.no_grad():
                        q_next = tgt(Sn).max(-1).values
                        target = R + gamma * q_next * (1 - D)
                    loss = crit(q_sa, target)
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
        if ep % 5 == 0:
            tgt.load_state_dict(q.state_dict())
        eps = max(eps_end, eps * eps_decay)
        history.append(ep_reward / max(1, sum(t.num_steps for t in topos)))
        pbar.set_postfix(reward=f"{history[-1]:.4f}", eps=f"{eps:.3f}")

    ckpt_fp = CKPT_DIR / f"{tag}.pt"
    torch.save({"model_state": q.state_dict(),
                "state_dim": state_dim, "num_actions": n_act,
                "history": history}, ckpt_fp)
    return {"model": q, "device": device, "history": history, "ckpt": ckpt_fp}


def dqn_decision_fn(model: QNet, topo: TopologySnapshot, loads: np.ndarray, device):
    state = {"current_gw": None}

    def decide(t_idx: int) -> int:
        if state["current_gw"] is None:
            r0 = topo.remaining_visibility(0)
            state["current_gw"] = int(np.argmax(r0)) if r0.max() > 0 else 0
        s = build_state_vector(topo, t_idx, loads, state["current_gw"])
        with torch.no_grad():
            a = int(model(torch.from_numpy(s).unsqueeze(0).to(device)).argmax(-1).item())
        # 屏蔽不可见
        if not topo.visible[t_idx, a]:
            rem = topo.remaining_visibility(t_idx)
            a = int(np.argmax(rem)) if rem.max() > 0 else a
        state["current_gw"] = a
        return a

    return decide
