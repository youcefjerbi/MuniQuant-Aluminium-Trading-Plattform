# Cinematic interface

The overview combines a local looping film, editorial typography, a moving word strip, animated document/network/signal cards, scroll reveals, a small magnetic button effect and a narrated platform-film dialog. Other workspace pages share the updated palette, navigation and hover treatment.

## Media provenance

- `app/static/media/aluminium-motion.mp4`: original, procedurally rendered 12-second silent aluminium-fin sculpture. Decorative artwork, not footage of a registered facility or a live data feed. The matching JPEG is its first frame. Regenerate with `python scripts/render_brand_film.py` after installing optional authoring dependencies `numpy`, `Pillow` and `imageio-ffmpeg` in a development environment. These are not application dependencies.
- `platform-walkthrough.mp4`: the repository's existing `docs/demo/walkthrough.mp4`, reused locally. It shows the earlier evidence interface with fictional demonstration data and AI narration, not the redesigned overview or the later paper-trading extension. Captions are converted from the existing SRT to WebVTT without changing their text or timing. `walkthrough-poster.jpg` is a frame from that video.
- RobCo's about page informed the video-led layout and editorial hierarchy. No RobCo footage, branding, code or imagery is included. No third-party video player, analytics or CDN is required.

## Playback and accessibility

The hero is silent and plays inline while visible. It pauses off-screen, in a hidden tab, while the platform film is open, when the user pauses motion, or when the system requests reduced motion. Autoplay failure leaves a local poster. Native video controls and English captions are available in the platform-film dialog; Escape and Close dismiss it and restore focus to its launcher. Watching that film is an explicit user action, including under reduced motion.

Motion preferences persist locally. Scroll reveals run on navigation, not routine refreshes. Motion-off keeps content visible and the operational tables stationary. The layout responds to desktop and mobile widths. Video assets are included in the Python package-data configuration.
