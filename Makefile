.PHONY: test test-unit test-integration test-e2e clean

test:
	python3 -m pytest

test-unit:
	python3 -m pytest tests/unit

test-integration:
	python3 -m pytest tests/integration

test-e2e:
	python3 -m pytest tests/e2e

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
