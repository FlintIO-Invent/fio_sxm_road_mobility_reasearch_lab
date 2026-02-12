from sxm_mobility.assignment.bpr import bpr_time


def test_bpr_time_monotonic_in_flow():
    t0 = 10.0
    cap = 100.0
    t1 = bpr_time(t0, flow=0.0, capacity=cap)
    t2 = bpr_time(t0, flow=50.0, capacity=cap)
    t3 = bpr_time(t0, flow=200.0, capacity=cap)
    assert t1 <= t2 <= t3
