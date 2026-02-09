from loguru import logger
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO"):
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
        colorize=True,
    )

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "salesforce_mcp.log",
        level=log_level,
        rotation="1 day",
        retention="7 days",
    )

    return logger
