.PHONY: install compile test lint run demo clean

install:
	pip install -e ".[dev]"

compile:
	python -m consentchain.chain.compile

test:
	pytest --cov=consentchain --cov-report=term-missing

lint:
	ruff check consentchain tests

run:
	uvicorn consentchain.main:app --reload --port 8000

demo:
	python -m consentchain.cli demo

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
