from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_build_marker_prefers_configured_sha(monkeypatch):
    monkeypatch.setenv('BUILD_SHA', '0123456789abcdef')
    r = client.get('/build.txt')
    assert r.status_code == 200
    assert r.text == '0123456789abcdef\n'
    assert r.headers['cache-control'] == 'no-store'
    assert r.headers['x-robots-tag'] == 'noindex, nofollow, noarchive'


def test_analyze_rejects_unsupported_domain_without_network():
    r = client.post('/api/v1/analyze', json={'url':'https://example.com/video'})
    assert r.status_code == 400


def test_html_aliases_redirect_to_canonical_clean_urls():
    expected = {
        '/index.html': 'https://download.avocadoss.co.kr/',
        '/youtube-downloader.html': 'https://download.avocadoss.co.kr/youtube-downloader',
        '/instagram-reels-downloader.html': 'https://download.avocadoss.co.kr/instagram-reels-downloader',
        '/threads-downloader.html': 'https://download.avocadoss.co.kr/threads-downloader',
        '/douyin-downloader.html': 'https://download.avocadoss.co.kr/douyin-downloader',
        '/xiaohongshu-downloader.html': 'https://download.avocadoss.co.kr/xiaohongshu-downloader',
        '/faq.html': 'https://download.avocadoss.co.kr/faq',
        '/terms.html': 'https://download.avocadoss.co.kr/terms',
        '/privacy.html': 'https://download.avocadoss.co.kr/privacy',
        '/copyright.html': 'https://download.avocadoss.co.kr/copyright',
    }
    for source, target in expected.items():
        r = client.get(source, follow_redirects=False)
        assert r.status_code == 301
        assert r.headers['location'] == target
