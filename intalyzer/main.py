import typer
from pathlib import Path
import logging
from .analyzer import RaceConditionAnalyzer
from .batch_analyzer import BatchAnalyzer
from .visualizer import Visualizer

app = typer.Typer(help="Analyze Arduino code for interrupt-related race conditions.")


def setup_logging(verbose: int = 0):
    """Set up logging based on verbosity level."""
    if verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose >= 2:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)


def ensure_results_dir():
    """Ensure the results directory exists."""
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    return results_dir


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
        "result.json", "-o", "--output", help="Output JSON file for analysis results"
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
    results_dir = ensure_results_dir()
    output_path = results_dir / output
    batch_analyzer = BatchAnalyzer(str(directory), str(output_path))
    batch_analyzer.run_analysis()


@app.command()
def visualize(
    json_file: Path = typer.Option(
        "results/result.json", "-i", "--input", help="JSON file containing analysis results"
    ),
    output_image: Path = typer.Option(
        "race_conditions_summary.png", help="Output image file for visualization"
    ),
    report: Path = typer.Option(None, help="Output report file (optional)"),
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
    results_dir = ensure_results_dir()
    output_image_path = results_dir / output_image
    report_path = results_dir / (report if report else "race_conditions_report.md")

    visualizer = Visualizer(str(json_file), dark_mode=dark_mode)
    visualizer.plot_race_condition_summary(str(output_image_path))
    visualizer.generate_report(str(report_path))


def main():  # noqa: D103
    app()


if __name__ == "__main__":
    main()
