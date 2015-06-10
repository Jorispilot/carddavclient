import logging
import warnings
import xml.etree.ElementTree as etree
from requests.auth import HTTPBasicAuth
from time import strftime, strptime
from urllib.parse import urlparse

import requests


__all__ = ["ressources_info"]


HTTP_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"

logger = logging.getLogger("CardDavClient.Requests")


class Ressources(dict):

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config")
        self.config = config
        super().__init__(self, *args, **kwargs)

    def fetch(self):
        params = self.get_parameters()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("PROPFIND", **params)
        formatted = self.format(fetched.text,)
        self.update(formatted)

    def format(self, text):
        addressbook = self.config["server"].get("addressbook-url")
        addressbook = urlparse(addressbook)
        addressbook = "".join(addressbook[2:])
        root = etree.fromstring(text)
        ressources = dict()
        for child in root:
            url = child[0].text
            if not url.endswith(".vcf"):
                continue
            name = url.split(addressbook,1)[1]
            lastmodified = child[1][0][0].text
            contentlength = child[1][0][1].text
            etag = child[1][0][3].text
            etag = etag[1:-1]
            contenttype = child[1][0][4].text
            ressources[name] = {"Content-Length": contentlength,
                                "Content-Type": contenttype,
                                "ETag": etag,
                                "Last-Modified": lastmodified,
                                "URL": url}
        return ressources
        
    def get_parameters(self):
        p = dict()
        p["url"]    = self.config["server"].get("addressbook-url")
        p["verify"] = self.config["server"].get("ca-certificate")
        user = self.config["server"].get("user")
        password = self.config["server"].get("password")
        if password is "":
            password = input("password?")
        p["auth"]   = HTTPBasicAuth(user, password)
        return p

    def last_modified(self):
        name_last, date_last = None, strptime("Thu, 28 Jun 2001 14:17:15 GMT", HTTP_DATE_FORMAT)
        for name, res in self.items():
            date = strptime(res["Last-Modified"], HTTP_DATE_FORMAT)
            if date > date_last:
                name_last, date_last = name, date
        return name, date_last


def ressources_info(config, file):
    ressources = Ressources(config=config)
    ressources.fetch()
    ressouces_number = len(ressources)
    _, last_modified = ressources.last_modified()
    print("Number of ressources: {:d}".format(ressouces_number), file=file)
    print("Last modified: {}".format(strftime(HTTP_DATE_FORMAT, last_modified)), file=file)
