from simple_salesforce import Salesforce
import logging

logger = logging.getLogger(__name__)


class SalesforceConnection:
    def __init__(self, consumer_key: str, consumer_secret: str, domain: str):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.domain = domain
        self.sf = None

    def connect(self) -> Salesforce:
        """Establish connection to Salesforce via OAuth Client Credentials flow."""
        logger.info("Connecting to Salesforce via Client Credentials flow")
        try:
            self.sf = Salesforce(
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                domain=self.domain,
            )
            logger.info("Connected to Salesforce")
            return self.sf
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """Test if connection is active."""
        if not self.sf:
            return False
        try:
            self.sf.query("SELECT Id FROM User LIMIT 1")
            return True
        except Exception:
            return False

    def reconnect_if_needed(self):
        """Reconnect if connection lost."""
        if not self.test_connection():
            logger.warning("Connection lost, reconnecting...")
            self.connect()
