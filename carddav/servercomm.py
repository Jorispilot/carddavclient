import logging
import warnings
import urllib.parse as urllib
import xml.etree.ElementTree as etree
from pprint import pformat

import requests
from requests.auth import HTTPBasicAuth

from .tools import gen_digest, name_it, url_from_etree


class PropfindEntry(object):
    """PROPFIND information about one ressource

    """
    def __getitem__(self, attr):
        """Defined items:
        - Content-Length
        - Content-Type
        - ETag
        - Last-Modified
        """
        if   attr == "Content-Length":
            return self.contentlength
        elif attr == "Content-Type":
            return self.contenttype
        elif attr == "ETag":
            return self.etag
        elif attr == "Last-Modified":
            return self.lastmodified
        else:
            raise AttributeError(attr)

    def __init__(self, server_comm, contentlength, contenttype, etag,
                 lastmodified, url):
        self.server_comm = server_comm
        self.contentlength = contentlength
        self.contenttype = contenttype
        self.etag = etag
        self.lastmodified = lastmodified
        self.url = url

    def fetch(self):
        """Fetch CardDav server information.

        """
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        self.logger.debug("PROPFIND")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        node = next( self.server_comm._iter_propfind_result(fetched) )
        self._update_from_etree(node)
        self.logger.debug("Content-Length: {Content-Length}".format(**self))
        self.logger.debug("Content-Type: {}".format(self["Content-Type"]))
        self.logger.debug("Etag: {}".format(self["ETag"]))
        self.logger.debug("Last-Modified: {}".format(self["Last-Modified"]))

    @classmethod
    def from_etree(cls, server_comm, node):
        """Build an object from PROPFIND xml result.

        The node argument must be an etree-parsed node.

        """
        url = url_from_etree(node)
        url = server_comm.url.scheme + "://" + server_comm.url.netloc + url
        self = cls(server_comm, "", "", "", "", url)
        self._update_from_etree(node)
        return self

    @classmethod
    def from_cacheentry(cls, server_comm, cache_entry):
        """Build an object from cache information.

        """
        name = cache_entry.path.name
        url = server_comm.url.geturl() + urllib.quote(name)
        self = cls( server_comm, None, None, None, None, url)
        return self

    def get(self, cache_entry, *, force=False):
        """Download a ressource using cache_entry information.

        """
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        ## Add "If-None-Match" only if there is some local data.
        if not force and cache_entry.path.exists():
            params["headers"] = {"If-None-Match": cache_entry.etag}
        ##
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("GET", **params)
        ##
        self.logger.debug("GET {0.status_code} {0.reason}".format(fetched))
        if   fetched.status_code == 200:
            self.logger.info("Downloaded")
        elif fetched.status_code == 304:
            self.logger.info("Not Modified")
        else:
            self.logger.warning("GET {0.status_code} {0.reason}".format(fetched))
        ## Save data.
        if fetched.status_code != 200: ## Do not open file if the request has failed.
            return
        self.logger.debug("Etag: {}".format(fetched.headers["ETag"]))
        cache_entry.save(fetched)

    @property
    def logger(self):
        return logging.getLogger("CardDavClient.ServerComm.{}".format(self.name))
    
    @property
    def name(self):
        """Generate a name from url.

        """
        return name_it(self.server_comm.url.geturl(), self.url)

    def put(self, cache_entry, *, force=False):
        """Upload a ressource using cache_entry information.

        """
        if not cache_entry.path.exists():
            self.logger.error("No local cache.")
            return
        with cache_entry.path.open("r") as file:
            data = file.read()
        ## Check for updated information
        current_digest = gen_digest(data)
        if (not force and self.etag is not None and
            current_digest == cache_entry.digest):
            self.logger.info("Not modified.")
            return
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        params["headers"] = dict()
        params["headers"].update({"Content-Type": "text/x-vcard"})
        if self.etag == None:
            self.logger.debug("Uploading new entry.")
            params["headers"].update({"If-None-Match": cache_entry.etag})
        else:
            params["headers"].update({"If-Match": cache_entry.etag})
        #
        params["data"] = data
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PUT", **params)
        ##
        self.logger.debug("PUT {0.status_code} {0.reason}".format(fetched))
        if fetched.status_code == 201:
            self.logger.info("Created".format(fetched))
            return
        if fetched.status_code == 204:
            self.logger.info("Uploaded".format(fetched))
            return
        elif fetched.status_code == 412:
            self.logger.info("PUT {0.status_code} {0.reason}".format(fetched))
            self.logger.info("Request headers:\n " + pformat(fetched.request.headers))
            self.logger.info("Response headers:\n " + pformat(fetched.headers))
            return
        self.fetch()
        cache_entry.etag = fetched.headers["ETag"]
        cache_entry.digest = current_digest

    def _update_from_etree(self, node):
        self.lastmodified = node[1][0][0].text
        self.contentlength = node[1][0][1].text
        self.etag = node[1][0][3].text
        self.contenttype = node[1][0][4].text

    @property
    def url(self):
        """Ressource url"""
        return self._url
    @url.setter
    def url(self, value):
        self._url = urllib.urlparse(value)


class ServerComm(object):
    """Handle communications with a CardDav server.

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
        self.url = serverconfig.get("url")
        ## Get server parameters.
        params = dict()
        params["verify"]   = serverconfig.get("ca-certificate")
        params["user"]     = serverconfig.get("user")
        params["password"] = serverconfig.get("password")
        self.params = params
        ##
        self._propfind_result = dict()

    @staticmethod
    def _iter_propfind_result(request_result):
        root = etree.fromstring(request_result.text)
        for child in root:
            url = child[0].text
            if not url.endswith(".vcf"):
                continue
            yield child

    def fetch(self):
        """Fetch CardDav server information (entries and etag).

        The data is stored in the propfind property.

        """
        params = self._get_parameters()
        params["url"] = self.url.geturl()
        self.logger.debug("PROPFIND")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        propfind = dict()
        for node in self._iter_propfind_result(fetched):
            entry = PropfindEntry.from_etree(self, node)
            propfind[entry.name] = entry
        ## Updating, deleting
        old_names = set(self.propfind.keys())
        new_names = set(propfind.keys())
        for name in new_names & old_names:
            self.propfind[name] = propfind[name]
        for name in new_names - old_names:
            self.logger.debug("New ressource: {}".format(name))
            self.propfind[name] = propfind[name]
        for name in old_names - new_names:
            self.logger.debug("Deleted ressource: {}".format(name))
            del self.propfind[name]

    @property
    def logger(self):
        return logging.getLogger("CardDavClient.ServerComm")

    @property
    def propfind(self):
        """PROPFIND cached data."""
        return self._propfind_result

    @property
    def url(self):
        """CardDav server url"""
        return self._url
    @url.setter
    def url(self, value):
        self._url = urllib.urlparse(value)
