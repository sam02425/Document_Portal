import logging
from typing import Optional


class CustomLogger:
	"""Simple configurable logger helper used in notebooks.

	Usage:
		logger = CustomLogger().get_logger("my-name")
		logger.info("hello")
	"""

	def __init__(self, level: int = logging.INFO):
		self.level = level

	def _configure_handler(self, handler: logging.Handler) -> None:
		fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
		handler.setFormatter(fmt)
		handler.setLevel(self.level)

	def get_logger(self, name: str, level: Optional[int] = None) -> logging.Logger:
		"""Return a logger configured with a stream handler.

		This is intentionally simple so it works inside notebooks without
		relying on external config files.
		"""
		logger = logging.getLogger(name)
		logger.setLevel(level if level is not None else self.level)

		# If no handlers configured, add a StreamHandler to avoid duplicate logs
		if not logger.handlers:
			handler = logging.StreamHandler()
			self._configure_handler(handler)
			logger.addHandler(handler)

		return logger
