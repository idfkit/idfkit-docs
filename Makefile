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
docs: ## Build and serve the documentation
	@uv run zensical serve

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
