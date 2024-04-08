from .fetchers import *

class Fetcher:
    def __init__(self, url):
        self.url = url

    def fetch(self):
        fetcher = self.getInstance(self.url)
        return fetcher.fetch()

    @staticmethod
    def getInstance(url):
        return Stooq.tryCreate(url) or \
            Investing.tryCreate(url) or \
            BiznesRadar.tryCreate(url) or \
            Morningstar.tryCreate(url) or \
            Kraken.tryCreate(url) or \
            Mock.tryCreate(url)
