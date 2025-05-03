import sys
import logging
from typing import Dict, Set, List
import clang.cindex
from clang.cindex import CursorKind

from intalyzer.models import (
    InterruptInfo,
    MainProgramInfo,
    ReadAccessInfo,
    WriteAccessInfo,
    RaceCondition,
    AccessType,
)
from intalyzer.constants import ARDUINO_WRAPPER


class RaceConditionAnalyzer:
    """Analyzes Arduino code for interrupt-related race conditions."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.interrupts: Dict[str, InterruptInfo] = {}
        self.global_vars: Set[str] = set()
        self.race_conditions: List[RaceCondition] = []
        self.main_program = MainProgramInfo()
        self.setup_clang()

    def setup_clang(self):
        """Set up the Clang index and parse the input file."""
        index = clang.cindex.Index.create()
        temp_file = self._preprocess_ino_file()

        try:
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
            logging.info(f"Successfully parsed {self.file_path}")
        except Exception as e:
            logging.error(f"Error parsing file: {e}")
            sys.exit(1)

    def _preprocess_ino_file(self) -> str:
        """Preprocess .ino file to make it valid C++ for Clang."""
        with open(self.file_path, "r") as f:
            content = f.read()

        arduino_wrapper = ARDUINO_WRAPPER
        temp_file = f"{self.file_path}.cpp"
        with open(temp_file, "w") as f:
            f.write(arduino_wrapper + content)

        return temp_file

    def find_interrupts(self):
        """Find all interrupt service routines and analyze main program."""
        self._find_globals(self.translation_unit.cursor)
        logging.info(f"Found {len(self.global_vars)} global variables: {self.global_vars}")

        self._find_attach_interrupts(self.translation_unit.cursor)
        logging.info(
            f"Found {len(self.interrupts)} interrupt handlers: {list(self.interrupts.keys())}"
        )

        self._analyze_main_program(self.translation_unit.cursor)

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
                self.global_vars.add(node.spelling)
                logging.debug(f"Found global variable: {node.spelling}")

            self._find_globals(node)

    def _find_attach_interrupts(self, cursor):
        """Find all attachInterrupt calls and their associated functions."""
        for node in cursor.get_children():
            if node.kind == CursorKind.COMPOUND_STMT:
                # Get all tokens in this compound statement
                tokens = list(node.get_tokens())
                for i, token in enumerate(tokens):
                    if token.spelling == "attachInterrupt":
                        # Look for the function name in the next few tokens
                        for j in range(i, min(i + 10, len(tokens))):
                            if tokens[j].spelling == "(":
                                # The function name should be the token after the next comma
                                for k in range(j, min(j + 10, len(tokens))):
                                    if tokens[k].spelling == ",":
                                        isr_name = tokens[k + 1].spelling
                                        if isr_name.endswith(")"):
                                            isr_name = isr_name[:-1]  # Remove trailing parenthesis

                                        logging.debug(
                                            f"Found attachInterrupt for function: {isr_name}"
                                        )
                                        self.interrupts[isr_name] = InterruptInfo(name=isr_name)
                                        self._analyze_interrupt_function(isr_name)
                                        break
                                break

            self._find_attach_interrupts(node)

    def _analyze_interrupt_function(self, func_name: str):
        """Analyze an interrupt function to find variable reads and writes."""
        for node in self.translation_unit.cursor.get_children():
            if node.kind == CursorKind.FUNCTION_DECL and node.spelling == func_name:
                logging.debug(f"Analyzing interrupt function: {func_name}")
                # Find the function body (compound statement)
                for child in node.get_children():
                    if child.kind == CursorKind.COMPOUND_STMT:
                        logging.debug("Found function body")
                        self._process_statements(child, self.interrupts[func_name])
                        break

    def _process_statements(self, node, info):
        """Process statements to find variable reads and writes."""
        logging.debug(f"Processing statement node: {node.kind} {node.spelling}")

        # If this is a compound statement, check all tokens for global variable references
        if node.kind == CursorKind.COMPOUND_STMT:
            tokens = list(node.get_tokens())
            logging.debug(f"Statement tokens: {[t.spelling for t in tokens]}")

            # Check all tokens for global variable references
            for token in tokens:
                if token.spelling in self.global_vars:
                    var_name = token.spelling
                    logging.debug(f"Found global variable {var_name} in compound statement")
                    line_number = token.location.line

                    # Find the statement containing this variable
                    statement = ""
                    current = node
                    while current and current.kind != CursorKind.TRANSLATION_UNIT:
                        if (
                            current.kind == CursorKind.BINARY_OPERATOR
                            or current.kind == CursorKind.UNARY_OPERATOR
                            or current.kind == CursorKind.CALL_EXPR
                            or current.kind == CursorKind.MEMBER_REF_EXPR
                        ):
                            statement = "".join(t.spelling for t in current.get_tokens())
                            break
                        current = current.semantic_parent

                    # Always add read access for variable references
                    info.reads.add(
                        ReadAccessInfo(
                            line_number=line_number,
                            statement=statement,
                            var_name=var_name,
                        )
                    )
                    logging.debug(f"Added read of {var_name} in compound statement")

        for child in node.get_children():
            logging.debug(f"Processing node: {child.kind} {child.spelling}")
            logging.debug(f"Node tokens: {[t.spelling for t in child.get_tokens()]}")

            if child.kind == CursorKind.BINARY_OPERATOR:
                logging.debug(f"Binary operator tokens: {[t.spelling for t in child.get_tokens()]}")
                # Check if this is an assignment
                tokens = list(child.get_tokens())
                for i, token in enumerate(tokens):
                    if token.spelling == "=":
                        # Get the left side variable name
                        left_side = tokens[:i]
                        left_var = left_side[0].spelling if left_side else None
                        if left_var in self.global_vars:
                            logging.debug(f"Found write to global variable: {left_var}")
                            info.writes.add(
                                WriteAccessInfo(
                                    line_number=child.location.line,
                                    statement="".join(t.spelling for t in tokens),
                                    var_name=left_var,
                                )
                            )
                            # Also add read access for the variable being written to
                            info.reads.add(
                                ReadAccessInfo(
                                    line_number=child.location.line,
                                    statement="".join(t.spelling for t in tokens),
                                    var_name=left_var,
                                )
                            )
                        break

            elif child.kind == CursorKind.UNARY_OPERATOR:
                # Check if this is an increment/decrement operation
                tokens = list(child.get_tokens())
                logging.debug(f"Unary operator tokens: {[t.spelling for t in tokens]}")

                # Look for ++ or -- operators
                if len(tokens) == 2 and (tokens[1].spelling == "++" or tokens[1].spelling == "--"):
                    var_name = tokens[0].spelling
                    if var_name in self.global_vars:
                        logging.debug(f"Found increment/decrement of global variable: {var_name}")
                        statement = "".join(t.spelling for t in tokens)
                        line_number = child.location.line

                        # Add both read and write accesses
                        info.reads.add(
                            ReadAccessInfo(
                                line_number=line_number,
                                statement=statement,
                                var_name=var_name,
                            )
                        )
                        info.writes.add(
                            WriteAccessInfo(
                                line_number=line_number,
                                statement=statement,
                                var_name=var_name,
                            )
                        )
                        logging.debug(f"Added read and write of {var_name} for increment/decrement")

            elif child.kind == CursorKind.DECL_REF_EXPR:
                var_name = child.spelling
                if var_name in self.global_vars:
                    logging.debug(f"Found reference to global variable: {var_name}")
                    # Get the line number
                    line_number = child.location.line

                    # Get the full statement text
                    statement = ""
                    current = child
                    while current and current.kind != CursorKind.TRANSLATION_UNIT:
                        if (
                            current.kind == CursorKind.BINARY_OPERATOR
                            or current.kind == CursorKind.UNARY_OPERATOR
                            or current.kind == CursorKind.CALL_EXPR
                            or current.kind == CursorKind.MEMBER_REF_EXPR
                        ):
                            statement = "".join(t.spelling for t in current.get_tokens())
                            break
                        current = current.semantic_parent

                    # If we didn't find a statement, look for a parent call expression
                    if not statement:
                        current = child
                        while current and current.kind != CursorKind.TRANSLATION_UNIT:
                            if current.kind == CursorKind.CALL_EXPR:
                                statement = "".join(t.spelling for t in current.get_tokens())
                                break
                            current = current.semantic_parent

                    # Always add read access for variable references
                    info.reads.add(
                        ReadAccessInfo(
                            line_number=line_number,
                            statement=statement,
                            var_name=var_name,
                        )
                    )
                    logging.debug(f"Added read of {var_name}")

            elif child.kind == CursorKind.CALL_EXPR:
                # Process function call arguments and nested expressions
                self._process_function_call(child, info)

            elif child.kind == CursorKind.MEMBER_REF_EXPR:
                # Process member references (e.g., Serial.print)
                tokens = list(child.get_tokens())
                logging.debug(f"Member reference tokens: {[t.spelling for t in tokens]}")

                # Get the parent call expression
                parent = child.semantic_parent
                if parent and parent.kind == CursorKind.CALL_EXPR:
                    statement = "".join(t.spelling for t in parent.get_tokens())
                    logging.debug(f"Parent call expression: {statement}")

                    # Process any global variables in the arguments
                    for arg in parent.get_children():
                        if arg.kind == CursorKind.DECL_REF_EXPR:
                            var_name = arg.spelling
                            if var_name in self.global_vars:
                                logging.debug(
                                    f"Found global variable {var_name} in member reference call"
                                )
                                line_number = arg.location.line
                                # Always add read access for variable references
                                info.reads.add(
                                    ReadAccessInfo(
                                        line_number=line_number,
                                        statement=statement,
                                        var_name=var_name,
                                    )
                                )
                                logging.debug(f"Added read of {var_name} in member reference call")

            elif child.kind == CursorKind.UNEXPOSED_EXPR:
                # Process unexposed expressions at the top level
                tokens = list(child.get_tokens())
                logging.debug(f"Processing unexposed expression: {[t.spelling for t in tokens]}")

                # Check all tokens for global variable references
                for token in tokens:
                    if token.spelling in self.global_vars:
                        var_name = token.spelling
                        logging.debug(f"Found global variable {var_name} in unexposed expression")
                        line_number = token.location.line

                        # Find the statement containing this variable
                        statement = ""
                        current = child
                        while current and current.kind != CursorKind.TRANSLATION_UNIT:
                            if (
                                current.kind == CursorKind.BINARY_OPERATOR
                                or current.kind == CursorKind.UNARY_OPERATOR
                                or current.kind == CursorKind.CALL_EXPR
                                or current.kind == CursorKind.MEMBER_REF_EXPR
                            ):
                                statement = "".join(t.spelling for t in current.get_tokens())
                                break
                            current = current.semantic_parent

                        # If we didn't find a statement, look for a parent call expression
                        if not statement:
                            current = child
                            while current and current.kind != CursorKind.TRANSLATION_UNIT:
                                if current.kind == CursorKind.CALL_EXPR:
                                    statement = "".join(t.spelling for t in current.get_tokens())
                                    break
                                current = current.semantic_parent

                        # Always add read access for variable references
                        info.reads.add(
                            ReadAccessInfo(
                                line_number=line_number,
                                statement=statement,
                                var_name=var_name,
                            )
                        )
                        logging.debug(f"Added read of {var_name} in unexposed expression")

                # Also process children recursively
                for subchild in child.get_children():
                    logging.debug(
                        f"Processing unexposed child: {subchild.kind} {subchild.spelling}"
                    )
                    logging.debug(
                        f"Unexposed child tokens: {[t.spelling for t in subchild.get_tokens()]}"
                    )
                    self._process_statements(subchild, info)

            self._process_statements(child, info)

    def _process_function_call(self, node, info):
        """Process a function call node to find variable reads in arguments and nested expressions."""
        # Get the full statement text for logging
        statement = "".join(t.spelling for t in node.get_tokens())
        logging.debug(f"Processing function call: {statement}")
        logging.debug(f"Function call node kind: {node.kind}")
        logging.debug(f"Function call children: {[child.kind for child in node.get_children()]}")
        logging.debug(f"Function call tokens: {[t.spelling for t in node.get_tokens()]}")

        # Process all children of the function call
        for arg in node.get_children():
            logging.debug(f"Processing argument: {arg.kind} {arg.spelling}")

            # If the argument is a direct variable reference
            if arg.kind == CursorKind.DECL_REF_EXPR:
                var_name = arg.spelling
                if var_name in self.global_vars:
                    logging.debug(f"Found global variable {var_name} in function argument")
                    line_number = arg.location.line

                    # Always add read access for variable references
                    info.reads.add(
                        ReadAccessInfo(
                            line_number=line_number,
                            statement=statement,
                            var_name=var_name,
                        )
                    )
                    logging.debug(f"Added read of {var_name} in function argument")

            # If the argument is a more complex expression, process it recursively
            elif arg.kind in [
                CursorKind.BINARY_OPERATOR,
                CursorKind.UNARY_OPERATOR,
                CursorKind.CALL_EXPR,
                CursorKind.PAREN_EXPR,
                CursorKind.MEMBER_REF_EXPR,
                CursorKind.UNEXPOSED_EXPR,
            ]:
                # For member references, we need to process their children
                if arg.kind == CursorKind.MEMBER_REF_EXPR:
                    for child in arg.get_children():
                        if child.kind == CursorKind.DECL_REF_EXPR:
                            var_name = child.spelling
                            if var_name in self.global_vars:
                                logging.debug(
                                    f"Found global variable {var_name} in member reference"
                                )
                                line_number = child.location.line
                                # Always add read access for variable references
                                info.reads.add(
                                    ReadAccessInfo(
                                        line_number=line_number,
                                        statement=statement,
                                        var_name=var_name,
                                    )
                                )
                                logging.debug(f"Added read of {var_name} in member reference")
                # For unexposed expressions, we need to process their children recursively
                elif arg.kind == CursorKind.UNEXPOSED_EXPR:
                    for child in arg.get_children():
                        if child.kind == CursorKind.DECL_REF_EXPR:
                            var_name = child.spelling
                            if var_name in self.global_vars:
                                logging.debug(
                                    f"Found global variable {var_name} in unexposed expression"
                                )
                                line_number = child.location.line
                                # Always add read access for variable references
                                info.reads.add(
                                    ReadAccessInfo(
                                        line_number=line_number,
                                        statement=statement,
                                        var_name=var_name,
                                    )
                                )
                                logging.debug(f"Added read of {var_name} in unexposed expression")
                        else:
                            self._process_statements(child, info)
                else:
                    self._process_statements(arg, info)

        # Also check for any global variables in the function call tokens
        tokens = list(node.get_tokens())
        for token in tokens:
            if token.spelling in self.global_vars:
                var_name = token.spelling
                logging.debug(f"Found global variable {var_name} in function call tokens")
                line_number = token.location.line
                # Always add read access for variable references
                info.reads.add(
                    ReadAccessInfo(
                        line_number=line_number,
                        statement=statement,
                        var_name=var_name,
                    )
                )
                logging.debug(f"Added read of {var_name} in function call tokens")

    def _analyze_main_program(self, cursor):
        """Find and analyze all non-interrupt functions."""
        for node in cursor.get_children():
            if node.kind == CursorKind.FUNCTION_DECL:
                func_name = node.spelling
                # Skip only interrupt handlers, include setup and loop
                if func_name not in self.interrupts:
                    logging.debug(f"Analyzing main program function: {func_name}")
                    # Find the function body
                    for child in node.get_children():
                        if child.kind == CursorKind.COMPOUND_STMT:
                            self._process_statements(child, self.main_program)
                            break

            self._analyze_main_program(node)

    def analyze_race_conditions(self):
        """Analyze potential race conditions between interrupts and main program."""
        # Check for race conditions between main program and interrupts
        for var_name in self.global_vars:
            main_program_accesses = {
                a for a in self.main_program.accesses if a.var_name == var_name and not a.protected
            }
            main_writes = {a for a in main_program_accesses if a.access_type == AccessType.WRITE}

            logging.debug(f"Analyzing {var_name}:")
            logging.debug(f"  Main program accesses: {main_program_accesses}")
            logging.debug(f"  Main program writes: {main_writes}")

            for isr in self.interrupts.values():
                interrupt_accesses = {a for a in isr.accesses if a.var_name == var_name}
                isr_writes = {a for a in interrupt_accesses if a.access_type == AccessType.WRITE}

                logging.debug(f"  Interrupt {isr.name} accesses: {interrupt_accesses}")
                logging.debug(f"  Interrupt {isr.name} writes: {isr_writes}")

                # Check if this variable is accessed by both the interrupt and main program
                if len(main_program_accesses) > 0 and len(interrupt_accesses) > 0:
                    # If either the interrupt or main program writes to the variable, it's a race condition
                    if len(isr_writes) > 0 or len(main_writes) > 0:
                        logging.debug(
                            f"Found race condition for {var_name}: "
                            f"Main accesses: {main_program_accesses}, "
                            f"ISR accesses: {interrupt_accesses}"
                        )
                        # If the interrupt writes to the variable, include all interrupt accesses
                        # If the interrupt only reads, include only the writes (which should be empty)
                        interrupt_race_accesses = (
                            interrupt_accesses if len(isr_writes) > 0 else isr_writes
                        )
                        self.race_conditions.append(
                            RaceCondition(
                                var_name=var_name,
                                interrupt_name=isr.name,
                                main_program_accesses=main_program_accesses,
                                interrupt_accesses=interrupt_race_accesses,
                            )
                        )

    def print_results(self):
        """Report the analysis results in a well-formatted way."""
        if not self.race_conditions:
            print("No potential race conditions detected.")
            return

        print("\n=== Race Condition Analysis Results ===\n")
        print(f"Total potential race conditions found: {len(self.race_conditions)}\n")

        for i, race_condition in enumerate(self.race_conditions, 1):
            print(f"Race Condition #{i}:")
            print(f"Variable: {race_condition.var_name}")
            print(f"Interrupt: {race_condition.interrupt_name}\n")

            print("Main Program Accesses:")
            for access in sorted(race_condition.main_program_accesses, key=lambda x: x.line_number):
                access_type = "WRITE" if access.access_type == AccessType.WRITE else "READ"
                print(f"  - Line {access.line_number}: {access_type} of '{access.var_name}'")
                if access.statement and not access.statement.isspace():
                    print(f"    Statement: {access.statement}")

            print("\nInterrupt Accesses:")
            for access in sorted(race_condition.interrupt_accesses, key=lambda x: x.line_number):
                access_type = "WRITE" if access.access_type == AccessType.WRITE else "READ"
                print(f"  - Line {access.line_number}: {access_type} of '{access.var_name}'")
                if access.statement and not access.statement.isspace():
                    print(f"    Statement: {access.statement}")

            print("\n" + "=" * 50 + "\n")

    def run_analysis(self):
        """Run the analysis."""
        self.find_interrupts()
        self.analyze_race_conditions()
        self.print_results()
