# utils/logger.py
import logging
from datetime import datetime

def setup_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(
            f'logs/analytics_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    
    return logger
