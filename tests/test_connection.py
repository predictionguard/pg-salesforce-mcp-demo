import pytest
from src.salesforce_connection import SalesforceConnection
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def sf_conn():
    return SalesforceConnection(
        consumer_key=os.getenv("SF_CONSUMER_KEY"),
        consumer_secret=os.getenv("SF_CONSUMER_SECRET"),
        domain=os.getenv("SF_DOMAIN"),
    )


def test_connection(sf_conn):
    sf = sf_conn.connect()
    assert sf is not None
    assert sf_conn.test_connection() is True


def test_query_products(sf_conn):
    sf_conn.connect()
    result = sf_conn.sf.query("SELECT Id, Name FROM Product2 LIMIT 5")
    assert result["totalSize"] >= 0
