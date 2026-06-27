import sys
from loguru import logger

def setup_logger():
    # Remove default handler
    logger.remove()
    
    # Add console handler (Rich-like formatting natively supported by Loguru)
    logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    
    # Add file handler
    logger.add("logs/app_{time}.log", rotation="1 day", retention="7 days", level="DEBUG")
    
    logger.info("Logger initialized successfully.")

# Initialize upon import
setup_logger()
