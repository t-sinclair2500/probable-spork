from bin.qa.gates import GateResult, pass_fail


def test_pass_fail():
    """Test pass_fail function logic."""
    assert pass_fail(True) == "PASS"
    assert pass_fail(False, warn=True) == "WARN"
    assert pass_fail(False, warn=False) == "FAIL"


def test_gate_result_creation():
    """Test GateResult dataclass creation."""
    result = GateResult(
        gate="test_gate",
        status="PASS",
        metrics={"test_metric": 42},
        thresholds={"test_threshold": 50},
        notes=["Test note"],
    )

    assert result.gate == "test_gate"
    assert result.status == "PASS"
    assert result.metrics["test_metric"] == 42
    assert result.thresholds["test_threshold"] == 50
    assert result.notes == ["Test note"]


def test_gate_result_dict_conversion():
    """Test GateResult conversion to dict."""
    result = GateResult(
        gate="test_gate",
        status="WARN",
        metrics={"metric": 10},
        thresholds={"threshold": 5},
        notes=["Warning note"],
    )

    result_dict = result.__dict__
    assert result_dict["gate"] == "test_gate"
    assert result_dict["status"] == "WARN"
    assert result_dict["metrics"]["metric"] == 10
