.PHONY: test lint run stop clean build

# Run full test suite
test:
	python -m pytest tests/ -v --tb=short

# Run tests with coverage (requires pytest-cov)
test-cov:
	python -m pytest tests/ -v --tb=short --cov=bannin --cov-report=term-missing

# Lint with ruff (requires ruff)
lint:
	python -m ruff check bannin/ tests/

# Start the Bannin agent
run:
	python -m bannin.cli start

# Stop the Bannin agent
stop:
	python -m bannin.cli stop

# Agent status
status:
	python -m bannin.cli status

# Build wheel for distribution
build:
	python -m build --wheel

# Install in editable mode (dev)
install:
	pip install --user -e ".[all]"

# Install dev dependencies
install-dev:
	pip install --user pytest pytest-cov ruff

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
