from .custom_logger import CustomLogger

# Wrap the standard logger so callers can pass keyword metadata without raising
class _GlobalLogger:
	def __init__(self, logger):
		self._logger = logger

	def _format(self, msg: str, kwargs: dict) -> str:
		if not kwargs:
			return msg
		try:
			meta = " | " + ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
		except Exception:
			meta = " | <meta>"
		return msg + meta

	def info(self, msg: str, **kwargs) -> None:
		self._logger.info(self._format(msg, kwargs))

	def warning(self, msg: str, **kwargs) -> None:
		self._logger.warning(self._format(msg, kwargs))

	def error(self, msg: str, **kwargs) -> None:
		self._logger.error(self._format(msg, kwargs))

	def exception(self, msg: str, **kwargs) -> None:
		# include traceback
		self._logger.exception(self._format(msg, kwargs))


# Global logger instance for library modules
GLOBAL_LOGGER = _GlobalLogger(CustomLogger().get_logger("document_portal"))

__all__ = ["CustomLogger", "GLOBAL_LOGGER"]

