import configparser
import logging


__all__ = ["config"]


config = configparser.ConfigParser()
config['server'] = {"url": "",
                    "ca-certificate": "",
                    "password": "",
                    "user": ""}
config['local'] = {"dir": ".",
                   "propfind_cache": "propfind_cache.pickle"}


def check(config):
    logger = logging.getLogger("CardDavClient.config")
    if not config.get("server", "url").endswith("/"):
        logger.warning("Server url does not ends with a '/'. Adding it.")
        logger.warning("Modify your config file to get rid of this message.")
        config["server"]["url"] += "/"
        

config.check = lambda :check(config)
