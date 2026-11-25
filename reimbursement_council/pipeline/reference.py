"""The reference the website decides with: the seeded people plus members added by hand."""

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.core.new_member import with_new_members


def load_reference(seed: ReferenceData, store: ClaimStore) -> ReferenceData:
    return with_new_members(seed, store.list_new_members())
