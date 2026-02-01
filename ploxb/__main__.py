#!/usr/bin/env python3

import argparse
import traceback
from ploxb.Scanner import Scanner
from ploxb.Compiler import Compiler
from ploxb.VM import VM

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from pathlib import Path
from platformdirs import user_data_dir
from termcolor import colored


class Ploxb:
    def __init__(self):
        self.vm = VM()

    def run(self, source: str, debug: bool = False):
        scanner = Scanner(source)
        try:
            tokens = scanner.scan()
        except Exception as e:
            if debug:
                traceback.print_exc()
            print(colored(f"Scanning Error: {e}", "light_red"))
            return None

        compiler = Compiler(tokens)
        try:
            main_function = compiler.compile()
        except Exception as e:
            if debug:
                traceback.print_exc()
            print(colored(f"Compilation Error: {e}", "light_red"))
            return None

        if not main_function:
            return

        if debug:
            main_function.dis()
            print()

        try:
            self.vm.run(main_function, debug)
        except Exception as e:
            if debug:
                traceback.print_exc()
            self.vm.stack = []
            self.vm.frames = []
            self.vm.open_upvalues = []
            print(colored(f"Runtime Error: {e}", "light_red"))
            return

    def main(self):
        parser = argparse.ArgumentParser(
            prog="ploxb",
            description="Lox Bytecode compiler in Python",
        )
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        parser.add_argument(
            "file", nargs="?", help="Interpret a file instead of running the REPL"
        )

        args = parser.parse_args()

        if args.file:
            with open(args.file, "r") as file:
                source = file.read()
                self.run(source, args.debug)
                return

        while True:
            history_file = (
                Path(user_data_dir("ploxb", ensure_exists=True)) / ".ploxb_history"
            )
            prompt_session: PromptSession[str] = PromptSession(
                history=FileHistory(history_file)
            )

            try:
                source = prompt_session.prompt("> ")
            except (EOFError, KeyboardInterrupt):
                break

            self.run(source, args.debug)


def main():
    ploxb = Ploxb()
    ploxb.main()


if __name__ == "__main__":
    main()
