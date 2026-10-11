from app.event_search import rank


def test_normalization_unknown_terms_and_stable_ties():
    assert rank('!!!', ['power']) == []
    assert rank('missing', ['power']) == []
    ranked = rank('ＰＯＷＥＲ', ['power', 'POWER', 'unrelated'])
    assert [row[0] for row in ranked] == [0, 1]
    assert ranked[0][1] == 1.0
    assert rank('power unknown', ['power'])[0][1] < 1.0
    assert rank('électricité', ['ÉLECTRICITÉ'])[0][2] == ['électricité']
