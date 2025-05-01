# Intalyzer

A tool for analyzing Arduino code for interrupt-related race conditions.

## Features

- Detects interrupt service routines (ISRs) in Arduino code
- Identifies shared variables accessed by multiple ISRs
- Analyzes potential race conditions between interrupts
- Supports verbose output for detailed analysis

## Installation

The project uses Poetry for dependency management. To install:

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/yourusername/intalyzer.git
cd intalyzer

# Install dependencies
poetry install
```

## Usage

```bash
# Run the analyzer on an Arduino sketch
poetry run intalyzer path/to/your/sketch.ino

# Run with verbose output
poetry run intalyzer path/to/your/sketch.ino --verbose

# Save output to a file
poetry run intalyzer path/to/your/sketch.ino --output-file results.txt
```

## Development

### Code Formatting and Linting

The project uses [Ruff](https://github.com/astral-sh/ruff) for code formatting and linting.

#### Formatting

```bash
# Format all Python files
poetry run ruff format .

# Check formatting without making changes
poetry run ruff format --check .
```

#### Linting

```bash
# Check for linting issues
poetry run ruff check .

# Fix automatically fixable linting issues
poetry run ruff check --fix .

# Check for specific rule violations
poetry run ruff check --select E,F,W .
```

Common Ruff commands:
- `ruff format .`: Format all Python files
- `ruff check .`: Check for linting issues
- `ruff check --fix .`: Fix automatically fixable issues
- `ruff check --select E,F,W .`: Check for errors (E), fatal errors (F), and warnings (W)

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=intalyzer
```

## License

MIT License 