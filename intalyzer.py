import sys
import argparse
import os
import logging
from typing import Dict, Set, List, Tuple
import clang.cindex
from clang.cindex import CursorKind


class InterruptInfo:
    """Information about an interrupt."""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        self.reads: Set[str] = set()
        self.writes: Set[str] = set()

    def __str__(self) -> str:
        return f"Interrupt {self.name} (priority {self.priority}): Reads {self.reads}, Writes {self.writes}"


class MainProgramInfo:
    """Information about the main program (setup/loop)."""

    def __init__(self):
        self.reads: Set[str] = set()
        self.writes: Set[str] = set()
        self.functions_analyzed: Set[str] = set()  # Track which functions we've analyzed

    def __str__(self) -> str:
        return f"Main Program: Reads {self.reads}, Writes {self.writes}"


class RaceConditionAnalyzer:
    """Analyzes Arduino code for interrupt-related race conditions."""

    def __init__(self, file_path: str, verbose: bool = False):
        self.file_path = file_path
        self.verbose = verbose
        self.interrupts: Dict[str, InterruptInfo] = {}
        self.global_vars: Set[str] = set()
        self.volatile_vars: Set[str] = set()
        self.race_conditions: List[Tuple[str, str, str, str]] = []
        self.main_program = MainProgramInfo()  # Add main program tracking
        self.setup_clang()

    def setup_clang(self):
        """Set up the Clang index and parse the input file."""
        # Initialize clang
        index = clang.cindex.Index.create()

        # For Arduino .ino files, we need to preprocess them to make them valid C++
        # Create a temporary file with Arduino-specific includes
        temp_file = self._preprocess_ino_file()

        try:
            # Parse the file
            self.translation_unit = index.parse(
                temp_file,
                args=[
                    "-x",
                    "c++",
                    "-std=c++11",
                    "-D__ARDUINO_INTERRUPTS_ANALYSIS__",
                    "-I/usr/local/arduino/hardware/arduino/avr/cores/arduino",
                ],
            )
            if self.verbose:
                logging.info(f"Successfully parsed {self.file_path}")
        except Exception as e:
            logging.error(f"Error parsing file: {e}")
            sys.exit(1)

    def _preprocess_ino_file(self) -> str:
        """Preprocess .ino file to make it valid C++ for Clang."""
        # Read the original file
        with open(self.file_path, "r") as f:
            content = f.read()

        # Create Arduino wrapper with common includes
        arduino_wrapper = """
#define ISR(vector) void vector(void)
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// Arduino core function prototypes
void setup();
void loop();

"""
        # Create temporary file
        temp_file = f"{self.file_path}.cpp"
        with open(temp_file, "w") as f:
            f.write(arduino_wrapper + content)

        return temp_file

    def find_interrupts(self):
        """Find all interrupt service routines and analyze main program."""
        self._find_globals(self.translation_unit.cursor)
        self._find_interrupt_handlers(self.translation_unit.cursor)
        self._analyze_main_program(self.translation_unit.cursor)

        if self.verbose:
            logging.info(f"Found {len(self.interrupts)} interrupt handlers")
            for isr in self.interrupts.values():
                logging.info(str(isr))
            logging.info(str(self.main_program))

    def _find_globals(self, cursor):
        """Find all global variables in the code."""
        for node in cursor.get_children():
            if (
                node.kind == CursorKind.VAR_DECL
                and node.semantic_parent.kind == CursorKind.TRANSLATION_UNIT
            ):
                # This is a global variable
                self.global_vars.add(node.spelling)
                # Check if it's volatile
                if node.type.is_volatile_qualified():
                    self.volatile_vars.add(node.spelling)
                    if self.verbose:
                        logging.info(f"Found volatile global variable: {node.spelling}")

            # Recursively process child nodes
            self._find_globals(node)

    def _find_interrupt_handlers(self, cursor):
        """Find all ISRs in the code."""
        for node in cursor.get_children():
            # Look for function definitions
            if node.kind == CursorKind.FUNCTION_DECL:
                # Check if this is an ISR (common patterns in Arduino)
                is_isr = False
                priority = 0

                # Check for ISR vector names
                func_name = node.spelling
                if self.verbose:
                    logging.info(f"Checking function: {func_name}")

                if "_vect" in func_name or func_name in [
                    "ADC_vect",
                    "TIMER1_COMPA_vect",
                    "TIMER2_COMPA_vect",
                ]:
                    is_isr = True
                    # Set priority based on vector name
                    if "TIMER1" in func_name:
                        priority = 1  # Higher priority
                    elif "TIMER2" in func_name or "ADC" in func_name:
                        priority = 2  # Lower priority

                if is_isr:
                    if self.verbose:
                        logging.info(f"Found ISR: {func_name} with priority {priority}")
                    isr_info = InterruptInfo(func_name, priority)
                    self._analyze_isr_body(node, isr_info)
                    self.interrupts[func_name] = isr_info

            # Recursively process child nodes
            self._find_interrupt_handlers(node)

    def _analyze_isr_body(self, node, isr_info):
        """Analyze an ISR body to find variable reads and writes."""
        for child in node.get_children():
            if child.kind == CursorKind.COMPOUND_STMT:
                # This is the function body
                self._process_statements(child, isr_info)

    def _process_statements(self, node, isr_info):
        """Process statements to find variable reads and writes."""
        for child in node.get_children():
            if self.verbose:
                logging.info(f"Processing node: {child.kind} {child.spelling}")

            # Check for variable references
            if child.kind == CursorKind.DECL_REF_EXPR:
                var_name = child.spelling

                # Only care about global variables
                if var_name in self.global_vars:
                    if self.verbose:
                        logging.info(f"Found reference to global variable: {var_name}")

                    # Determine if this is a read or write
                    # Check parent nodes to see if this is part of an assignment
                    parent = child.semantic_parent
                    is_write = False

                    while parent and parent != node:
                        if self.verbose:
                            logging.info(f"Checking parent node: {parent.kind} {parent.spelling}")

                        if parent.kind == CursorKind.BINARY_OPERATOR:
                            # Check if this is an assignment
                            for token in parent.get_tokens():
                                if token.spelling in [
                                    "=",
                                    "+=",
                                    "-=",
                                    "*=",
                                    "/=",
                                    "&=",
                                    "|=",
                                    "^=",
                                    ">>=",
                                    "<<=",
                                ]:
                                    # Check if our variable is on the left side
                                    lhs = list(parent.get_children())[0]
                                    if var_name in [c.spelling for c in lhs.walk_preorder()]:
                                        is_write = True
                                        if self.verbose:
                                            logging.info(
                                                f"Found write operation: {var_name} {token.spelling}"
                                            )
                                        break
                        elif parent.kind == CursorKind.UNARY_OPERATOR:
                            # Check for increment/decrement operators
                            for token in parent.get_tokens():
                                if token.spelling in ["++", "--"]:
                                    # Check if our variable is the operand
                                    if var_name in [c.spelling for c in parent.get_children()]:
                                        is_write = True
                                        if self.verbose:
                                            logging.info(
                                                f"Found increment/decrement: {var_name}{token.spelling}"
                                            )
                                        break
                        elif parent.kind == CursorKind.CALL_EXPR:
                            # Check if this is a function call that might modify the variable
                            if parent.spelling == "millis":
                                # If this variable is being assigned to millis(), it's a write
                                grandparent = parent.semantic_parent
                                if grandparent and grandparent.kind == CursorKind.BINARY_OPERATOR:
                                    for token in grandparent.get_tokens():
                                        if token.spelling == "=":
                                            lhs = list(grandparent.get_children())[0]
                                            if var_name in [
                                                c.spelling for c in lhs.walk_preorder()
                                            ]:
                                                is_write = True
                                                if self.verbose:
                                                    logging.info(
                                                        f"Found millis() assignment: {var_name} = millis()"
                                                    )
                                                break
                            elif parent.spelling == "analogRead":
                                # If this variable is being assigned to analogRead(), it's a write
                                grandparent = parent.semantic_parent
                                if grandparent and grandparent.kind == CursorKind.BINARY_OPERATOR:
                                    for token in grandparent.get_tokens():
                                        if token.spelling == "=":
                                            lhs = list(grandparent.get_children())[0]
                                            if var_name in [
                                                c.spelling for c in lhs.walk_preorder()
                                            ]:
                                                is_write = True
                                                if self.verbose:
                                                    logging.info(
                                                        f"Found analogRead() assignment: {var_name} = analogRead()"
                                                    )
                                                break
                        elif parent.kind == CursorKind.COMPOUND_STMT:
                            # Check if this is a direct assignment in the compound statement
                            for sibling in parent.get_children():
                                if sibling.kind == CursorKind.BINARY_OPERATOR:
                                    for token in sibling.get_tokens():
                                        if token.spelling == "=":
                                            lhs = list(sibling.get_children())[0]
                                            if var_name in [
                                                c.spelling for c in lhs.walk_preorder()
                                            ]:
                                                is_write = True
                                                if self.verbose:
                                                    logging.info(
                                                        f"Found direct assignment: {var_name} = ..."
                                                    )
                                                break
                        elif parent.kind == CursorKind.UNEXPOSED_EXPR:
                            # Handle unexposed expressions that might contain assignments
                            # First check if this is part of a binary operator
                            grandparent = parent.semantic_parent
                            if grandparent and grandparent.kind == CursorKind.BINARY_OPERATOR:
                                for token in grandparent.get_tokens():
                                    if token.spelling in [
                                        "=",
                                        "+=",
                                        "-=",
                                        "*=",
                                        "/=",
                                        "&=",
                                        "|=",
                                        "^=",
                                        ">>=",
                                        "<<=",
                                    ]:
                                        # Check if our variable is on the left side
                                        lhs = list(grandparent.get_children())[0]
                                        if var_name in [c.spelling for c in lhs.walk_preorder()]:
                                            is_write = True
                                            if self.verbose:
                                                logging.info(
                                                    f"Found write in unexposed expr with binary op: {var_name} {token.spelling}"
                                                )
                                            break
                            # Then check for unary operators
                            elif grandparent and grandparent.kind == CursorKind.UNARY_OPERATOR:
                                for token in grandparent.get_tokens():
                                    if token.spelling in ["++", "--"]:
                                        # Check if our variable is the operand
                                        if var_name in [
                                            c.spelling for c in grandparent.get_children()
                                        ]:
                                            is_write = True
                                            if self.verbose:
                                                logging.info(
                                                    f"Found write in unexposed expr with unary op: {var_name}{token.spelling}"
                                                )
                                            break
                            # Finally check for direct assignments
                            for token in parent.get_tokens():
                                if token.spelling in [
                                    "=",
                                    "+=",
                                    "-=",
                                    "*=",
                                    "/=",
                                    "&=",
                                    "|=",
                                    "^=",
                                    ">>=",
                                    "<<=",
                                    "++",
                                    "--",
                                ]:
                                    # Check if our variable is on the left side
                                    if var_name in [c.spelling for c in parent.get_children()]:
                                        is_write = True
                                        if self.verbose:
                                            logging.info(
                                                f"Found write in unexposed expr: {var_name} {token.spelling}"
                                            )
                                        break
                        parent = parent.semantic_parent

                    if is_write:
                        isr_info.writes.add(var_name)
                        if self.verbose:
                            logging.info(f"ISR {isr_info.name} writes to {var_name}")
                    else:
                        isr_info.reads.add(var_name)
                        if self.verbose:
                            logging.info(f"ISR {isr_info.name} reads from {var_name}")

            # Recursively process child statements
            self._process_statements(child, isr_info)

    def _analyze_main_program(self, cursor):
        """Find and analyze setup() and loop() functions."""
        for node in cursor.get_children():
            if node.kind == CursorKind.FUNCTION_DECL:
                func_name = node.spelling
                if (
                    func_name in ["setup", "loop"]
                    and func_name not in self.main_program.functions_analyzed
                ):
                    if self.verbose:
                        logging.info(f"Analyzing main program function: {func_name}")
                    self.main_program.functions_analyzed.add(func_name)
                    self._process_statements(node, self.main_program)

            # Recursively process child nodes
            self._analyze_main_program(node)

    def analyze_race_conditions(self):
        """Analyze potential race conditions between interrupts and main program."""
        # First analyze interrupt-to-interrupt race conditions
        interrupt_list = list(self.interrupts.values())
        for i in range(len(interrupt_list)):
            for j in range(i + 1, len(interrupt_list)):
                isr1 = interrupt_list[i]
                isr2 = interrupt_list[j]

                # Determine which interrupt can preempt the other
                if isr1.priority < isr2.priority:
                    higher_priority, lower_priority = isr2, isr1
                else:
                    higher_priority, lower_priority = isr1, isr2

                # Check for race conditions between interrupts
                for var in higher_priority.writes:
                    if var in lower_priority.reads:
                        self.race_conditions.append(
                            (var, higher_priority.name, lower_priority.name, "read")
                        )
                    if var in lower_priority.writes:
                        self.race_conditions.append(
                            (var, higher_priority.name, lower_priority.name, "write")
                        )

                for var in lower_priority.writes:
                    if var in higher_priority.reads:
                        self.race_conditions.append(
                            (var, lower_priority.name, higher_priority.name, "read")
                        )

        # Then analyze main program vs interrupt race conditions
        for isr in self.interrupts.values():
            # Check for race conditions where interrupt writes variables that main program reads/writes
            for var in isr.writes:
                if var in self.main_program.reads:
                    self.race_conditions.append((var, isr.name, "main program", "read"))
                if var in self.main_program.writes:
                    self.race_conditions.append((var, isr.name, "main program", "write"))

            # Check for race conditions where main program writes variables that interrupt reads
            for var in self.main_program.writes:
                if var in isr.reads:
                    self.race_conditions.append((var, "main program", isr.name, "read"))

    def report_results(self):
        """Report the analysis results."""
        if not self.race_conditions:
            print("No potential race conditions detected.")
            return

        print(f"Found {len(self.race_conditions)} potential race conditions:")
        for var, writer, reader, access_type in self.race_conditions:
            print(f"  • Race condition on variable '{var}':")
            print(f"    - '{writer}' writes to '{var}'")
            if access_type == "read":
                print(f"    - '{reader}' reads '{var}'")
            else:
                print(f"    - '{reader}' also writes to '{var}'")
            if var not in self.volatile_vars:
                print(f"    Note: '{var}' is not declared as volatile")


def main():
    """Main entry point for the program."""
    parser = argparse.ArgumentParser(
        description="Analyze Arduino code for interrupt-related race conditions"
    )
    parser.add_argument("input_file", help="Input .ino file to analyze")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--output-file", "-o", help="Output file for results")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Check if the input file exists
    if not os.path.isfile(args.input_file):
        logging.error(f"Input file {args.input_file} does not exist")
        sys.exit(1)

    # Redirect output if needed
    if args.output_file:
        sys.stdout = open(args.output_file, "w")

    # Perform the analysis
    analyzer = RaceConditionAnalyzer(args.input_file, args.verbose)
    analyzer.find_interrupts()
    analyzer.analyze_race_conditions()
    analyzer.report_results()

    return 0  # Return success code


if __name__ == "__main__":
    sys.exit(main())
