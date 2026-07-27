from app.services.preventive_service import calculate_cycle_progress


def test_calculate_cycle_progress_uses_cycle_and_remaining_hours():
    result = calculate_cycle_progress(20320, 20000, 20500)

    assert result["hours_used"] == 320.0
    assert result["hours_remaining"] == 180.0
    assert result["cycle_hours"] == 500.0
    assert result["percent_used"] == 64.0
    assert result["status"] == "ATENCAO"


def test_calculate_cycle_progress_applies_operational_thresholds():
    assert calculate_cycle_progress(20499, 20000, 20500)["status"] == "CRITICA"
    assert calculate_cycle_progress(20400, 20000, 20500)["status"] == "PROXIMA"
    assert calculate_cycle_progress(20300, 20000, 20500)["status"] == "ATENCAO"
    assert calculate_cycle_progress(20250, 20000, 20500)["status"] == "NO_PRAZO"
    assert calculate_cycle_progress(20500, 20000, 20500)["status"] == "VENCIDA"


def test_calculate_cycle_progress_without_plan_data_returns_sem_dados():
    result = calculate_cycle_progress(None, None, None)

    assert result["status"] == "SEM_DADOS"
    assert result["hours_remaining"] is None
