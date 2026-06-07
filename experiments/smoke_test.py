"""端到端小规模冒烟测试：跑通整个 pipeline 但用很小的时长/Epoch。"""
from __future__ import annotations

import experiments.run_all as run_all
import experiments.plot_figures as plot_figures


def main():
    run_all.RUN_CFG.update(
        train_duration_sec=1800.0,
        test_duration_sec=1800.0,
        step_sec=2.0,
        num_train_scenarios=3,
        aos_rate_pps=100.0,
        use_fallback_tle=True,
        il_epochs=15,
        dqn_epochs=6,
    )
    run_all.main()
    plot_figures.main()


if __name__ == "__main__":
    main()
