"""add-member: writes the new member to the website's database in the data folder."""

from pathlib import Path

import pytest

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.cli.main import main
from reimbursement_council.cli.members import web_database
from tests.factories import REPO_CONFIG


def add(tmp_path: Path, *extra: str) -> int:
    return main(
        ["add-member", "--config-dir", str(REPO_CONFIG), "--data-dir", str(tmp_path), *extra]
    )


def test_add_member_saves_and_prints_the_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = add(
        tmp_path,
        "--name",
        "Sara Ahmed",
        "--name-ar",
        "سارة أحمد",
        "--tier",
        "silver",
        "--dependant",
        "Omar Ahmed",
        "--dependant",
        "Lina Ahmed",
        "--used",
        "dental=600",
        "--used",
        "lab=12.50",
    )
    assert code == 0
    (added,) = ClaimStore(web_database(tmp_path)).list_new_members()
    main_member = added.members[0]
    assert main_member.member_id in capsys.readouterr().out
    assert main_member.display_name == "Sara Ahmed"
    assert main_member.name_ar == "سارة أحمد"
    assert [m.display_name for m in added.members[1:]] == ["Omar Ahmed", "Lina Ahmed"]
    assert added.histories[0].limits_used == {"dental": 60000, "lab": 1250}


def test_web_database_is_where_serve_keeps_claims(tmp_path: Path) -> None:
    assert web_database(tmp_path) == tmp_path / "web" / "claims.sqlite"


@pytest.mark.parametrize(
    "extra",
    [
        ("--name", "Sara 2", "--tier", "silver"),
        ("--name", "Sara Ahmed", "--tier", "platinum"),
        ("--name", "Sara Ahmed", "--tier", "silver", "--used", "spa=10"),
        ("--name", "Sara Ahmed", "--tier", "silver", "--used", "dental=-5"),
        ("--name", "Sara Ahmed", "--tier", "silver", "--used", "dental"),
    ],
)
def test_bad_input_saves_nothing(tmp_path: Path, extra: tuple[str, ...]) -> None:
    assert add(tmp_path, *extra) == 2
    assert ClaimStore(web_database(tmp_path)).list_new_members() == []
