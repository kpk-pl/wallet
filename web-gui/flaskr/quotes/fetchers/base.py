class FetchError:
    def __init__(self, url, desc):
        self.url = url
        self.desc = desc
        self.msg = str(self.desc)

    def __str__(self):
        return f"Error fetching data from '{self.url}': {self.msg}"


class BaseFetcher:
    def __init__(self, url):
        self.url = url

    @classmethod
    def tryCreate(cls, url):
        if cls.validUrl(url):
            return cls(url)
        return None
