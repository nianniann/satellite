PY = PYTHONPATH=. python3
# 指定使用的 GPU 索引（默认 0）。CI/多人共用时可在命令行覆盖：make full GPU=2
GPU ?= 0
ENV = SAT_GPU_INDEX=$(GPU) CUDA_VISIBLE_DEVICES=$(GPU)

.PHONY: help install test full figures tb clean

help:
	@echo "make install   - 安装依赖"
	@echo "make test      - 跑 pytest 单元测试 (~1min)"
	@echo "make full      - 完整 GPU 实验 + 出图 (~10min on L20X)"
	@echo "make figures   - 仅基于已有 pkl 重出图"
	@echo "make tb        - 启动 TensorBoard"
	@echo "make clean     - 清理 results/ 与拓扑缓存"
	@echo ""
	@echo "可选: make full GPU=2  # 指定 GPU 索引"

install:
	pip install -r requirements.txt

test:
	$(ENV) $(PY) -m pytest tests/ -q

full:
	$(ENV) $(PY) experiments/run_all.py
	$(ENV) $(PY) experiments/plot_figures.py

figures:
	$(PY) experiments/plot_figures.py

tb:
	tensorboard --logdir results/tensorboard

clean:
	rm -rf results/figures/*.png \
	       results/checkpoints/*.pt \
	       results/tensorboard/* \
	       results/*.pkl results/*.json results/*.md \
	       data/topo_*.npz
	@echo "✅ 清理完毕"
