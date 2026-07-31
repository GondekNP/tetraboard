.PHONY: serve lint typecheck

serve:
	python scripts/serve.py 8000

lint:
	ruff check web

typecheck:
	mypy web
