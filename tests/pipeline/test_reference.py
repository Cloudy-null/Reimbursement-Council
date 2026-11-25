"""The website's reference: the seeded people plus members added by hand."""

from pathlib import Path

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.pipeline.reference import load_reference
from reimbursement_council.synthetic.claims import make_claim_set
from tests.core.test_new_member import build
from tests.factories import SUBMITTED_AT, repo_settings


def test_load_reference_is_the_seed_when_nothing_was_added(tmp_path: Path) -> None:
    seed = make_claim_set(7, 0, repo_settings()).reference
    assert load_reference(seed, ClaimStore(tmp_path / "db.sqlite")) == seed


def test_load_reference_adds_stored_members(tmp_path: Path) -> None:
    seed = make_claim_set(7, 0, repo_settings()).reference
    store = ClaimStore(tmp_path / "db.sqlite")
    added = build(dependants=("Omar Ahmed",), used={"dental": "600"})
    store.save_new_member(added, SUBMITTED_AT)
    merged = load_reference(seed, store)
    assert merged.members[: len(seed.members)] == seed.members
    assert merged.members[len(seed.members) :] == added.members
    assert merged.policy(added.policy.policy_id) == added.policy
    assert merged.history(added.members[0].member_id).limits_used == {"dental": 60000}
