"""Pure-Python tests, runnable even before dbt build."""
import pytest

from finops.cost_allocation import allocate_shared_cents


def test_even_split_rounds_deterministically():
    assert allocate_shared_cents(101, {'streaming': 1, 'checkout': 1, 'catalog': 1}) == {
        'catalog': 34, 'checkout': 34, 'streaming': 33,
    }


def test_weighted_spend_reconciles_to_the_cent():
    alloc = allocate_shared_cents(101, {'checkout': 3, 'catalog': 1})
    assert alloc == {'checkout': 76, 'catalog': 25}
    assert sum(alloc.values()) == 101


def test_zero_traffic_falls_back_to_equal_allocation():
    assert allocate_shared_cents(5, {'streaming': 0, 'checkout': 0}) == {
        'checkout': 3, 'streaming': 2,
    }


def test_zero_shared_costs():
    assert allocate_shared_cents(0, {'catalog': 50, 'checkout': 80}) == {
        'catalog': 0, 'checkout': 0,
    }


@pytest.mark.parametrize('cents,requests', [(-1, {'catalog': 1}), (1, {}), (1, {'catalog': -2}), (1.5, {'catalog': 10})])
def test_invalid_inputs_rejected(cents, requests):
    with pytest.raises(ValueError):
        allocate_shared_cents(cents, requests)
