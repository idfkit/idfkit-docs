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

.PHONY: docs
docs: ## Serve a single version locally (usage: make docs [VERSION=v25.2.0])
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
serve: ## Serve the full multi-version site from dist/ (run convert-all first)
	@if [ ! -d dist ] || [ ! -f dist/index.html ]; then \
		echo "No dist/ found. Run 'make convert-all' first."; exit 1; \
	fi
	@echo "Serving full site from dist/ on http://localhost:8000"
	@python -m http.server 8000 --directory dist

.PHONY: convert
convert: ## Convert a single EnergyPlus version (usage: make convert VERSION=v25.2.0)
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
		--version $(VERSION) --verbose

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
