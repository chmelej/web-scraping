import pytest
from fastapi.testclient import TestClient
from src.api.main import app

def test_api_queue_info_url_hash_history():
    """Verify that get_url_info aggregates results across all queue entries matching url_hash."""
    client = TestClient(app)
    res = client.get("/api/v1/queue/info", params={"url": "https://www.fsgroup.be"})
    if res.status_code == 404:
        pytest.skip("Test data not present in local database")
    
    assert res.status_code == 200
    data = res.json()
    assert data["site_type"] == "single_page"
    assert "history" in data
    assert len(data["history"]) >= 3

    result_ids = [h["result_id"] for h in data["history"]]
    assert 389806 in result_ids  # Scrape result from http://www.fsgroup.be (queue_id 894080)
    assert 902453 in result_ids  # Scrape result from https://www.fsgroup.be (queue_id 2598639)
    assert 902538 in result_ids  # Latest scrape result

    # Check that individual history rows contain scraped URL and queue ID
    for h in data["history"]:
        assert "url" in h
        assert "queue_id" in h
