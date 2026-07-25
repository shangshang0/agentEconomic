.PHONY: smoke deploy down data reproduce paper audit test mcp

PYTHON ?= python3

smoke:
	$(PYTHON) scripts/open_source_smoke.py

deploy:
	./scripts/deploy.sh

down:
	cd runtime/authority_world && docker compose --env-file .env.runtime -f docker-compose.v2.fallback.yml down

data:
	$(PYTHON) scripts/fetch_release.py --release public-data-v1 --all

reproduce:
	$(PYTHON) scripts/reproduce.py --catalog data/catalog/worlds.jsonl --output build/reproduction

paper:
	$(PYTHON) scripts/build_paper.py

audit:
	$(PYTHON) scripts/scan_secrets.py .
	$(PYTHON) scripts/audit_catalog.py data/catalog/worlds.jsonl --assets data/catalog/assets.jsonl
	$(PYTHON) scripts/verify_manifest.py data/manifests/repository-manifest.json --root .

test:
	$(PYTHON) -m pytest -q

mcp:
	$(PYTHON) -m agent_economic_mcp.server
