from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_analyze_rejects_unsupported_domain_without_network():
    r = client.post('/api/v1/analyze', json={'url':'https://example.com/video'})
    assert r.status_code == 400
