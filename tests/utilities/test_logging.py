import logging

from FlashMCP.utilities.logging import get_logger


def test_logging_doesnt_affect_other_loggers(caplog):
    # set FlashMCP loggers to CRITICAL and ensure other loggers still emit messages
    original_level = logging.getLogger("FlashMCP").getEffectiveLevel()

    try:
        logging.getLogger("FlashMCP").setLevel(logging.CRITICAL)

        root_logger = logging.getLogger()
        app_logger = logging.getLogger("app")
        FlashMCP_logger = logging.getLogger("FlashMCP")
        FlashMCP_server_logger = get_logger("server")

        with caplog.at_level(logging.INFO):
            root_logger.info("--ROOT--")
            app_logger.info("--APP--")
            FlashMCP_logger.info("--FASTMCP--")
            FlashMCP_server_logger.info("--FASTMCP SERVER--")

        assert "--ROOT--" in caplog.text
        assert "--APP--" in caplog.text
        assert "--FASTMCP--" not in caplog.text
        assert "--FASTMCP SERVER--" not in caplog.text

    finally:
        logging.getLogger("FlashMCP").setLevel(original_level)
