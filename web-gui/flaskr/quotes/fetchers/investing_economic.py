from ..model import Quote
from .base import BaseFetcher, FetchError
from decimal import Decimal
import dateutil.parser
import subprocess
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

    investing.com's WAF blocks the `requests`/urllib TLS fingerprint (403),
    so we fetch via the system `curl`, whose TLS signature gets through.
    """

    _UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    _NEXT_DATA_RE = re.compile(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

    @staticmethod
    def validUrl(url):
        return url.startswith("https://pl.investing.com/economic-calendar/")

    def __init__(self, url):
        super(InvestingEconomic, self).__init__(url)

    def _fetchPage(self):
        try:
            proc = subprocess.run(
                ["curl", "-sSf", "-A", self._UA, self.url],
                capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, OSError) as e:
            raise FetchError(self.url, e)
        if proc.returncode != 0:
            raise FetchError(self.url,
                             f"curl failed (exit {proc.returncode}): {proc.stderr.strip()}")
        return proc.stdout

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
