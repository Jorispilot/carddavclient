import logging
import pickle
from pathlib import Path

from .tools import gen_digest, path_it


class CacheEntry(object):
    """Local copy of a vcard stored on a CardDAV server.
    
    The local copy can be kept synchronized with the server by storing
    metadata. Use the methods to perform the corresponding
    operation while updating metadata.

    """
    def __init__(self, local_cache, name, etag, digest=None):
        """Low-level object initialization. Try to use one of the .from_*()
        methods instead.

        """
        self.local_cache = local_cache
        self.name = name
        self.etag = etag
        self.digest = digest

    def delete(self):
        """Removes the local copy.

        """
        self.path.unlink()
        del self.local_cache.cache[self.name]
        del self

    @classmethod
    def from_file(cls, local_cache, path):
        """Builds an object from a file.

        """
        ## Do not add add ETag here because there is no local data.
        ## Do not add digest here since there is no data on the
        ## server.
        name = local_cache.identify(path)
        return cls(local_cache, name, None, None)

    @classmethod
    def from_propfindentry(cls, local_cache, propfind_entry):
        """Builds an object from propfind information.

        """
        ## Do not add add ETag here because there is no local data.
        ## Do not add digest here since there is no data on the
        ## server.
        return cls(local_cache, propfind_entry.name, None, None)

    @property
    def _logger(self):
        return logging.getLogger("CardDavClient.LocalCache.{}".format(self.name))

    def move(self, dest_name_or_path):
        dest_name = self.local_cache.identify(dest_name_or_path)
        dest_path = path_it(self.local_cache.cache_dir, dest_name_or_path)
        self.path.rename(dest_path)
        self.local_cache.cache[dest_name] = self.local_cache.cache.pop(self.name)
        self.name = dest_name

    @property
    def path(self):
        """Path to the local copy."""
        return path_it(self.local_cache.cache_dir, self.name)

    def save_from_server(self, response):
        """Save a vcard from CardDAV server."""
        digest = gen_digest(response.text)
        self._logger.debug("Digest: {}".format(digest))
        self._logger.debug("Writing into: {}".format(self.path))
        with self.path.open("w") as file:
            file.write(response.text)
            self.etag = response.headers["ETag"]
            self.digest = digest
            

class LocalCache(object):
    """Manager for local vcard copies of a CardDAV server.

    Before all, use the `.start()` method to load metadata. Each
    synchronized copy has a corresponding entry in the `.cache` dict.

    """
    def __init__(self, config):
        localconfig = config["local"]
        self.cache_dir = Path(localconfig.get("dir"))
        cache_file = Path(localconfig.get("propfind_cache"))
        self.cache_file = cache_file
        ##
        self._cache = dict()

    def _dump_metadata(self):
        """Save cache metadata."""
        self._logger.debug("Writing cache.")
        with self.cache_file.open("wb") as file:
            pickle.dump(self.cache, file)

    def _load_metadata(self):
        if not self.cache_file.exists():
            return
        self._logger.debug("Reading cache.")
        with self.cache_file.open("rb") as file:
            data = pickle.load(file)
            self.cache.update(data)
            for name in data:
                self._logger.debug("New cache: {}".format(name))

    @property
    def cache(self):
        """Contains cache metadata."""
        return self._cache

    @property
    def cache_file(self):
        """File that stores cache metadata between sessions."""
        return self._cache_file
    @cache_file.setter
    def cache_file(self, path):
        self._cache_file = path

    @staticmethod
    def identify(name_or_path):
        """Returns the cache entry name from either its name of its path.

        """
        path = Path(name_or_path)
        if path.exists():
            name = path.name.rsplit(".vcf")[0]
        else:
            name = name_or_path
        return name

    @property
    def _logger(self):
        return logging.getLogger("CardDavClient.LocalCache")

    def start(self):
        """Sets the object ready."""
        self._load_metadata()
