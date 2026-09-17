from app.evaluation.safety import SAFETY_DATASET, run_safety_evaluation


def test_fixed_dataset_has_required_categories_unique_ids_and_safe_size():
    assert {case.category for case in SAFETY_DATASET} == {
        "ROUTINE",
        "CONCERNING",
        "URGENT",
        "AMBIGUOUS",
        "INCOMPLETE",
        "CONFLICTING",
        "ADVERSARIAL",
    }
    assert 20 <= len(SAFETY_DATASET) <= 30
    assert len({case.case_id for case in SAFETY_DATASET}) == len(SAFETY_DATASET)


def test_evaluation_is_reproducible_and_does_not_require_external_api():
    assert run_safety_evaluation() == run_safety_evaluation()


def test_confusion_matrix_and_false_negative_visibility_are_explicit():
    report = run_safety_evaluation()
    assert report["metrics"] == {
        "total_cases": 21,
        "correct_cases": 20,
        "accuracy": 20 / 21,
        "TP": 18,
        "FP": 1,
        "TN": 2,
        "FN": 0,
        "precision": 18 / 19,
        "recall": 1.0,
        "false_negative_rate": 0.0,
    }
    assert report["false_negative_cases"] == []
    assert sum(1 for item in report["results"] if item["outcome"] == "TN") == 2


def test_sensitive_categories_and_adversarial_inputs_remain_conservative():
    report = run_safety_evaluation()
    outcomes = {item["case_id"]: item for item in report["results"]}
    for category in ("URGENT", "AMBIGUOUS", "INCOMPLETE", "CONFLICTING", "ADVERSARIAL"):
        assert all(
            item["actual_escalation_required"]
            for item in outcomes.values()
            if item["category"] == category
        )
