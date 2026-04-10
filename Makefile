.PHONY: test test-unit test-integration test-e2e coverage coverage-html clean

test:
	python3 -m pytest

test-unit:
	python3 -m pytest tests/unit

test-integration:
	python3 -m pytest tests/integration

test-e2e:
	python3 -m pytest tests/e2e

# Run the full suite with in-process and subprocess coverage. pytest-cov
# combines the parallel datafiles automatically. Requires pytest-cov.
coverage:
	rm -f .coverage .coverage.*
	python3 -m pytest --cov=scripts --cov-report=term-missing

coverage-html:
	rm -f .coverage .coverage.*
	python3 -m pytest --cov=scripts --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

coverage-xml:
	rm -f .coverage .coverage.*
	python3 -m pytest --cov=scripts --cov-report=term-missing --cov-report=xml
	@echo "XML report: coverage.xml"

clean:
	rm -rf .pytest_cache htmlcov .coverage .coverage.*
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
