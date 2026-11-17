import pytest
from app.engine.cpm_pert import calculate_cpm, analyze_cpm


def test_mandatory_cpm_case():
    activities = [
        {"id": "A", "duration": 3.0},
        {"id": "B", "duration": 4.0},
        {"id": "C", "duration": 2.0},
        {"id": "D", "duration": 2.0},
    ]
    precedences = [
        {"predecessor_id": "A", "successor_id": "B", "relation_type": "FS", "lag": 1.0},
        {"predecessor_id": "B", "successor_id": "C", "relation_type": "SS", "lag": -1.0},
        {"predecessor_id": "A", "successor_id": "C", "relation_type": "FF", "lag": 0.0},
        {"predecessor_id": "B", "successor_id": "D", "relation_type": "FF", "lag": -2.0},
    ]
    res = calculate_cpm(activities, precedences, project_deadline=8.0)
    assert res["A"]["es"] == 0.0 and res["A"]["ef"] == 3.0
    assert res["B"]["es"] == 4.0 and res["B"]["ef"] == 8.0
    assert res["C"]["es"] == 3.0 and res["C"]["ef"] == 5.0
    assert res["D"]["es"] == 4.0 and res["D"]["ef"] == 6.0


def test_fs_plus_one_expected_dates():
    result = calculate_cpm(
        [{"id": "A", "duration": 3}, {"id": "B", "duration": 4}],
        [{"predecessor_id": "A", "successor_id": "B", "relation_type": "FS", "lag": 1}],
    )
    assert result["A"]["es"] == 0
    assert result["A"]["ef"] == 3
    assert result["B"]["es"] == 4
    assert result["B"]["ef"] == 8


def test_multiple_relations_between_same_pair_are_both_preserved():
    result = calculate_cpm(
        [{"id": "A", "duration": 3}, {"id": "B", "duration": 4}],
        [
            {"predecessor_id": "A", "successor_id": "B", "relation_type": "FS", "lag": 0},
            {"predecessor_id": "A", "successor_id": "B", "relation_type": "SS", "lag": 0},
        ],
    )
    assert result["B"]["es"] == 3
    assert result["B"]["ef"] == 7


@pytest.mark.parametrize("relation,lag,expected_es", [
    ("FS", 0, 5), ("SS", 2, 2), ("FF", 0, 3), ("SF", 0, 0),
    ("FS", -2, 3), ("SS", -2, 0),
])
def test_relation_types_and_negative_lag_respect_project_start(relation, lag, expected_es):
    result = calculate_cpm(
        [{"id": "A", "duration": 5}, {"id": "B", "duration": 2}],
        [{"predecessor_id": "A", "successor_id": "B", "relation_type": relation, "lag": lag}],
    )
    assert result["B"]["es"] == expected_es



def test_multiple_relations_are_order_independent():
    activities = [{"id": "A", "duration": 3}, {"id": "B", "duration": 4}]
    fs = {"predecessor_id": "A", "successor_id": "B", "relation_type": "FS", "lag": 0}
    ss = {"predecessor_id": "A", "successor_id": "B", "relation_type": "SS", "lag": 0}
    first = calculate_cpm(activities, [fs, ss])
    second = calculate_cpm(activities, [ss, fs])
    assert first["B"]["es"] == second["B"]["es"] == 3


def test_impossible_deadline_reports_negative_float():
    summary = analyze_cpm([{"id": "A", "duration": 10}], [], project_deadline=5)
    assert summary["deadline_feasible"] is False
    assert summary["project_finish"] == 10
    assert summary["activities"]["A"]["tf"] == -5
    assert summary["activities"]["A"]["is_critical"] == 1


def test_cycle_is_rejected():
    activities = [{"id": "A", "duration": 1}, {"id": "B", "duration": 1}]
    relations = [
        {"predecessor_id": "A", "successor_id": "B", "relation_type": "FS", "lag": 0},
        {"predecessor_id": "B", "successor_id": "A", "relation_type": "FS", "lag": 0},
    ]
    with pytest.raises(ValueError, match="Ciclo"):
        calculate_cpm(activities, relations)


def test_unknown_activity_and_invalid_relation_are_rejected():
    with pytest.raises(ValueError, match="inexistente"):
        calculate_cpm([{"id": "A", "duration": 1}], [{"predecessor_id": "A", "successor_id": "B"}])
    with pytest.raises(ValueError, match="Tipo de relação"):
        calculate_cpm([{"id": "A", "duration": 1}, {"id": "B", "duration": 1}], [{"predecessor_id": "A", "successor_id": "B", "relation_type": "XX"}])
