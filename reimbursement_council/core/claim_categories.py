"""The benefit categories of a claim, from the services matched on its billing document."""

from collections.abc import Mapping, Sequence

from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.reference import PriceListItem


def claim_categories(items: Sequence[LineItem], prices: Mapping[str, PriceListItem]) -> list[str]:
    """Sorted, unique categories of the matched items. Unmatched items add nothing."""
    return sorted(
        {
            prices[item.service_code].category
            for item in items
            if item.service_code is not None and item.service_code in prices
        }
    )
