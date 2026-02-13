from sxm_mobility.demand.od_generation import scale_od

def test_scale_od_scales_total():
    od = [(1, 2, 100.0), (2, 3, 50.0)]
    out = scale_od(od, 0.8)
    assert abs(sum(q for *_, q in out) - 120.0) < 1e-9

def test_scale_od_preserves_pairs():
    od = [(1, 2, 100.0), (2, 3, 50.0)]
    out = scale_od(od, 0.8)
    assert [(o, d) for o, d, _ in out] == [(1, 2), (2, 3)]
