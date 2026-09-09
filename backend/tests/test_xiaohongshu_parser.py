from app.platforms import xiaohongshu_adapter


def test_xhs_parses_observed_normal_note_state_and_images():
    note_id = "6a73dffa000000002c006ead"
    html = f'''
    <html><body><script>
    window.__INITIAL_STATE__={{"global":{{"maybe":undefined}},"note":{{"noteDetailMap":{{
      "{note_id}":{{"comments":{{"list":[]}},"note":{{
        "xsecToken":"share-token",
        "noteId":"{note_id}",
        "type":"normal",
        "title":"test image note",
        "user":{{"nickname":"owner"}},
        "imageList":[
          {{"width":1179,"height":1558,"urlDefault":"http://sns-webpic-qc.xhscdn.com/path/a!nd_dft_wlteh_webp_3","infoList":[{{"imageScene":"WB_DFT","url":"http://sns-webpic-qc.xhscdn.com/path/a!nd_dft_wlteh_webp_3"}}]}},
          {{"width":1080,"height":1440,"urlDefault":"https://sns-webpic-qc.xhscdn.com/path/b.jpg","infoList":[]}}
        ]
      }} }}
    }}}}}};
    </script></body></html>
    '''
    state = xiaohongshu_adapter._extract_initial_state(html)
    note = xiaohongshu_adapter._note_from_state(state, note_id)
    assert note["type"] == "normal"
    assets = xiaohongshu_adapter._image_assets(note)
    assert len(assets) == 2
    assert [asset.id for asset in assets] == ["image:0", "image:1"]
    assert all(asset.kind == "image" for asset in assets)
    assert assets[0].preview_url.startswith("https://sns-webpic-qc.xhscdn.com/")
    assert assets[0].ext == "webp"
    assert assets[0].width == 1179
    assert assets[0].height == 1558


def test_xhs_video_state_prefers_larger_progressive_stream():
    note = {
        "noteId": "6aaaaaaaaaaaaaaaaaaaaaaa",
        "type": "video",
        "imageList": [
            {
                "width": 720,
                "height": 1280,
                "urlDefault": "https://sns-webpic-qc.xhscdn.com/cover.webp",
            }
        ],
        "video": {
            "media": {
                "stream": {
                    "h264": [
                        {
                            "masterUrl": "https://sns-video-qc.xhscdn.com/low.mp4",
                            "width": 720,
                            "height": 1280,
                            "avgBitrate": 1000000,
                            "size": 2000000,
                        },
                        {
                            "masterUrl": "https://sns-video-qc.xhscdn.com/high.mp4",
                            "backupUrls": ["https://sns-video-qc.xhscdn.com/high-backup.mp4"],
                            "width": 1080,
                            "height": 1920,
                            "avgBitrate": 3000000,
                            "size": 8000000,
                        },
                    ],
                    "h265": [
                        {
                            "masterUrl": "https://sns-video-qc.xhscdn.com/h265.mp4",
                            "width": 720,
                            "height": 1280,
                        }
                    ],
                }
            }
        },
    }
    candidates = xiaohongshu_adapter._collect_video_candidates(note)
    assert candidates
    assert candidates[0][0] == "https://sns-video-qc.xhscdn.com/high.mp4"
    assert candidates[0][1:3] == (1080, 1920)
    assert all("m3u8" not in item[0] for item in candidates)


def test_xhs_asset_id_resolution_helpers_reject_non_xhs_cdn():
    assert xiaohongshu_adapter._https_xhs_cdn("http://sns-webpic-qc.xhscdn.com/a.webp") == "https://sns-webpic-qc.xhscdn.com/a.webp"
    assert xiaohongshu_adapter._https_xhs_cdn("https://evil.example/a.webp") is None
