import pytest

from topicgate.core.models.health.health_expectation import EqualCondition


@pytest.mark.parametrize(
    ("actual", "expected", "result"),
    [
        (b"online", b"online", True),
        (b"offline", b"online", False),
        ("online", "online", True),
        ("offline", "online", False),
    ],
)
def test_equal_condition_compares_values_of_the_same_type(
    actual: bytes | str,
    expected: bytes | str,
    result: bool,
) -> None:
    assert EqualCondition.compare(actual, expected) is result


def test_equal_condition_rejects_values_of_different_types() -> None:
    with pytest.raises(
        TypeError,
        match="Actual and expected values must have the same type",
    ):
        EqualCondition.compare(b"online", "online")
