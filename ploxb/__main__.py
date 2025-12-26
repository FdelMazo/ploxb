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


history_file = Path(user_data_dir("ploxb", ensure_exists=True)) / ".ploxb_history"
promptsession: PromptSession[str] = PromptSession(history=FileHistory(history_file))


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
            print(f"Scanning Error: {e}")
            return None

        compiler = Compiler(tokens)
        try:
            chunk = compiler.compile()
        except Exception as e:
            if debug:
                traceback.print_exc()
            print(f"Compilation Error: {e}")
            return None

        if not chunk:
            return

        if debug:
            chunk.dis()

        try:
            self.vm.ip = 0
            self.vm.run(chunk)
        except Exception as e:
            if debug:
                traceback.print_exc()
            print(f"Runtime Error: {e}")
            return

    def main(self):
        parser = argparse.ArgumentParser(
            prog="ploxb",
            description="Lox bytecode compiler in Python",
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
            try:
                source = promptsession.prompt("> ")
            except (EOFError, KeyboardInterrupt):
                break

            self.run(source, args.debug)


def main():
    ploxb = Ploxb()
    ploxb.main()


if __name__ == "__main__":
    main()
