from policy_layer2.temporal import TemporalConstraint, classify_temporal_relation


def test_duration_vs_deadline_is_trigger_mismatch():
    retention = TemporalConstraint(type="duration", value=7, unit="years", value_days=2555)
    deletion = TemporalConstraint(type="deadline", trigger="deletion request")
    result = classify_temporal_relation(retention, deletion)
    assert result.kind == "trigger_mismatch"
    assert result.is_jointly_satisfiable is False


def test_two_recurring_is_value_only_not_allen():
    a = TemporalConstraint(type="recurring", value=90, unit="days", value_days=90)
    b = TemporalConstraint(type="recurring", value=365, unit="days", value_days=365)
    result = classify_temporal_relation(a, b)
    assert result.kind == "recurring_value_only"


def test_two_absolute_dates_use_allen_relation():
    a = TemporalConstraint(type="absolute_date", start_day=0, end_day=100)
    b = TemporalConstraint(type="absolute_date", start_day=200, end_day=300)
    result = classify_temporal_relation(a, b)
    assert result.kind == "allen"
    assert result.allen_relation == "before"


def test_missing_temporal_constraint_returns_none_kind():
    a = TemporalConstraint(type="recurring", value=90, unit="days", value_days=90)
    result = classify_temporal_relation(a, None)
    assert result.kind == "none"
