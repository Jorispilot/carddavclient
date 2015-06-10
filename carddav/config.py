import configparser


__all__ = ["config"]


config = configparser.ConfigParser()
config['server'] = {"url": "",
                    "ca-certificate": "",
                    "password": "",
                    "user": ""}
config['local'] = {"dir": ".",
                   "propfind_cache": "propfind_cache.pickle"}
