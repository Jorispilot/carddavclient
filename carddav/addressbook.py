import logging
# import warnings
# import xml.etree.ElementTree as etree
# from requests.auth import HTTPBasicAuth
# from time import strftime, strptime, time
# from urllib.parse import urlparse

# import requests

from .localcache import CacheEntry, LocalCache
from .servercomm import PropfindEntry, ServerComm


__all__ = ["CardDavAddressBook"]


class CardDavAddressBook(ServerComm, LocalCache):
    """Address book synced to a CardDav server and a local directory.

    """
    def __init__(self, config):
        ServerComm.__init__(self, config)
        LocalCache.__init__(self, config)

    def get(self, entry_list, *, force=False):
        for name in entry_list:
            name = self.identify(name)
            ## The ressource must exist on the server.
            if name not in self.propfind:
                raise KeyError(name)
            propfind_entry = self.propfind[name]
            ## Get cache_entry, or create a new one if needed.
            if name in self.cache:
                cache_entry = self.cache[name]
            else:
                self.logger.debug("New cache entry: {}".format(name))
                cache_entry = CacheEntry.from_propfindentry(
                    self, propfind_entry)
                self.cache[name] = cache_entry
            propfind_entry.get(cache_entry, force=force)
        self._dump_metadata()

    def info(self, file):
        entry_number = len(self.propfind)
        last_entry, last_modified = self.last_modified()
        print("Server entries: {:d}".format(entry_number), file=file)
        last_modified = strftime(HTTP_DATE_FORMAT, last_modified)
        print("Last modified: {} ({})".format(last_modified, last_entry.name), file=file)

    def last_modified(self):
        entry_last, date_last = None, strptime("Thu, 28 Jun 2001 14:17:15 GMT", HTTP_DATE_FORMAT)
        for name, entry in self.propfind.items():
            date = strptime(entry["Last-Modified"], HTTP_DATE_FORMAT)
            if date > date_last:
                entry_last, date_last = entry, date
        return entry_last, date_last

    @property
    def logger(self):
        return logging.getLogger("CardDavClient.AddressBook")

    def put(self, entry_list, *, force=False):
        """Upload ressources.

        """
        for name_or_path in entry_list:
            name = self.identify(name_or_path)
            ## The ressource must exist locally.
            if name not in self.cache:
                raise KeyError(name)
            cache_entry = self.cache[name]
            if name in self.propfind:
                propfind_entry = self.propfind[name]
                propfind_entry.put(cache_entry, force=force)
            else:
                propfind_entry = PropfindEntry.from_cacheentry(self, cache_entry)
                propfind_entry.put(cache_entry)
