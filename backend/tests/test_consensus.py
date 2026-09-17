import pytest

from app.schemas.ai import AgreementStatus, TriageClassification
from app.services.consensus import conservative_consensus


@pytest.mark.parametrize(
    ("values", "final", "agreement", "review"),
    [
        (["ROUTINE"] * 3, "ROUTINE", "CONSENSUS", False),
        (["CONCERNING"] * 3, "CONCERNING", "CONSENSUS", False),
        (["URGENT"] * 3, "URGENT", "CONSENSUS", False),
        (["ROUTINE", "CONCERNING", "CONCERNING"], "CONCERNING", "MAJORITY", False),
        (["ROUTINE", "ROUTINE", "URGENT"], "URGENT", "MAJORITY", True),
        (["CONCERNING", "URGENT", "CONCERNING"], "URGENT", "MAJORITY", True),
        (["ROUTINE", "INSUFFICIENT_INFORMATION", "CONCERNING"], "CONCERNING", "DISAGREEMENT", True),
    ],
)
def test_conservative_consensus(values, final, agreement, review):
    result = conservative_consensus([TriageClassification(value) for value in values])
    assert result[0] == TriageClassification(final)
    assert result[1] == AgreementStatus(agreement)
    assert result[2] is review
