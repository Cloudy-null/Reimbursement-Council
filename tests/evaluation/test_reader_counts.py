from reimbursement_council.evaluation.reader_counts import reader_summary


def test_rates_are_out_of_what_was_returned_and_compared() -> None:
    counts = [
        {"returned": 6, "kept": 5, "made_up": 1, "qr_compared": 3, "qr_mismatch": 0},
        {"returned": 4, "kept": 3, "implausible": 1, "qr_compared": 1, "qr_mismatch": 1},
    ]
    summary = reader_summary(counts, [2.0, 4.0, 9.0])
    assert summary["made_up_rate"] == 0.1
    assert summary["implausible_rate"] == 0.1
    assert summary["qr_mismatch_rate"] == 0.25
    assert summary["seconds_per_document_median"] == 4.0


def test_no_model_answers_give_no_rates() -> None:
    assert "made_up_rate" not in reader_summary([{}], [])
