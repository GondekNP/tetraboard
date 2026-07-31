.PHONY: serve lint

serve:
	python scripts/serve.py 8000

lint:
	ruff check web
