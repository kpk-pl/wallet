from ..model import Quote
from .base import BaseFetcher, FetchError
from urllib.parse import urlparse, parse_qs


class Mock(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("mock://") or url.startswith("http://mocking.com")

    def __init__(self, url):
        super(Mock, self).__init__(url)

    def fetch(self):
        try:
            url = urlparse(self.url)
            params = {key: values[0] for (key, values) in parse_qs(url.query).items()}
            return Quote(**params)
        except Exception as err:
            raise FetchError(self.url, err)
