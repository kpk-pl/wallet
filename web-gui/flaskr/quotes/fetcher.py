from .fetchers import *

class Fetcher:
    def __init__(self, url):
        self.url = url

    def fetch(self, unit=None):
        fetcher = self.getInstance(self.url)
        return fetcher.fetch(unit)

    @staticmethod
    def getInstance(url):
        return Stooq.tryCreate(url) or \
            InvestingEconomic.tryCreate(url) or \
            Investing.tryCreate(url) or \
            BiznesRadar.tryCreate(url) or \
            Morningstar.tryCreate(url) or \
            JustETF.tryCreate(url) or \
            Yahoo.tryCreate(url) or \
            BIS.tryCreate(url) or \
            Kraken.tryCreate(url) or \
            Mock.tryCreate(url)
