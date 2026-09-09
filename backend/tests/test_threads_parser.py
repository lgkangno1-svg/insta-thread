from app.platforms import threads_adapter


def test_threads_selects_exact_target_post_not_recommendation():
    html = '''
    <html><head><meta property="og:url" content="https://www.threads.com/@owner/post/TARGET1"></head>
    <body><script type="application/json">{
      "recommended": {"code":"OTHER1","video_versions":[{"url":"https://cdn.example/other.mp4"}]},
      "target": {"code":"TARGET1","caption":{"text":"hello"},"user":{"username":"owner"},
        "video_versions":[{"url":"https://cdn.example/target.mp4"}],
        "image_versions2":{"candidates":[{"url":"https://cdn.example/cover.jpg","width":1080,"height":1920}]}}
    }</script></body></html>
    '''
    post, code = threads_adapter._extract_target('https://www.threads.com/@owner/post/TARGET1', html)
    assert code == 'TARGET1'
    assert post['code'] == 'TARGET1'
    flat = threads_adapter._flatten_assets(post)
    assert any(x['url'].endswith('/target.mp4') for x in flat)
    assert all(not x['url'].endswith('/other.mp4') for x in flat)
    assert any(x['kind'] == 'video' for x in flat)
    assert any(x['kind'] == 'thumbnail' and x['url'].endswith('/cover.jpg') for x in flat)


def test_threads_share_link_uses_canonical_target():
    html = '''<html><head><meta property="og:url" content="https://www.threads.com/@owner/post/ABC999"></head>
    <script type="application/json">{"post":{"code":"ABC999","image_versions2":{"candidates":[{"url":"https://cdn.example/a.jpg","width":800,"height":800}]}}}</script></html>'''
    post, code = threads_adapter._extract_target('https://www.threads.com/share/xyz/', html)
    assert code == 'ABC999'
    assert post['code'] == 'ABC999'
    flat = threads_adapter._flatten_assets(post)
    assert flat
    assert all(x['kind'] == 'image' for x in flat)
    assert flat[0]['url'].endswith('/a.jpg')


def test_threads_carousel_classifies_each_unit_by_media_type():
    post = {
        'code': 'MIXED1',
        'carousel_media': [
            {
                'video_versions': [{'url': 'https://cdn.example/v.mp4'}],
                'image_versions2': {'candidates': [{'url': 'https://cdn.example/v-cover.jpg', 'width': 720, 'height': 1280}]},
            },
            {
                'image_versions2': {'candidates': [{'url': 'https://cdn.example/photo.jpg', 'width': 1080, 'height': 1080}]},
            },
        ],
    }
    flat = threads_adapter._flatten_assets(post)
    assert [x['kind'] for x in flat] == ['video', 'thumbnail', 'image']
