"""The cinematic interface must serve local, seekable media and accessible captions."""
def test_cinema_assets_and_seekable_videos(client):
    root = client.get('/').text
    assert '/static/cinema.css' in root
    assert 'id="film-dialog"' in root
    assert 'kind="captions"' in root
    for name in ('aluminium-motion.mp4', 'platform-walkthrough.mp4'):
        response = client.get('/static/media/' + name, headers={'Range': 'bytes=0-63'})
        assert response.status_code == 206
        assert response.headers['content-type'] == 'video/mp4'
        assert len(response.content) == 64
        assert b'ftyp' in response.content
    captions = client.get('/static/media/platform-walkthrough.vtt')
    assert captions.status_code == 200
    assert captions.text.startswith('WEBVTT\n')
    assert '00:00:00.250 --> 00:00:01.701' in captions.text
    for name in ('aluminium-poster.jpg', 'walkthrough-poster.jpg'):
        response = client.get('/static/media/' + name)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/jpeg'
        assert response.content[:2] == b'\xff\xd8'
