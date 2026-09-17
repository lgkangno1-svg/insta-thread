from app import main as main_module


def setup_function():
    main_module._rate_windows.clear()


def teardown_function():
    main_module._rate_windows.clear()


def test_rate_slot_enforces_per_client_limit():
    assert main_module._reserve_rate_slot("analyze", "203.0.113.10", 2, now=100.0)
    assert main_module._reserve_rate_slot("analyze", "203.0.113.10", 2, now=101.0)
    assert not main_module._reserve_rate_slot("analyze", "203.0.113.10", 2, now=102.0)


def test_rate_bucket_cap_rejects_new_keys_until_stale_entries_are_pruned(monkeypatch):
    monkeypatch.setattr(main_module, "_RATE_BUCKETS_MAX", 2)

    assert main_module._reserve_rate_slot("analyze", "203.0.113.1", 20, now=100.0)
    assert main_module._reserve_rate_slot("analyze", "203.0.113.2", 20, now=100.0)
    assert not main_module._reserve_rate_slot("analyze", "203.0.113.3", 20, now=100.0)
    assert len(main_module._rate_windows) == 2

    assert main_module._reserve_rate_slot("analyze", "203.0.113.3", 20, now=161.0)
    assert len(main_module._rate_windows) <= 2
