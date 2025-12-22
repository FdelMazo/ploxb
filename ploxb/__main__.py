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
    def run(self, source: str):
        scanner = Scanner(source)
        try:
            tokens = scanner.scan()
        except Exception as e:
            traceback.print_exc()
            print(f"Scanning Error: {e}")
            return None

        compiler = Compiler(tokens)
        try:
            chunk = compiler.compile()
        except Exception as e:
            traceback.print_exc()
            print(f"Compilation Error: {e}")
            return None

        if not chunk:
            return

        chunk.dis()
        vm = VM(chunk)
        try:
            vm.run()
        except Exception as e:
            print(f"Runtime Error: {e}")
            return

    def main(self):
        parser = argparse.ArgumentParser(
            prog="ploxb",
            description="Lox bytecode compiler in Python",
        )
        parser.add_argument(
            "file", nargs="?", help="Interpret a file instead of running the REPL"
        )

        args = parser.parse_args()

        if args.file:
            with open(args.file, "r") as file:
                source = file.read()
                self.run(source)
                return

        while True:
            try:
                source = promptsession.prompt("> ")
            except (EOFError, KeyboardInterrupt):
                break

            self.run(source)


def main():
    ploxb = Ploxb()
    ploxb.main()


if __name__ == "__main__":
    main()
