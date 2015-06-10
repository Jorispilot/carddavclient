import argparse
import logging
from pathlib import Path
from io import StringIO
from sys import stdout

from .config import config
from .propfind import ressources_info


__all__ = ["add_args", "process"]


def process(parser):
    logger = logging.getLogger("CardDavClient")
    args = parser.parse_args()
    config_file = Path(args.config)
    ##
    if args.command == "dump-config":
        dump_config(config_file, config)
        return
    ##
    read_config(config_file, config, logger)
    ##
    if args.command == "print-config":
        with StringIO() as buffer:
            config.write(buffer)
            buffer.seek(0)
            print(buffer.read())
        return
    ##
    if args.command == "info":
        ressources_info(config, stdout)


def add_args(parser):
    parser.add_argument(
        "--config", type=str, default="config", metavar="FILE",
        help="Configuration file. (Default: config)")
    subparsers = parser.add_subparsers(
        dest="command", metavar="COMMAND", help="Command to execute")
    subparser_dump = subparsers.add_parser(
        'dump-config', help="Dump a default config file.")
    subparser_print = subparsers.add_parser(
        "print-config", help="Print config.")
    subparser_info = subparsers.add_parser(
        "info", help="Server information.")
    

def dump_config(config_file, config):
    do_overwrite = False
    if config_file.exists():
        do_overwrite = input("The config file exists, really overwrite it? [Y/n]")
        do_overwrite = do_overwrite.startswith("Y")
    else:
        do_overwrite = True
    if not config_file.exists():
        config_file = Path("config")
    if do_overwrite:
        with config_file.open("w") as file:
            config.write(file)


def read_config(config_file, config, logger):
    if config_file.exists():
        config.read(str(config_file))
        logger.debug("Config file read: " + str(config_file))
    else:
        logger.info("No config file found at " + str(config_file))
    
