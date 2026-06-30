.PHONY: setup init-db test lint eval ablation notebook validate-data full-check

PYTHON ?= python

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

init-db:
	$(PYTHON) -m app.db.init_db

test:
	pytest

lint:
	ruff check app evals tests

eval:
	$(PYTHON) -m evals.run_eval --all-modes --fail-under 0.70

ablation:
	$(PYTHON) -m evals.run_ablation

notebook:
	$(PYTHON) scripts/execute_notebook.py

validate-data:
	$(PYTHON) scripts/validate_demo_data.py

full-check: init-db validate-data test lint eval ablation notebook
