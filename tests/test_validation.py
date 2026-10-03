import pytest

from core.validation import require_bool, require_finite_number, require_int


@pytest.mark.parametrize("value", [True, 1.0, 1.7, "1", None])
def test_integer_boundary_rejects_coercion(value):
    with pytest.raises(ValueError, match="count"):
        require_int(value, "count", minimum=1, maximum=6)


@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_boolean_boundary_rejects_coercion(value):
    with pytest.raises(ValueError, match="enabled"):
        require_bool(value, "enabled")


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf"), -float("inf"), 10**400])
def test_numeric_boundary_rejects_invalid_or_overflowing_values(value):
    with pytest.raises(ValueError, match="weight"):
        require_finite_number(value, "weight")


def test_numeric_ranges_include_endpoints_and_allow_negative_weights():
    assert require_int(1, "count", minimum=1, maximum=6) == 1
    assert require_int(6, "count", minimum=1, maximum=6) == 6
    assert require_finite_number(-2, "weight") == -2.0
    assert require_finite_number(0, "epsilon", minimum=0.0, maximum=1.0) == 0.0
    assert require_finite_number(1, "epsilon", minimum=0.0, maximum=1.0) == 1.0
    for value in (-1, 2):
        with pytest.raises(ValueError):
            require_finite_number(value, "epsilon", minimum=0.0, maximum=1.0)
