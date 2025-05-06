import FlashMCP
from FlashMCP.utilities.tests import temporary_settings


class TestTemporarySettings:
    def test_temporary_settings(self):
        with temporary_settings(log_level="DEBUG"):
            assert FlashMCP.settings.settings.log_level == "DEBUG"
        assert FlashMCP.settings.settings.log_level == "INFO"
