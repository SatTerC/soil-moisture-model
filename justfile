# Default recipe to display available commands.
_:
  @just --list

# Format and lint the package using ruff.
lint:
  ruff format
  ruff check --fix

# Variant of `lint` that doesn't cause any changes to files.
lint-check:
  ruff format --check
  ruff check

# Run the test suite.
test:
  pytest --log-cli-level=INFO

# Run tests with coverage report.
test-cov:
  pytest --cov=soil_moisture_model --cov-report=term-missing --cov-fail-under=90

# Run static type checker.
typecheck:
  pyright src/soil_moisture_model

# Build the documentation using Zensical.
docs: 
  zensical build --clean --strict
