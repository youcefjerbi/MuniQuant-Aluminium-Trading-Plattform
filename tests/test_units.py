from decimal import Decimal

import pytest

from app.units import UnitError, normalize, resolve_unit


@pytest.mark.parametrize(('reported','canonical'),[
    ('tpa','t/year'),
    ('KTPA','kt/year'),
    ('Mtpa','Mt/year'),
    ('tonnes per year','t/year'),
])
def test_explicit_unit_aliases(reported,canonical):
    assert resolve_unit(reported)==canonical


def test_mass_rate_normalization_is_decimal_and_dimension_checked():
    value,base,reported=normalize('0.4','Mtpa',expected_dimension='MASS_RATE')
    assert value==Decimal('4E+5')
    assert base=='t/year'
    assert reported=='Mt/year'
    with pytest.raises(UnitError,match='dimension'):
        normalize('10','MW',expected_dimension='MASS_RATE')


@pytest.mark.parametrize('ambiguous',['mtpa','MTPA','mt/year'])
def test_ambiguous_lowercase_megatonne_aliases_are_rejected(ambiguous):
    with pytest.raises(UnitError,match='ambiguous'):
        resolve_unit(ambiguous)
