from app.services.ip2region_progress import MemoryProgressStore, UpdateProgress


def test_memory_store_roundtrip():
    store = MemoryProgressStore()
    store.set(
        UpdateProgress(
            state="running",
            stage="downloading_v4",
            downloaded_bytes=100,
            total_bytes=200,
            percent=50.0,
            started_at="2026-08-14T00:00:00+00:00",
        )
    )

    status = store.get()
    assert status["state"] == "running"
    assert status["stage"] == "downloading_v4"
    assert status["percent"] == 50.0
    assert status["total_bytes"] == 200


def test_memory_store_empty_returns_idle():
    store = MemoryProgressStore()
    assert store.get()["state"] == "idle"


def test_memory_store_expires_to_idle(monkeypatch):
    store = MemoryProgressStore(ttl_seconds=0.01)
    store.set(UpdateProgress(state="running", stage="checking"))
    import time

    time.sleep(0.03)
    assert store.get()["state"] == "idle"


def test_update_progress_dict_fields():
    progress = UpdateProgress(
        state="success",
        stage="installing",
        percent=100.0,
        version="v3.17.0",
        changed=False,
        message="已是最新",
        started_at="2026-08-14T00:00:00+00:00",
        finished_at="2026-08-14T00:00:01+00:00",
    )
    body = progress.to_dict()
    assert body["state"] == "success"
    assert body["version"] == "v3.17.0"
    assert body["changed"] is False
    assert body["finished_at"]
