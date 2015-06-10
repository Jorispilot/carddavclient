import logging
import pickle
import warnings
import xml.etree.ElementTree as etree
from pathlib import Path
from requests.auth import HTTPBasicAuth
from time import strftime, strptime, time
from urllib.parse import urlparse

import requests

from .addbk_entry import Entry


__all__ = ["CardDavAddressBook"]


HTTP_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"

logger = logging.getLogger("CardDav.AddressBook")


class AddressBook_servercomm(object):
    """Address book synced to a CardDav server.

    """
    def _get_parameters(self):
        ## Get a suitable version of params for the requests module.
        params = self.params.copy()
        if "auth" not in params:
            if params["password"] is "":
                params["password"] = input("password?")
            params["auth"] = HTTPBasicAuth(params["user"], params["password"])
            self.params["auth"] = params["auth"]
        del params["user"]
        del params["password"]
        return params

    def __init__(self, config):
        serverconfig = config["server"]
        self.url = urlparse(serverconfig.get("url"))
        ## Get server parameters.
        params = dict()
        params["verify"]   = serverconfig.get("ca-certificate")
        params["user"]     = serverconfig.get("user")
        params["password"] = serverconfig.get("password")
        self.params = params
        self.book = dict()
        super().__init__()

    @staticmethod
    def _iter_propfind(request_result):
        root = etree.fromstring(request_result.text)
        for child in root:
            url = child[0].text
            if not url.endswith(".vcf"):
                continue
            yield child

    def fetch(self):
        """Fetch CardDav server information (entries and etag).

        """
        params = self._get_parameters()
        params["url"] = self.url.geturl()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        for node in self._iter_propfind(fetched):
            entry = Entry.from_etree(self, node)
            self.book[entry.name] = entry
            

class AddressBook_localcache(AddressBook_servercomm):
    """Address book synced to a local directory.

    """
    def __init__(self, config):
        localconfig = config["local"]
        ## Get server parameters.
        params = dict()
        filename = Path(localconfig.get("dir"))
        filename = filename / localconfig.get("propfind_cache")
        self.cache_file = filename
        super().__init__(config)
        self.load()

    def dump(self):
        logger.info("Doing cache.")
        with self.cache_file.open("wb") as file:
            pickle.dump(self.book, file)

    def fetch(self):
        super().fetch()
        self.dump()

    def get(self):
        for entry in self.book.values():
            entry.get()

    def load(self):
        if not self.cache_file.exists():
            return
        logger.info("Reading local cache.")
        with self.cache_file.open("rb") as file:
            data = pickle.load(file)
            self.book.update(data)

    
class CardDavAddressBook(AddressBook_localcache):
    """Address book synced to a CardDav server and a local directory.

    """
    def info(self, file):
        entry_number = len(self.book)
        last_entry, last_modified = self.last_modified()
        print("Entries: {:d}".format(entry_number), file=file)
        last_modified = strftime(HTTP_DATE_FORMAT, last_modified)
        print("Last modified: {} ({})".format(last_modified, last_entry.name), file=file)

    def last_modified(self):
        entry_last, date_last = None, strptime("Thu, 28 Jun 2001 14:17:15 GMT", HTTP_DATE_FORMAT)
        for name, entry in self.book.items():
            date = strptime(entry["Last-Modified"], HTTP_DATE_FORMAT)
            if date > date_last:
                entry_last, date_last = entry, date
        return entry_last, date_last
