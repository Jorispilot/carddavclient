import warnings
from urllib.parse import urlparse

import requests


class Entry(object):

    def __getitem__(self, attr):
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

    def __init__(self, book, contentlength, contenttype, etag, lastmodified, url):
        self.book = book
        self.contentlength = contentlength
        self.contenttype = contenttype
        self.etag = etag
        self.lastmodified = lastmodified
        self.url = url

    def get(self):
        params = self.book._get_parameters()
        params["url"] = self.book.url.scheme + "://" + self.book.url.netloc + self.url
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Certificate has no `subjectAltName`")
            fetched = requests.request("GET", **params)
        with open(self.name + ".vcf", "w") as file:
            file.write(fetched.text)

    @classmethod
    def from_etree(cls, book, node):
        url = node[0].text
        lastmodified = node[1][0][0].text
        contentlength = node[1][0][1].text
        etag = node[1][0][3].text
        etag = etag[1:-1]
        contenttype = node[1][0][4].text
        return cls(book, contentlength, contenttype, etag, lastmodified, url)

    @staticmethod
    def name_it(bookurl, url):
        bookurl = urlparse(bookurl)
        bookurl = "".join(bookurl[2:])
        name = url.split(bookurl,1)[1]
        name = name.rsplit(".vcf",1)[0]
        return name

    @property
    def name(self):
        return self.name_it(self.book.url.geturl(), self.url)
