import os
import logging
from logging.handlers import TimedRotatingFileHandler
from asgiref.sync import async_to_sync
import asyncio
from utilities.helper_functions import parse_log_entry, send_logger_data

LOG_FILE = '/logs/core_service.log'
logger = logging.getLogger(__name__)
SERVER = os.environ.get("SERVER", "SERVER_1")

# TimedRotatingFileHandler to handle log file rotation
file_handler = TimedRotatingFileHandler(filename=LOG_FILE, when="midnight")
formatter = logging.Formatter(
    '%(asctime)s -  %(filename)20s - %(funcName)25s() - %(levelname)10s - %(lineno)s -  %(message)s')

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)


class WebSocketLoggingHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        data = parse_log_entry(log_entry)
        data['server'] = SERVER

        try:
            loop = asyncio.get_running_loop()
            # If inside an event loop
            asyncio.create_task(send_logger_data(data))
        except RuntimeError:
            # No event loop is running (sync context)
            async_to_sync(send_logger_data)(data)


# Adding the WebSocket logging handler
websocket_handler = WebSocketLoggingHandler()
websocket_handler.setFormatter(formatter)
logger.addHandler(websocket_handler)
