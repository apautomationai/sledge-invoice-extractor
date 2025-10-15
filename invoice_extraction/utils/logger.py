"""
Logging configuration for invoice extraction service.
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logger(service_name: str, enable_file_logging: Optional[bool] = None) -> logging.Logger:
    """
    Set up logger with conditional file logging based on DEBUG_LOG environment variable.
    
    Args:
        service_name: Name of the service for log file naming
        enable_file_logging: Force enable/disable file logging. If None, reads from DEBUG_LOG env var.
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Determine if file logging should be enabled
    if enable_file_logging is None:
        debug_log = os.getenv("DEBUG_LOG", "false").lower()
        enable_file_logging = debug_log in ("true", "1", "yes", "on")
    
    # Set log level based on file logging
    if enable_file_logging:
        log_level = logging.DEBUG
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Set up file handler with rotation
        log_file = logs_dir / f"{service_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        print(f"File logging enabled: {log_file}")
    else:
        log_level = logging.ERROR
        print("File logging disabled (set DEBUG_LOG=true to enable)")
    
    # Set up console handler for errors
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # Set logger level
    logger.setLevel(log_level)
    
    # Prevent duplicate logs in parent loggers
    logger.propagate = False
    
    return logger
