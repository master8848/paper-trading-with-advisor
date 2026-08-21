.PHONY: openapi dev install test lint

# Default port 8000 avoids clash with paraphras on :3000; frontend VITE_API_URL defaults to 8000
PORT ?= 8000

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port $(PORT)

# Export OpenAPI spec to openapi.json (for frontend codegen)
# Usage: make openapi  |  make openapi OUT=../frontend/openapi.json
OUT ?= ./openapi.json
openapi:
	python scripts/export_openapi.py --out $(OUT)
	@echo "OpenAPI exported to $(OUT) — available at runtime as http://localhost:$(PORT)/openapi.json and /docs"

openapi-frontend:
	python scripts/export_openapi.py --frontend
	@echo "Also copied to frontend/openapi.json"

test:
	pytest -q

lint:
	python -m py_compile app/main.py app/models.py app/database.py app/nse.py app/utils/duration.py app/routers/*.py app/quant/*.py
