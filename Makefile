.PHONY: install
install: ## Install the virtual environment and install the pre-commit hooks
	@if [ ! -d .git ]; then \
		echo "❌ Error: Not a git repository. Run 'git init -b main' first (see README step 1)."; \
		exit 1; \
	fi
	@echo "🚀 Creating virtual environment using uv"
	@uv sync
	@uv run pre-commit install

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo "🚀 Linting code: Running pre-commit"
	@uv run pre-commit run -a

.PHONY: docs-test
docs-test: ## Test if documentation can be built without errors
	@uv run zensical build

.PHONY: dev
dev: ## Hot-reload dev server for a single version (usage: make dev [VERSION=v25.2.0])
	@if [ -z "$(VERSION)" ]; then \
		SHORT=$$(ls -d build/v*/ 2>/dev/null | head -1 | xargs basename); \
		if [ -z "$$SHORT" ]; then echo "No built versions found. Run 'make convert VERSION=v25.2.0' first."; exit 1; fi; \
		echo "Serving build/$$SHORT ..."; \
		cd build/$$SHORT && uv run zensical serve; \
	else \
		SHORT=$$(uv run python -c "from scripts.config import version_to_short; print(version_to_short('$(VERSION)'))"); \
		if [ ! -d "build/$$SHORT" ]; then echo "Version $(VERSION) not built. Run 'make convert VERSION=$(VERSION)' first."; exit 1; fi; \
		echo "Serving build/$$SHORT ..."; \
		cd build/$$SHORT && uv run zensical serve; \
	fi

.PHONY: serve
serve: ## Serve the full multi-version site from dist/
	@if [ ! -d dist ] || [ ! -f dist/index.html ]; then \
		echo "No dist/ found. Run 'make convert VERSION=v25.2.0' first."; exit 1; \
	fi
	@echo "Serving full site from dist/ on http://localhost:8003"
	@uv run python -m http.server 8003 --directory dist

.PHONY: build-editor
build-editor: ## Build the IDF Monaco editor bundle
	@echo "Building IDF editor bundle..."
	@cd idf-editor && npm ci --silent && npm run build
	@cp idf-editor/dist/idf-editor.js idf-editor/dist/idf-editor.css scripts/assets/
	@echo "IDF editor bundle built and copied to scripts/assets/"

.PHONY: convert
convert: build-editor ## Convert a single EnergyPlus version (usage: make convert VERSION=v25.2.0)
	@if [ -z "$(VERSION)" ]; then echo "Usage: make convert VERSION=v25.2.0"; exit 1; fi
	@echo "Converting EnergyPlus $(VERSION)..."
	@mkdir -p build/sources
	@if [ ! -d "build/sources/$(VERSION)/doc" ]; then \
		rm -rf "build/sources/$(VERSION)"; \
		git clone --filter=blob:none --no-checkout --depth=1 \
			--branch $(VERSION) --single-branch \
			https://github.com/NatLabRockies/EnergyPlus.git build/sources/$(VERSION) && \
		git -C build/sources/$(VERSION) sparse-checkout set doc && \
		git -C build/sources/$(VERSION) checkout; \
	fi
	@uv run python -m scripts.convert \
		--source build/sources/$(VERSION) \
		--output build/$$(uv run python -c "from scripts.config import version_to_short; print(version_to_short('$(VERSION)'))") \
		--version $(VERSION) --verbose \
		$(if $(MAX_WORKERS),--max-workers $(MAX_WORKERS),)
	@$(MAKE) deploy VERSION=$(VERSION)

.PHONY: deploy
deploy: ## Deploy a built version to dist/ (usage: make deploy VERSION=v25.2.0)
	@if [ -z "$(VERSION)" ]; then echo "Usage: make deploy VERSION=v25.2.0"; exit 1; fi
	@SHORT=$$(uv run python -c "from scripts.config import version_to_short; print(version_to_short('$(VERSION)'))"); \
	if [ ! -d "build/$$SHORT" ]; then echo "Version $(VERSION) not built. Run 'make convert VERSION=$(VERSION)' first."; exit 1; fi; \
	echo "Deploying $$SHORT to dist/..."; \
	uv run python -c "from pathlib import Path; from scripts.version_manager import deploy_single_version; deploy_single_version('$(VERSION)', Path('build/$$SHORT'), Path('dist'))"
	@echo "✅ Deployed to dist/. Run 'make serve' to view."

.PHONY: convert-all
convert-all: ## Convert all target EnergyPlus versions in parallel
	@echo "Converting all EnergyPlus versions..."
	@uv run python -m scripts.convert_all --verbose --force-rebuild

.PHONY: build-version
build-version: ## Convert and build a single version (usage: make build-version VERSION=v25.2.0)
	@if [ -z "$(VERSION)" ]; then echo "Usage: make build-version VERSION=v25.2.0"; exit 1; fi
	@$(MAKE) convert VERSION=$(VERSION)

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
