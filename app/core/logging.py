import logging
import sys
from app.core.config import settings
import newrelic.agent

def setup_logging():
    """
    Configures logging for the application.
    Integrates with New Relic if configured.
    """
    # Create a root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Standard stream handler (stdout)
    handler = logging.StreamHandler(sys.stdout)
    
    # Use New Relic's formatter to automatically include trace/entity metadata
    # This allows New Relic Logs in Context to work seamlessly
    if settings.new_relic_license_key:
        try:
            handler.setFormatter(newrelic.agent.NewRelicContextFormatter())
        except Exception:
            # Fallback to standard formatter if something goes wrong
             handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
    else:
         handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    root_logger.addHandler(handler)

    # Set log levels for specific libraries to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
