import pandas as pd

from scripts.apps.executive import baseline_delay_from_sweep, deduplicate_connectors


def test_baseline_delay_is_reconstructed_from_scenario_delta() -> None:
    scenarios = pd.DataFrame(
        {
            "avg_delay_min": [7.5, 5.0],
            "delta_avg_delay_min": [-2.5, -5.0],
        }
    )

    assert baseline_delay_from_sweep(scenarios) == 10.0


def test_connector_shortlist_removes_reversed_endpoint_duplicates() -> None:
    scenarios = pd.DataFrame(
        {
            "scenario_id": ["a", "b", "c"],
            "connector_a": [10, 20, 30],
            "connector_b": [20, 10, 40],
            "improve_delay_pct": [8.0, 12.0, 3.0],
        }
    )

    shortlist = deduplicate_connectors(scenarios)

    assert shortlist["scenario_id"].tolist() == ["b", "c"]
