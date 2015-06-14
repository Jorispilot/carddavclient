import logging
import pickle
from pathlib import Path

from .tools import gen_digest


class CacheEntry(object):
    """Metadata associated to a cached ressource

    """
    def __init__(self, local_cache, name, etag, digest=None):
        self.local_cache = local_cache
        self.name = name
        self.etag = etag
        self.digest = digest

    @classmethod
    def from_propfindentry(cls, local_cache, propfind_entry):
        """Build an object from propfind information.

        """
        ## Do not add add ETag here because there is no local data.
        return cls(local_cache, propfind_entry.name, "000000", "000000")

    @property
    def logger(self):
        return logging.getLogger("CardDavClient.LocalCache.{}".format(self.name))

    @property
    def path(self):
        return self.local_cache.cache_dir.joinpath(self.name + ".vcf")

    def save(self, response):
        digest = gen_digest(response.text)
        self.logger.debug("Digest: {}".format(digest))
        self.logger.debug("Writing into: {}".format(self.path))
        with self.path.open("w") as file:
            file.write(response.text)
            self.etag = response.headers["ETag"]
            self.digest = digest
            

class LocalCache(object):
    """Cache manager for CardDav server ressources.

    """
    def __init__(self, config):
        localconfig = config["local"]
        self.cache_dir = Path(localconfig.get("dir"))
        cache_file = Path(localconfig.get("propfind_cache"))
        self.cache_file = cache_file
        ##
        self._cache = dict()
        ##
        self._load_metadata()

    def _dump_metadata(self):
        """Save cache metadata."""
        self.logger.debug("Writing cache.")
        with self.cache_file.open("wb") as file:
            pickle.dump(self.cache, file)

    def _load_metadata(self):
        if not self.cache_file.exists():
            return
        self.logger.debug("Reading cache.")
        with self.cache_file.open("rb") as file:
            data = pickle.load(file)
            self.cache.update(data)

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
        """Identify an entry according to:
        - its local path
        - its name

        """
        path = Path(name_or_path)
        if path.exists():
            name = path.name.rsplit(".vcf")[0]
        else:
            name = name_or_path
        return name

    @property
    def logger(self):
        return logging.getLogger("CardDavClient.LocalCache")

    def put(self, entry_list, *, force=False):
        """Upload ressources.

        """
        for name in entry_list:
            name = self.identify(name)
            cache_entry = self.cache[name]
            if name in self.propfind:
                propfind_entry = self.propfind[name]
                propfind_entry.put(cache_entry, force=force)
            else:
                ## TODO
                raise KeyError(name)
        self._dump_metadata()
        self.fetch()
