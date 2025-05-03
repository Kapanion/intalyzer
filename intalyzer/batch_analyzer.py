import json
from pathlib import Path
from typing import List, Dict, Any
from intalyzer.analyzer import RaceConditionAnalyzer
from intalyzer.models import AccessType


class BatchAnalyzer:
    """Analyzes multiple Arduino files and outputs results to JSON."""

    def __init__(self, input_dir: str, output_file: str):
        """
        Initialize the batch analyzer.

        Args:
        ----
            input_dir: Directory containing .ino files to analyze
            output_file: Path to output JSON file

        """
        self.input_dir = Path(input_dir)
        self.output_file = Path(output_file)
        self.results: List[Dict[str, Any]] = []

    def find_ino_files(self) -> List[Path]:
        """Find all .ino files in the input directory."""
        return list(self.input_dir.glob("**/*.ino"))

    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file and return its results."""
        analyzer = RaceConditionAnalyzer(str(file_path))
        analyzer.run_analysis()

        # Convert results to JSON-serializable format
        file_results = {
            "file": str(file_path),
            "global_vars": list(analyzer.global_vars),
            "interrupts": {
                name: {
                    "reads": [
                        {"line": r.line_number, "var": r.var_name, "statement": r.statement}
                        for r in isr.reads
                    ],
                    "writes": [
                        {"line": w.line_number, "var": w.var_name, "statement": w.statement}
                        for w in isr.writes
                    ],
                }
                for name, isr in analyzer.interrupts.items()
            },
            "race_conditions": [
                {
                    "variable": rc.var_name,
                    "interrupt": rc.interrupt_name,
                    "main_program_accesses": [
                        {
                            "line": a.line_number,
                            "type": "WRITE" if a.access_type == AccessType.WRITE else "READ",
                            "var": a.var_name,
                            "statement": a.statement,
                        }
                        for a in rc.main_program_accesses
                    ],
                    "interrupt_accesses": [
                        {
                            "line": a.line_number,
                            "type": "WRITE" if a.access_type == AccessType.WRITE else "READ",
                            "var": a.var_name,
                            "statement": a.statement,
                        }
                        for a in rc.interrupt_accesses
                    ],
                }
                for rc in analyzer.race_conditions
            ],
        }
        return file_results

    def run_analysis(self):
        """Run analysis on all .ino files and save results to JSON."""
        ino_files = self.find_ino_files()
        logging.info(f"Found {len(ino_files)} .ino files to analyze")

        for i, file_path in enumerate(ino_files, 1):
            logging.info(f"Analyzing file {i}/{len(ino_files)}: {file_path}")
            try:
                file_results = self.analyze_file(file_path)
                self.results.append(file_results)
            except Exception as e:
                logging.error(f"Error analyzing {file_path}: {str(e)}")
                self.results.append({"file": str(file_path), "error": str(e)})

        # Save results to JSON
        with open(self.output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        logging.info(f"Analysis complete. Results saved to {self.output_file}")
