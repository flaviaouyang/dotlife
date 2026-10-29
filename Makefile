.DEFAULT_GOAL := help
MD_PATHS := -r --respect-gitignore -e ./.venv .

.PHONY: help install format test

help: ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install dependencies, including dev tools
	uv sync

format: ## Lint and format Python and Markdown
	uv run ruff format .
	uv run ruff check --fix .
	uv run pymarkdown fix $(MD_PATHS) || true
	uv run pymarkdown scan $(MD_PATHS)

test: ## Run the tests
	uv run python -m unittest discover -s tests
