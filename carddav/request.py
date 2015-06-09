import logging
import requests
import xml.etree.ElementTree as etree
from requests.auth import HTTPBasicAuth


__all__ = ["list_vcards"]


logger = logging.getLogger("CardDavClient.Requests")


def get_parameters(config):
    p = dict()
    p["url"]    = config["server"].get("addressbook-url")
    p["verify"] = config["server"].get("ca-certificate")
    user = config["server"].get("user")
    password = config["server"].get("password")
    if password is "":
        password = input("password?")
    p["auth"]   = HTTPBasicAuth(user, password)
    return p


def list_vcards(config):
    p = get_parameters(config)
    r = requests.request("PROPFIND", **p)
    root = etree.fromstring(r.text)
    for child in root:
        href = child[0]
        if not href.text.endswith(".vcf"):
            continue
        name = href.text.rsplit("/")[-1]
        etag = child[1][0][3].text
        etag = etag[1:-1]
        print(etag, name)
        
