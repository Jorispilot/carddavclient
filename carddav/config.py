import configparser


__all__ = ["config"]


config = configparser.ConfigParser()
config['server'] = {"addressbook-url": "",
                    "ca-certificate": "",
                    "password": "",
                    "user": ""}
