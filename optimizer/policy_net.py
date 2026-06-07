"""
模仿学习策略网络：
  输入 state（来自 lyapunov_solver.build_state_vector）
  输出 N 个网关的 logits → argmax 即网关选择
  训练目标：行为克隆 Lyapunov 在线/离线最优解给出的 action

为什么是模仿学习而不是 DRL？
  - 卫星星历完全可预测，Lyapunov 求解器已能给出近最优解
  - DRL 训练不稳定、决策耗 GPU；模仿学习一次离线训练好，星上部署只需 <1ms 推理
  - 论文里可同时报告"Lyapunov 在线（理论最优）"与"IL 网络（部署友好）"
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from config import CFG, CKPT_DIR, TB_DIR, get_device


# --------------------------- 策略网络 ---------------------------
class GatewayPolicyNet(nn.Module):
    def __init__(self, state_dim: int, num_gateways: int,
                 hidden_dim: int = None, num_layers: int = None,
                 dropout: float = None):
        super().__init__()
        hidden_dim = hidden_dim or CFG.il_hidden_dim
        num_layers = num_layers or CFG.il_num_layers
        dropout = dropout if dropout is not None else CFG.il_dropout

        layers = [nn.Linear(state_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)]
        for _ in range(num_layers - 1):
            layers += [nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)]
        layers += [nn.Linear(hidden_dim, num_gateways)]
        self.net = nn.Sequential(*layers)
        self.state_dim = state_dim
        self.num_gateways = num_gateways

    def forward(self, x):
        return self.net(x)

    def predict(self, state: np.ndarray, visible_mask: np.ndarray | None = None) -> int:
        """单步推理：返回网关 index。visible_mask 用于屏蔽不可见网关。"""
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(state.astype(np.float32)).unsqueeze(0).to(next(self.parameters()).device)
            logits = self.net(x).cpu().numpy()[0]
            if visible_mask is not None:
                logits = np.where(visible_mask.astype(bool), logits, -1e9)
            return int(np.argmax(logits))


# --------------------------- 训练数据集 ---------------------------
@dataclass
class ILDataset:
    states: np.ndarray   # (M, state_dim)
    actions: np.ndarray  # (M,) int

    def to_tensor(self):
        return (torch.from_numpy(self.states.astype(np.float32)),
                torch.from_numpy(self.actions.astype(np.int64)))


def build_il_dataset(trajectories: list) -> ILDataset:
    """把多条 LyapunovTrajectory 拼成一个监督数据集。"""
    all_s, all_a = [], []
    for traj in trajectories:
        all_s.append(traj.states)
        all_a.append(traj.actions)
    return ILDataset(states=np.concatenate(all_s, axis=0),
                     actions=np.concatenate(all_a, axis=0))


def build_dagger_dataset(topo, loads_list, lyap_fn,
                         num_perturbations: int = 3,
                         perturb_sigma: float = 0.1) -> ILDataset:
    """
    DAgger 风格的数据扩增：除了"专家在专家状态下"的轨迹，还在状态上叠加扰动，
    让网络见到更多 (state, expert action) 配对，避免单一类别过拟合。

    lyap_fn(topo, loads) -> LyapunovTrajectory
    """
    all_s, all_a = [], []
    for loads in loads_list:
        traj = lyap_fn(topo, loads)
        all_s.append(traj.states)
        all_a.append(traj.actions)
        # 扰动版本：在 state（特别是 loads 部分）上加噪，专家动作不变
        for k in range(num_perturbations):
            rng = np.random.default_rng(hash((id(loads), k)) % (2 ** 32))
            noisy = traj.states + rng.normal(0, perturb_sigma,
                                              size=traj.states.shape).astype(np.float32)
            all_s.append(noisy)
            all_a.append(traj.actions)
    return ILDataset(states=np.concatenate(all_s, axis=0),
                     actions=np.concatenate(all_a, axis=0))


# --------------------------- 训练循环 ---------------------------
def train_il(ds: ILDataset, num_gateways: int,
             epochs: int = None, batch_size: int = None,
             lr: float = None, val_ratio: float = 0.2,
             tag: str = "il", verbose: bool = True) -> dict:
    epochs = epochs or CFG.il_epochs
    batch_size = batch_size or CFG.il_batch_size
    lr = lr or CFG.il_learning_rate

    device = get_device()
    state_dim = ds.states.shape[1]
    model = GatewayPolicyNet(state_dim, num_gateways).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    crit = nn.CrossEntropyLoss()

    X, Y = ds.to_tensor()
    full = TensorDataset(X, Y)
    n_val = int(len(full) * val_ratio)
    n_train = len(full) - n_val
    train_set, val_set = random_split(
        full, [n_train, n_val],
        generator=torch.Generator().manual_seed(CFG.seed),
    )
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size)

    writer = SummaryWriter(log_dir=TB_DIR / tag)
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for ep in range(epochs):
        model.train()
        loss_sum, n = 0.0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            loss = crit(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            loss_sum += loss.item() * len(xb)
            n += len(xb)
        tr_loss = loss_sum / max(1, n)

        # 验证
        model.eval()
        v_loss, v_correct, v_n = 0.0, 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                v_loss += crit(logits, yb).item() * len(xb)
                v_correct += (logits.argmax(-1) == yb).sum().item()
                v_n += len(xb)
        v_loss /= max(1, v_n)
        v_acc = v_correct / max(1, v_n)

        history["train_loss"].append(tr_loss)
        history["val_loss"].append(v_loss)
        history["val_acc"].append(v_acc)
        writer.add_scalar("loss/train", tr_loss, ep)
        writer.add_scalar("loss/val", v_loss, ep)
        writer.add_scalar("acc/val", v_acc, ep)
        if verbose:
            print(f"[IL ep {ep:02d}] train_loss={tr_loss:.4f} "
                  f"val_loss={v_loss:.4f} val_acc={v_acc:.4f}")

    writer.close()
    ckpt_fp = CKPT_DIR / f"{tag}.pt"
    torch.save({
        "model_state": model.state_dict(),
        "state_dim": state_dim,
        "num_gateways": num_gateways,
        "history": history,
    }, ckpt_fp)
    return {"model": model, "ckpt": ckpt_fp, "history": history, "device": device}


def load_policy(ckpt_fp: Path, device=None) -> GatewayPolicyNet:
    device = device or get_device()
    payload = torch.load(ckpt_fp, map_location=device, weights_only=False)
    m = GatewayPolicyNet(payload["state_dim"], payload["num_gateways"]).to(device)
    m.load_state_dict(payload["model_state"])
    m.eval()
    return m


if __name__ == "__main__":
    # 自检：生成多条 trajectory → 训练 → 测推理速度
    import time
    from orbit.topology import get_or_build_topology
    from optimizer.lyapunov_solver import (
        lyapunov_online, synthesize_gateway_loads,
    )

    topo, _, _ = get_or_build_topology("smoke", 600.0, step_sec=1.0, use_fallback_tle=True)
    rng = np.random.default_rng(0)
    trajs = []
    for i in range(8):
        loads = synthesize_gateway_loads(topo.num_gateways, topo.num_steps,
                                         np.random.default_rng(i))
        trajs.append(lyapunov_online(topo, loads))
    ds = build_il_dataset(trajs)
    print(f"[IL] dataset size: {len(ds.states)} state_dim={ds.states.shape[1]}")
    out = train_il(ds, topo.num_gateways, epochs=8, tag="smoke_il", verbose=True)

    # 推理延迟
    m = out["model"]
    state = ds.states[0]
    t0 = time.perf_counter()
    for _ in range(1000):
        m.predict(state)
    elapsed = (time.perf_counter() - t0) / 1000 * 1000
    print(f"[IL] avg inference latency: {elapsed:.3f} ms")
