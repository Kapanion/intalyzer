import json
from pathlib import Path
from typing import Dict, Any
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

    def plot_race_condition_summary(self, output_file: str):
        """Create a summary plot showing race condition statistics."""
        stats = self._get_race_condition_stats()

        # Create figure with subplots
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle("Race Condition Analysis Distributions", fontsize=16, color=self.text_color)

        # Plot 1: Distribution of race conditions per file
        race_conditions_per_file = []
        for result in self.results:
            if "error" not in result:
                race_conditions_per_file.append(len(result["race_conditions"]))

        if race_conditions_per_file:
            sns.histplot(race_conditions_per_file, ax=axes[0], discrete=True)
            axes[0].set_title("Race Conditions per File", color=self.text_color)
            axes[0].set_xlabel("Number of Race Conditions", color=self.text_color)
            axes[0].set_ylabel("Number of Files", color=self.text_color)
            axes[0].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[0].yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[0].tick_params(colors=self.text_color)

        # Plot 2: Distribution of race conditions per interrupt
        race_conditions_per_interrupt = list(stats["race_conditions_by_interrupt"].values())
        if race_conditions_per_interrupt:
            sns.histplot(race_conditions_per_interrupt, ax=axes[1], discrete=True)
            axes[1].set_title("Race Conditions per Interrupt", color=self.text_color)
            axes[1].set_xlabel("Number of Race Conditions", color=self.text_color)
            axes[1].set_ylabel("Number of Interrupts", color=self.text_color)
            axes[1].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[1].yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[1].tick_params(colors=self.text_color)

        # Plot 3: Distribution of race conditions per variable
        race_conditions_per_variable = list(stats["race_conditions_by_variable"].values())
        if race_conditions_per_variable:
            sns.histplot(race_conditions_per_variable, ax=axes[2], discrete=True)
            axes[2].set_title("Race Conditions per Variable", color=self.text_color)
            axes[2].set_xlabel("Number of Race Conditions", color=self.text_color)
            axes[2].set_ylabel("Number of Variables", color=self.text_color)
            axes[2].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[2].yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            axes[2].tick_params(colors=self.text_color)

        plt.tight_layout()
        plt.savefig(output_file, facecolor="black" if self.dark_mode else "white")
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
