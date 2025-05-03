import typer
from pathlib import Path
import logging
from .analyzer import RaceConditionAnalyzer
from .batch_analyzer import BatchAnalyzer
from .visualizer import Visualizer

app = typer.Typer(help="Analyze Arduino code for interrupt-related race conditions.")


def setup_logging(verbose: int = 0):
    """Set up logging based on verbosity level."""
    # Remove all existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    if verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose >= 2:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)


def ensure_dir_exists(path: Path) -> Path:
    """Ensure the directory exists, creating it if necessary."""
    path = Path(path)
    if path.suffix:  # If it's a file path
        path.parent.mkdir(parents=True, exist_ok=True)
    else:  # If it's a directory path
        path.mkdir(parents=True, exist_ok=True)
    return path


@app.command()
def analyze(
    file: Path = typer.Argument(..., help="Input .ino file to analyze"),
    verbose: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity level (-v for INFO, -vv for DEBUG)",
    ),
):
    """
    Analyze a single Arduino .ino file for race conditions.
    """
    setup_logging(verbose)
    analyzer = RaceConditionAnalyzer(str(file))
    analyzer.run_analysis()


@app.command()
def batch_analyze(
    directory: Path = typer.Argument(..., help="Directory containing .ino files"),
    output: Path = typer.Option(
        "results/result.json", "-o", "--output", help="Output JSON file for analysis results"
    ),
    verbose: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity level (-v for INFO, -vv for DEBUG)",
    ),
):
    """
    Analyze multiple Arduino .ino files in a directory for race conditions.
    """
    setup_logging(verbose)
    output = ensure_dir_exists(output)
    batch_analyzer = BatchAnalyzer(str(directory), str(output))
    batch_analyzer.run_analysis()


@app.command()
def visualize(
    json_file: Path = typer.Option(
        "results/result.json", "-i", "--input", help="JSON file containing analysis results"
    ),
    output_dir: Path = typer.Option(
        "results/visualizations", help="Directory to save visualization plots"
    ),
    report: Path = typer.Option(
        "results/race_conditions_report.md", help="Output report file (optional)"
    ),
    dark_mode: bool = typer.Option(False, "--dark-mode", help="Use dark mode styling for plots"),
    verbose: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity level (-v for INFO, -vv for DEBUG)",
    ),
):
    """
    Generate visualizations and reports from analysis results.
    """
    setup_logging(verbose)

    # Ensure all output directories exist
    output_dir = ensure_dir_exists(output_dir)
    report = ensure_dir_exists(report)

    visualizer = Visualizer(str(json_file), dark_mode=dark_mode)
    visualizer.plot_race_condition_summary(str(output_dir))
    visualizer.generate_report(str(report))


def main():  # noqa: D103
    app()


if __name__ == "__main__":
    main()
