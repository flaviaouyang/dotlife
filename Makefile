.DEFAULT_GOAL := help
MD_PATHS := -r --respect-gitignore -e ./.venv .

.PHONY: help install setup fresh format check test validate dashboard docs release

help: ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install dependencies and link the Streamlit agent skill
	uv sync
	@skill=$$(uv run python -c "import pathlib, streamlit; print(pathlib.Path(streamlit.__file__).parent / '.agents/skills/developing-with-streamlit')") && \
	mkdir -p .agents/skills && ln -sfn "$$skill" .agents/skills/developing-with-streamlit

format: ## Lint and format Python and Markdown
	uv run ruff format .
	uv run ruff check --fix .
	uv run pymarkdown fix $(MD_PATHS) || true
	uv run pymarkdown scan $(MD_PATHS)

check: ## Lint and check formatting and types without changing files (what CI runs)
	uv run ruff check .
	uv run ruff format --check .
	uv run pymarkdown scan $(MD_PATHS)
	uvx pyright@1.1.414 --pythonpath .venv/bin/python dotlife tests

test: ## Run the tests
	uv run python -m unittest discover -s tests

setup: ## Answer a few questions about what you track and where it comes from
	uv run dotlife setup

fresh: ## Fetch new data with your source scripts, then validate
	uv run dotlife fresh

validate: ## Check the data files (data_dir in config.toml, else sample/)
	uv run dotlife validate

dashboard: ## Open the dashboard (data_dir in config.toml, else sample/)
	uv run dotlife dashboard

docs: ## Regenerate the category tables in FORMAT.md
	uv run python -m dotlife.format_doc

release: ## Bump the version and update CHANGELOG.md (override: BUMP=major|minor|patch or VERSION=vX.Y.Z[-beta.N])
	@version=$(or $(VERSION),$$(uv run git-cliff --bumped-version $(if $(BUMP),--bump $(BUMP)))) && \
	uv version --no-sync "$${version#v}" && \
	uv run git-cliff --tag "$$version" --output CHANGELOG.md && \
	echo "Review the changes, then commit and push. Once CI passes, GitHub Actions tags $$version and publishes the release:" && \
	echo "  git add CHANGELOG.md pyproject.toml uv.lock && git commit -m 'chore(release): $$version' && git push"
