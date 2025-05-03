# Intalyzer-clang

This is the clang tokenizer based implementation of Intalyzer.

## Features

- Detects interrupt service routines (ISRs) in Arduino code
- Identifies shared variables accessed by ISRs and the main program
- Infers potential race conditions between interrupts

## Installation

The project is known to work on MacOS.

Make sure to have LLVM and clang installed.

The project uses Poetry for dependency management. To install:

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/Kapanion/intalyzer.git
cd intalyzer/intalyzer-clang

# Install dependencies
poetry install
```

## Usage

### Analyzing a Single Arduino Sketch

```bash
# Basic analysis
poetry run intalyzer analyze path/to/your/sketch.ino

# With verbose output (-v for INFO, -vv for DEBUG)
poetry run intalyzer analyze path/to/your/sketch.ino -v
```

### Analyzing Multiple Sketches

```bash
# Analyze all .ino files in a directory
poetry run intalyzer batch-analyze path/to/sketches/directory

# Specify custom output file name
poetry run intalyzer batch-analyze path/to/sketches/directory --output custom_results.json
```

### Visualizing Results

```bash
# Generate visualization from analysis results
poetry run intalyzer visualize

# Customize visualization
poetry run intalyzer visualize \
    --input results/result.json \
    --output-dir results/visualizations \
    --report analysis_report.md \
    --dark-mode
```

### Getting Help

```bash
# Show general help
poetry run intalyzer --help

# Show help for specific commands
poetry run intalyzer analyze --help
poetry run intalyzer batch-analyze --help
poetry run intalyzer visualize --help
```

## Development

### Code Formatting and Linting

The project uses [Ruff](https://github.com/astral-sh/ruff) for code formatting and linting.

#### Formatting

```bash
# Format all Python files
poetry run ruff format .

# Check linting issues and fix applicable ones automatically
poetry run ruff check --fix .
```