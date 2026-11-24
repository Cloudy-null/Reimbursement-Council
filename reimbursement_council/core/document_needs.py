"""Which documents a claim needs, and a specific request for each one that is missing.

The groups come from config/documents.yaml per benefit category. A claim with no known
category still needs a billing document (an invoice or a receipt).
"""

from collections.abc import Sequence

from reimbursement_council.config.models import LanguageMessages, Settings
from reimbursement_council.core.models.common import DocumentKind
from reimbursement_council.core.models.decision import DocumentNeed, MemberMessage

BILLING_GROUP: list[DocumentKind] = ["invoice", "receipt"]
"""Every claim needs one of these, whatever its category."""


def _names(group: Sequence[DocumentKind], language: LanguageMessages) -> str:
    return f" {language.or_word} ".join(language.documents[kind] for kind in group)


def document_needs(
    categories: Sequence[str], kinds: Sequence[DocumentKind], settings: Settings
) -> list[DocumentNeed]:
    groups: list[list[DocumentKind]] = [list(BILLING_GROUP)]
    for category in categories:
        for group in settings.documents.required_by_category.get(category, []):
            if group not in groups:
                groups.append(list(group))
    present = set(kinds)
    messages = settings.messages
    return [
        DocumentNeed(
            group=group,
            satisfied=bool(present & set(group)),
            request=MemberMessage(
                en=messages.en.requests.missing_document.format(
                    documents=_names(group, messages.en)
                ),
                ar=messages.ar.requests.missing_document.format(
                    documents=_names(group, messages.ar)
                ),
            ),
        )
        for group in groups
    ]
