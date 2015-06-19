import argparse
import logging
from pathlib import Path
from io import StringIO
from sys import stdout

from .config import config
from .addressbook import CardDavAddressBook


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
    if config_file.exists():
        config.read(str(config_file))
        logger.debug("Config file read: " + str(config_file))
    else:
        logger.info("No config file found at " + str(config_file))
        do_dump = False
        do_dump = input("Should I dump one? [y/N]")
        if do_dump:
            dump_config(config_file, config)
            return
    ##
    if args.command == "get":
        command_get(args, config)
    ##
    if args.command == "info":
        book = CardDavAddressBook(config)
        book.start()
        book.info(stdout)
    ##
    if args.command == "mv":
        command_mv(args, config)
    ##
    if args.command == "put":
        command_put(args, config)
    ##
    if args.command == "rm":
        command_rm(args, config)
    ##
    if args.command == "print-config":
        with StringIO() as buffer:
            config.write(buffer)
            buffer.seek(0)
            print(buffer.read())
        return


def add_args(parser):
    parser.add_argument(
        "--config", type=str, default="config", metavar="FILE",
        help="Configuration file. (Default: config)")
    subparsers = parser.add_subparsers(
        dest="command", metavar="COMMAND", help="Command to execute")
    subparser_dump = subparsers.add_parser(
        'dump-config', help="Dump a default config file.")
    subparser_get = subparsers.add_parser(
        "get", help="Download vcards.")
    subparser_get.add_argument("-a","--all",action="store_true",
                               help="Download ALL vcards.")
    subparser_get.add_argument("-f","--force",action="store_true",
                               help="Force download. (Default: False)",
                               default=False)
    subparser_get.add_argument("names",nargs="*",
                               help="List of vcard identifiers.")
    subparser_info = subparsers.add_parser(
        "info", help="Server information.")
    subparser_mv = subparsers.add_parser(
        "mv", help="Move vcards.")
    subparser_mv.add_argument("orig", help="Vcard identifier.")
    subparser_mv.add_argument("dest", help="Vcard identifier.")
    subparser_print = subparsers.add_parser(
        "print-config", help="Print config.")
    subparser_put = subparsers.add_parser(
        "put", help="Upload vcards.")
    subparser_put.add_argument("-a","--all",action="store_true",
                               help="Upload ALL vcards.")
    subparser_put.add_argument("-f","--force",action="store_true",
                               help="Force upload. (Default: False)",
                               default=False)
    subparser_put.add_argument("names",nargs="*",
                               help="List of vcard identifiers.")
    subparser_rm = subparsers.add_parser(
        "rm", help="Remove vcards.")
    subparser_rm.add_argument("-k","--keep-cache",action="store_true",
                              help="Keep cached vcards. (Default: False)",
                              default=False)
    subparser_rm.add_argument("names",nargs="*",
                              help="List of vcards identifiers.")


def command_get(args, config):
    book = CardDavAddressBook(config)
    book.start()
    if args.all:
        get_list = book.propfind
    else:
        get_list = args.names
    book.get(get_list, force=args.force)


def command_mv(args, config):
    book = CardDavAddressBook(config)
    book.start()
    book.move(args.orig, args.dest)


def command_put(args, config):
    book = CardDavAddressBook(config)
    book.start()
    if args.all:
        put_list = book.cache
    else:
        put_list = args.names
    book.put(put_list, force=args.force)


def command_rm(args, config):
    book = CardDavAddressBook(config)
    book.start()
    book.delete(args.names, keep_cache=args.keep_cache)
    

def dump_config(config_file, config):
    do_overwrite = False
    if config_file.exists():
        do_overwrite = input("The config file exists, really overwrite it? [y/N]")
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
    
