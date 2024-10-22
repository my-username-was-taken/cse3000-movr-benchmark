import argparse
import logging

LOG_FORMAT = "%(asctime)s %(name)10s %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class Command:
    """Base class for a command"""

    NAME = "<not_implemented>"
    HELP = ""
    DESCRIPTION = ""

    def create_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.NAME, description=self.DESCRIPTION, help=self.HELP
        )
        parser.set_defaults(run=self.initialize_and_do_command)
        self.add_arguments(parser)
        return parser

    def add_arguments(self, parser):
        pass

    def initialize_and_do_command(self, args):
        pass


def initialize_and_run_commands(description, commands, args=None):
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="command name")
    subparsers.required = True

    for command in commands:
        command().create_subparser(subparsers)

    parsed_args = parser.parse_args(args)
    parsed_args.run(parsed_args)
