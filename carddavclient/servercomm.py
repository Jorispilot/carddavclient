import logging
import warnings
import urllib.parse as urllib
import xml.etree.ElementTree as etree
from pprint import pformat
from subprocess import call

import requests
from pygments import highlight
from pygments.lexers.textfmts import HttpLexer
from pygments.formatters import Terminal256Formatter
from requests.auth import HTTPBasicAuth

from .tools import gen_digest, get_raw_http_request, get_raw_http_response, name_it, url_from_etree, url_it


class PropfindEntry(object):
    """Entry corresponding to a vcard stored on a CardDav server.

    Basic information about the vcard are accessible as object
    items. Use methods to manipulate the vcards on the server.

    """
    def __getitem__(self, attr):
        """PROPFIND information values

        Defined items:
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
        """Low-level object initialization. Try to use one of the .from_*()
        methods instead.

        """
        self.server_comm = server_comm
        self.contentlength = contentlength
        self.contenttype = contenttype
        self.etag = etag
        self.lastmodified = lastmodified
        self.url = url

    def delete(self):
        """Remove a ressource off the server.

        """
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        ##
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("DELETE", **params)
        ##
        self._logger.debug("GET {0.status_code} {0.reason}".format(fetched))
        if   fetched.status_code == 204:
            self._logger.info("Deleted")
        else:
            self._logger.warning("GET {0.status_code} {0.reason}".format(fetched))

    def _do_propfind(self):
        """Fetch PROPFIND information.

        """
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        self._logger.debug("PROPFIND")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        node = next( self.server_comm._iter_propfind_result(fetched) )
        self._update_from_etree(node)
        self._logger.debug("Content-Length: {Content-Length}".format(**self))
        self._logger.debug("Content-Type: {}".format(self["Content-Type"]))
        self._logger.debug("Etag: {}".format(self["ETag"]))
        self._logger.debug("Last-Modified: {}".format(self["Last-Modified"]))

    @classmethod
    def from_etree(cls, server_comm, node):
        """Build an object from xml formated data.

        The node argument is expected to be an xml node coming from a
        PROPFIND response. It should have been parsed by etree.

        """
        url = url_from_etree(node)
        url = server_comm.url.scheme + "://" + server_comm.url.netloc + url
        self = cls(server_comm, "", "", "", "", url)
        self._update_from_etree(node)
        return self

    @classmethod
    def from_cacheentry(cls, server_comm, cache_entry):
        """Build an object from a cache_entry object.

        """
        name = cache_entry.path.name
        url = url_it(server_comm.url, urllib.quote(name))
        return cls(server_comm, None, None, None, None, url)

    def get(self, cache_entry, *, force=False):
        """Download a ressource using cache_entry information.

        Replaces local data if ETag has changed or if forced.

        """
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        ## Add "If-None-Match" only if there is some local data.
        if not force and cache_entry.path.exists():
            params["headers"] = {"If-None-Match": cache_entry.etag}
        ##
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
                fetched = requests.request("GET", **params)
        except OSError as error:
            self._logger.warning("Error: {!s}".format(error))
            return
        ##
        self._logger.debug("GET {0.status_code} {0.reason}".format(fetched))
        if   fetched.status_code == 200:
            self._logger.info("Downloaded")
        elif fetched.status_code == 304:
            self._logger.info("Not Modified")
        else:
            self._logger.warning("GET {0.status_code} {0.reason}".format(fetched))
        ## Save data.
        if fetched.status_code != 200: ## Do not open file if the request has failed.
            return
        self._logger.debug("Etag: {}".format(fetched.headers["ETag"]))
        cache_entry.save_from_server(fetched)

    @property
    def _logger(self):
        return logging.getLogger("CardDavClient.ServerComm.{}".format(self.name))

    def move(self, dest_name_or_url):
        """Mode a ressource to the dest_url.

        """
        dest_url = url_it(self.server_comm.url, dest_name_or_url)
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        ## Add "If-None-Match" only if there is some local data.
        params["headers"] = {"Destination": dest_url}
        ##
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("MOVE", **params)
        ##
        success = False
        self._logger.debug("GET {0.status_code} {0.reason}".format(fetched))
        if   fetched.status_code == 201:
            success = True
            self._logger.info("Moved to new location")
        elif fetched.status_code == 204:
            success = True
            self._logger.info("Moved to existing location")
        else:
            self._logger.warning("GET {0.status_code} {0.reason}".format(fetched))
            self._logger.debug("Request headers:\n " + get_raw_http_request(fetched.request) )
            self._logger.debug("Response headers:\n " + get_raw_http_response(fetched) )
        return success
    
    @property
    def name(self):
        """Generated name from url.

        """
        return name_it(self.server_comm.url.geturl(), self.url)

    def put(self, cache_entry, *, force=False):
        """Upload a ressource using cache_entry information.

        Uploads if local data has been modified only.

        """
        if not cache_entry.path.exists():
            self._logger.error("No local cache.")
            return
        with cache_entry.path.open("r") as file:
            data = file.read()
        ## Check for updated information
        current_digest = gen_digest(data)
        if (not force and self.etag is not None and
            current_digest == cache_entry.digest):
            self._logger.info("Not modified.")
            return
        ## Prepare request.
        params = self.server_comm._get_parameters()
        params["url"] = self.url.geturl()
        params["headers"] = dict()
        params["headers"].update({"Content-Type": "text/x-vcard"})
        if self.etag == None:
            self._logger.debug("Uploading new entry.")
            params["headers"].update({"If-None-Match": cache_entry.etag})
        else:
            params["headers"].update({"If-Match": cache_entry.etag})
        #
        params["data"] = bytes(data, "utf-8")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PUT", **params)
        ##
        self._logger.debug("PUT {0.status_code} {0.reason}".format(fetched))
        if fetched.status_code == 201:
            self._logger.info("Created".format(fetched))
            return
        if fetched.status_code == 204:
            self._logger.info("Uploaded".format(fetched))
            return
        elif fetched.status_code == 412:
            self._logger.info("PUT {0.status_code} {0.reason}".format(fetched))
            self._logger.info("Request headers:\n " + pformat(fetched.request.headers))
            self._logger.info("Response headers:\n " + pformat(fetched.headers))
            return
        self._do_propfind()
        ## Update modification information.
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
    """Communications with an addressbook stored on a CardDav server.

    Each vcard on the server has a corresponding entry in the
    `.propfind` dict. Call `.start()` to populate `.proprind` and use
    the methods attached to the corresponding entry.

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

    def _do_propfind(self):
        params = self._get_parameters()
        params["url"] = self.url.geturl()
        self._logger.debug("PROPFIND")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        fetched.raise_for_status()
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
            self._logger.debug("New ressource: {}".format(name))
            self.propfind[name] = propfind[name]
        for name in old_names - new_names:
            self._logger.debug("Deleted ressource: {}".format(name))
            del self.propfind[name]

    @property
    def _logger(self):
        return logging.getLogger("CardDavClient.ServerComm")

    @property
    def propfind(self):
        """PROPFIND cached data."""
        return self._propfind_result

    def start(self):
        """Get the instance ready to communicate.

        """
        self._do_propfind()

    @property
    def url(self):
        """CardDav server url"""
        return self._url
    @url.setter
    def url(self, value):
        self._url = urllib.urlparse(value)
