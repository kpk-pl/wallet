from ..model import Quote
from .base import BaseFetcher, FetchError
from curl_cffi import requests as cffi_requests
from decimal import Decimal
import dateutil.parser
import json
import re


class InvestingEconomic(BaseFetcher):
    """Fetches a macroeconomic indicator from an investing.com economic
    calendar event page (e.g. Polish CPI YoY at
    https://pl.investing.com/economic-calendar/polish-cpi-445).

    The page is a Next.js app that embeds the event data as structured JSON
    in a <script id="__NEXT_DATA__"> tag, so we parse that rather than
    scraping rendered HTML. The latest released figure lives at
    state.economicCalendarEventStore.closestOccurrences.latest_release.

    investing.com sits behind Cloudflare, which blocks the plain
    `requests`/urllib and stock-`curl` TLS fingerprints (403). We fetch via
    curl_cffi impersonating Chrome, whose JA3/JA4 TLS signature gets through.
    """

    _NEXT_DATA_RE = re.compile(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

    @staticmethod
    def validUrl(url):
        return url.startswith("https://pl.investing.com/economic-calendar/")

    def __init__(self, url):
        super(InvestingEconomic, self).__init__(url)

    def _fetchPage(self):
        try:
            resp = cffi_requests.get(
                self.url, impersonate="chrome", timeout=30)
            resp.raise_for_status()
        except cffi_requests.RequestsError as e:
            raise FetchError(self.url, e)
        return resp.text

    def fetch(self, unit=None):
        html = self._fetchPage()

        m = self._NEXT_DATA_RE.search(html)
        if not m:
            raise FetchError(self.url, "Could not find __NEXT_DATA__ on page")

        try:
            data = json.loads(m.group(1))
            store = data['props']['pageProps']['state']['economicCalendarEventStore']
            release = store['closestOccurrences']['latest_release']
        except (KeyError, TypeError, ValueError) as e:
            raise FetchError(self.url, f"Unexpected page structure: {e}")

        actual = release.get('actual')
        if actual is None:
            raise FetchError(self.url, "No actual value in latest release")

        timestamp = dateutil.parser.parse(release['occurrence_time'])
        # Other fetchers return naive timestamps; drop tzinfo so the stale
        # comparison and chart rendering stay consistent.
        timestamp = timestamp.replace(tzinfo=None)

        event = store.get('event', {})
        name = event.get('long_name') or event.get('short_name')

        return Quote(quote=Decimal(str(actual)), timestamp=timestamp, name=name)
