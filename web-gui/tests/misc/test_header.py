import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from flaskr.header import HeaderData


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_header_from_empty_database(client):
    with client.application.app_context():
        hd = HeaderData(showLabels=True)

        assert hd.showLabels == True
        assert hd.allLabels == []
        assert hd.lastQuoteUpdate == None
