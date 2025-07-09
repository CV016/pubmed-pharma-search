"""
Logging configuration for the PubMed pharmaceutical search tool.

This module provides centralized logging configuration with appropriate
formatters and handlers for different components of the application.
"""

import logging
import sys
from typing import Optional


class LoggerConfig:
    """Configuration class for application logging."""
    
    @staticmethod
    def setup_logger(
        name: str, 
        level: int = logging.INFO, 
        debug_mode: bool = False
    ) -> logging.Logger:
        """
        Set up a logger with appropriate formatting and handlers.
        
        Args:
            name: Logger name
            level: Logging level (default: INFO)
            debug_mode: Enable debug mode with verbose output
            
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
            
        logger.setLevel(level if not debug_mode else logging.DEBUG)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level if not debug_mode else logging.DEBUG)
        
        # Create formatter
        if debug_mode:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(levelname)s: %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger


def get_logger(name: str, debug_mode: bool = False) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name
        debug_mode: Enable debug mode
        
    Returns:
        Configured logger instance
    """
    return LoggerConfig.setup_logger(name, debug_mode=debug_mode) 