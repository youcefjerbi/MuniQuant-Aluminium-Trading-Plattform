"""The dynamic background, UI effects and extra films must be local, CSP-safe and seekable."""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / 'app/static'
FX_SCRIPTS = ('fx-background.js', 'fx-ui.js', 'fx-reel.js')
NEW_FILMS = ('signal-contours', 'market-terrain')


def test_index_loads_fx_assets_when_requested(client):
    root = client.get('/').text
    assert '/static/fx.css' in root
    for script in FX_SCRIPTS:
        assert f'/static/{script}' in root


@pytest.mark.parametrize('script', FX_SCRIPTS)
def test_fx_script_is_served_as_javascript(client, script):
    response = client.get(f'/static/{script}')
    assert response.status_code == 200
    assert 'javascript' in response.headers['content-type']


@pytest.mark.parametrize('name', NEW_FILMS)
def test_extra_film_is_seekable_mp4_with_jpeg_poster(client, name):
    video = client.get(f'/static/media/{name}.mp4', headers={'Range': 'bytes=0-63'})
    assert video.status_code == 206
    assert b'ftyp' in video.content
    poster = client.get(f'/static/media/{name}-poster.jpg')
    assert poster.status_code == 200
    assert poster.content[:2] == b'\xff\xd8'


@pytest.mark.parametrize('script', FX_SCRIPTS)
def test_fx_script_avoids_unsafe_sinks_and_remote_hosts(script):
    source = (STATIC / script).read_text()
    assert 'innerHTML' not in source
    assert 'insertAdjacentHTML' not in source
    assert not re.search(r'https?://', source)
    assert 'eval(' not in source


def test_fx_script_references_only_existing_media():
    source = (STATIC / 'fx-reel.js').read_text()
    for film_id in re.findall(r"id:'([a-z-]+)'", source):
        assert (STATIC / 'media' / f'{film_id}.mp4').is_file()
    for poster in re.findall(r"'[a-z-]+':'([a-z-]+\.jpg)'", source):
        assert (STATIC / 'media' / poster).is_file()


def test_fx_css_respects_reduced_motion_and_motion_toggle():
    css = (STATIC / 'fx.css').read_text()
    assert 'prefers-reduced-motion' in css
    assert 'body[data-motion="off"]' in css
