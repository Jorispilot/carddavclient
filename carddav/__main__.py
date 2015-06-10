import argparse
import logging

from .cmdline import add_args, process


parser = argparse.ArgumentParser(description="Vcards synchronization \
with a CardDav server. Vcards are stored in the current working \
directory.")
add_args(parser)


if __name__ == "__main__":
    logging.basicConfig(level="DEBUG", format="[%(name)s] %(message)s")
    process(parser)
    
