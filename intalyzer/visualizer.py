import json
from pathlib import Path
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict


class Visualizer:
    """Generates visualizations from race condition analysis results."""

    def __init__(self, json_file: str, dark_mode: bool = False):
        """
        Initialize the visualizer.

        Args:
        ----
            json_file: Path to JSON file containing analysis results
            dark_mode: Whether to use dark mode styling for plots (default: False)

        """
        self.json_file = Path(json_file)
        self.dark_mode = dark_mode
        with open(json_file) as f:
            self.results = json.load(f)

        # Set dark mode styling if enabled
        if self.dark_mode:
            plt.style.use("dark_background")
            sns.set_style(
                "darkgrid",
                {
                    "axes.facecolor": "#1a1a1a",
                    "figure.facecolor": "#1a1a1a",
                    "grid.color": "#333333",
                    "axes.grid": True,
                    "axes.edgecolor": "#333333",
                    "axes.labelcolor": "white",
                    "xtick.color": "white",
                    "ytick.color": "white",
                    "text.color": "white",
                },
            )
            self.text_color = "white"
        else:
            self.text_color = "black"

    def _get_race_condition_stats(self) -> Dict[str, Any]:
        """Calculate statistics about race conditions across all files."""
        stats = {
            "total_files": len(self.results),
            "files_with_race_conditions": 0,
            "total_race_conditions": 0,
            "race_conditions_by_variable": defaultdict(int),
            "race_conditions_by_interrupt": defaultdict(int),
            "files_with_errors": 0,
        }

        for result in self.results:
            if "error" in result:
                stats["files_with_errors"] += 1
                continue

            if result["race_conditions"]:
                stats["files_with_race_conditions"] += 1
                stats["total_race_conditions"] += len(result["race_conditions"])

                for rc in result["race_conditions"]:
                    stats["race_conditions_by_variable"][rc["variable"]] += 1
                    stats["race_conditions_by_interrupt"][rc["interrupt"]] += 1

        return stats

    def _plot_histogram(
        self, data: List[int], title: str, xlabel: str, ylabel: str, output_path: Path
    ):
        """
        Helper function to create and save a histogram plot.

        Args:
        ----
            data: List of values to plot
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            output_path: Path to save the plot

        """
        if not data:
            return

        plt.figure(figsize=(8, 6))
        sns.histplot(data, discrete=True)
        plt.title(title, color=self.text_color)
        plt.xlabel(xlabel, color=self.text_color)
        plt.ylabel(ylabel, color=self.text_color)
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        plt.gca().yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        plt.gca().tick_params(colors=self.text_color)
        plt.tight_layout()
        plt.savefig(
            output_path,
            facecolor="black" if self.dark_mode else "white",
            bbox_inches="tight",
        )
        plt.close()

    def plot_race_condition_summary(self, output_file: str):
        """Create a summary plot showing race condition statistics."""
        stats = self._get_race_condition_stats()

        # Create base filename for individual plots
        base_output = Path(output_file)
        base_name = base_output.stem
        output_dir = base_output.parent

        # Calculate pie chart data
        no_race_conditions = (
            stats["total_files"] - stats["files_with_race_conditions"] - stats["files_with_errors"]
        )
        one_race_condition = 0
        two_or_more_race_conditions = 0

        for result in self.results:
            if "error" not in result:
                rc_count = len(result["race_conditions"])
                if rc_count == 1:
                    one_race_condition += 1
                elif rc_count >= 2:
                    two_or_more_race_conditions += 1

        # Plot 1: Distribution of race conditions per file
        race_conditions_per_file = []
        for result in self.results:
            if "error" not in result:
                race_conditions_per_file.append(len(result["race_conditions"]))

        self._plot_histogram(
            race_conditions_per_file,
            "Race Conditions per File",
            "Number of Race Conditions",
            "Number of Files",
            output_dir / f"{base_name}_per_file.png",
        )

        # Plot 2: Distribution of race conditions per interrupt
        race_conditions_per_interrupt = list(stats["race_conditions_by_interrupt"].values())
        self._plot_histogram(
            race_conditions_per_interrupt,
            "Race Conditions per Interrupt",
            "Number of Race Conditions",
            "Number of Interrupts",
            output_dir / f"{base_name}_per_interrupt.png",
        )

        # Plot 3: Distribution of race conditions per variable
        race_conditions_per_variable = list(stats["race_conditions_by_variable"].values())
        self._plot_histogram(
            race_conditions_per_variable,
            "Race Conditions per Variable",
            "Number of Race Conditions",
            "Number of Variables",
            output_dir / f"{base_name}_per_variable.png",
        )

        # Plot 4: Pie chart of files by race condition count
        plt.figure(figsize=(8, 6))
        sizes = [no_race_conditions, one_race_condition, two_or_more_race_conditions]
        labels = ["No Race Conditions", "1 Race Condition", "≥2 Race Conditions"]
        colors = ["#2ecc71", "#f1c40f", "#e74c3c"]

        plt.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color": self.text_color},
        )
        plt.title("Files by Race Condition Count", color=self.text_color)
        plt.axis("equal")
        plt.tight_layout()
        plt.savefig(
            output_dir / f"{base_name}_distribution.png",
            facecolor="black" if self.dark_mode else "white",
            bbox_inches="tight",
        )
        plt.close()

    def generate_report(self, output_file: str):
        """Generate a detailed report of the analysis results."""
        stats = self._get_race_condition_stats()

        with open(output_file, "w") as f:
            f.write("# Race Condition Analysis Report\n\n")

            # Summary statistics
            f.write("## Summary Statistics\n\n")
            f.write(f"- Total files analyzed: {stats['total_files']}\n")
            f.write(f"- Files with race conditions: {stats['files_with_race_conditions']}\n")
            f.write(f"- Total race conditions found: {stats['total_race_conditions']}\n")
            f.write(f"- Files with errors: {stats['files_with_errors']}\n\n")

            # Detailed results
            f.write("## Detailed Results\n\n")
            for result in self.results:
                f.write(f"### File: {result['file']}\n\n")

                if "error" in result:
                    f.write(f"Error during analysis: {result['error']}\n\n")
                    continue

                if result["race_conditions"]:
                    f.write("Race conditions found:\n")
                    for rc in result["race_conditions"]:
                        f.write(f"- Variable: {rc['variable']}\n")
                        f.write(f"  Interrupt: {rc['interrupt']}\n")
                        f.write("  Main program accesses:\n")
                        for access in rc["main_program_accesses"]:
                            f.write(
                                f"    - Line {access['line']}: {access['type']} of {access['var']}\n"
                            )
                        f.write("  Interrupt accesses:\n")
                        for access in rc["interrupt_accesses"]:
                            f.write(
                                f"    - Line {access['line']}: {access['type']} of {access['var']}\n"
                            )
                else:
                    f.write("No race conditions found.\n")

                f.write("\n")
