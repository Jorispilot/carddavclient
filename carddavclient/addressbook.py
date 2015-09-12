import logging

# import requests

from .localcache import CacheEntry, LocalCache
from .servercomm import PropfindEntry, ServerComm


__all__ = ["CardDavAddressBook"]


class CardDavAddressBook(ServerComm, LocalCache):
    """Address book synced to a CardDav server and a local files.

    """
    def __init__(self, config):
        ServerComm.__init__(self, config)
        LocalCache.__init__(self, config)

    def delete(self, entries, *, keep_cache=True):
        for name in entries:
            name = self.identify(name)
            ## The ressource must exist on the server.
            if name not in self.propfind:
                raise KeyError(name)
            propfind_entry = self.propfind[name]
            ## Get cache_entry, or create a new one if needed.
            cache_entry = self._get_or_create_cache_entry(name, propfind_entry)
            ##
            propfind_entry.delete()
            ## Remove digest and ETag from local cache as there is
            ## nothing more to compare to.
            cache_entry.digest = None
            cache_entry.etag = None
            if not keep_cache:
                cache_entry.delete()

    def get(self, entries, *, force=False):
        """Get the list of entries.

        The entries argument must be a list of names or paths.

        """
        for name in entries:
            name = self.identify(name)
            ## The ressource must exist on the server.
            if name not in self.propfind:
                raise KeyError(name)
            propfind_entry = self.propfind[name]
            ## Get cache_entry, or create a new one if needed.
            cache_entry = self._get_or_create_cache_entry(name, propfind_entry)
            ##
            propfind_entry.get(cache_entry, force=force)
        self._dump_metadata()

    def _get_or_create_cache_entry(self, name, propfind_entry):
        if name in self.cache:
            cache_entry = self.cache[name]
        else:
            self._logger.debug("New cache entry: {}".format(name))
            cache_entry = CacheEntry.from_propfindentry(
                self, propfind_entry)
            self.cache[name] = cache_entry
            self._dump_metadata()
        return cache_entry

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
    def _logger(self):
        return logging.getLogger("CardDavClient.AddressBook")

    def move(self, name_or_path, dest_name_or_path):
        name = self.identify(name_or_path)
        dest_name = self.identify(dest_name_or_path)
        self._logger.info("Moving {} to {}".format(name, dest_name))
        propfind_entry = self.propfind[name]
        cache_entry = self.cache[name]
        ##
        success = propfind_entry.move(dest_name)
        if success:
            cache_entry.move(dest_name_or_path)

    def put(self, entries, *, force=False):
        """Upload the list of entries.

        The entries arguments is an iterable of names or paths.

        """
        for name_or_path in entries:
            name = self.identify(name_or_path)
            if name in self.cache:
                cache_entry = self.cache[name]
            else:
                ## Create a new entry.
                self._logger.debug("Add new file: {}".format(name_or_path))
                cache_entry = CacheEntry.from_file(self, name_or_path)
                self.cache[name] = cache_entry
                self._dump_metadata()
            if name in self.propfind:
                propfind_entry = self.propfind[name]
                propfind_entry.put(cache_entry, force=force)
            else:
                propfind_entry = PropfindEntry.from_cacheentry(self, cache_entry)
                propfind_entry.put(cache_entry)

    def start(self):
        ServerComm.start(self)
        LocalCache.start(self)
        
