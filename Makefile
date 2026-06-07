PY = PYTHONPATH=. python3

.PHONY: help install test smoke full figures tb clean

help:
	@echo "make install   - 安装依赖"
	@echo "make test      - 跑 pytest 单元测试 (~1min, CPU)"
	@echo "make smoke     - 小规模冒烟实验 (~5min, CPU)"
	@echo "make full      - 完整实验 + 出图 (~30min, GPU 推荐)"
	@echo "make figures   - 仅基于已有 pkl 重出图"
	@echo "make tb        - 启动 TensorBoard"
	@echo "make clean     - 清理 results/ 与拓扑缓存"

install:
	pip install -r requirements.txt

test:
	$(PY) -m pytest tests/ -q

smoke:
	$(PY) experiments/smoke_test.py

full:
	$(PY) experiments/run_all.py
	$(PY) experiments/plot_figures.py

figures:
	$(PY) experiments/plot_figures.py

tb:
	tensorboard --logdir results/tensorboard

clean:
	rm -rf results/figures/*.png \
	       results/checkpoints/*.pt \
	       results/tensorboard/* \
	       results/*.pkl results/*.json \
	       data/topo_*.npz
	@echo "✅ 清理完毕"
