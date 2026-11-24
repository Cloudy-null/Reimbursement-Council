"""A logging filter that masks personal data in every record before a handler writes it."""

import logging

from reimbursement_council.core.privacy import mask_personal_data


class MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_personal_data(record.getMessage())
        record.args = None
        return True


def mask_all_logs() -> None:
    """Put the filter on every handler of the root logger (call after logging is set up)."""
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, MaskingFilter) for f in handler.filters):
            handler.addFilter(MaskingFilter())
