# Cinematic interface

The overview combines a local looping film, editorial typography, a moving word strip, animated document/network/signal cards, scroll reveals, a small magnetic button effect and a narrated platform-film dialog. Other workspace pages share the updated palette, navigation and hover treatment.

## Media provenance

- `app/static/media/aluminium-motion.mp4`: original, procedurally rendered 12-second silent aluminium-fin sculpture. Decorative artwork, not footage of a registered facility or a live data feed. The matching JPEG is its first frame. Regenerate with `python scripts/render_brand_film.py` after installing optional authoring dependencies `numpy`, `Pillow` and `imageio-ffmpeg` in a development environment. These are not application dependencies.
- `platform-walkthrough.mp4`: the repository's existing `docs/demo/walkthrough.mp4`, reused locally. It shows the earlier evidence interface with fictional demonstration data and AI narration, not the redesigned overview or the later paper-trading extension. Captions are converted from the existing SRT to WebVTT without changing their text or timing. `walkthrough-poster.jpg` is a frame from that video.
- RobCo's about page informed the video-led layout and editorial hierarchy. No RobCo footage, branding, code or imagery is included. No third-party video player, analytics or CDN is required.

## Playback and accessibility

The hero is silent and plays inline while visible. It pauses off-screen, in a hidden tab, while the platform film is open, when the user pauses motion, or when the system requests reduced motion. Autoplay failure leaves a local poster. Native video controls and English captions are available in the platform-film dialog; Escape and Close dismiss it and restore focus to its launcher. Watching that film is an explicit user action, including under reduced motion.

Motion preferences persist locally. Scroll reveals run on navigation, not routine refreshes. Motion-off keeps content visible and the operational tables stationary. The layout responds to desktop and mobile widths. Video assets are included in the Python package-data configuration.

## Dynamic layer (`fx.css`, `fx-background.js`, `fx-ui.js`, `fx-reel.js`)

All scripts are local, dependency-free and CSP-safe (no inline styles, no `innerHTML`). They load after `motion.js` and obey its motion toggle and `prefers-reduced-motion`.

- **Background**: a fixed WebGL fragment shader (domain-warped noise) follows the cursor, drifts with scroll, pulses on click and eases its palette per tab and theme. It renders at half resolution with the pixel ratio capped at 1.5, pauses in hidden tabs and falls back to a CSS gradient without WebGL.
- **Glass and bento**: cards, stats, sidebar and header use `backdrop-filter`; the overview gains a bento video reel.
- **Interaction**: spring-physics tilt and cursor spotlight on cards, trailing cursor ring, animated conic hover borders, click ripples, a gliding nav indicator, kinetic word-by-word headings, scroll-scrubbed headings, count-up statistics, cascading table rows, scroll-velocity marquee skew, a scroll-progress back-to-top ring, a live UTC clock and a command palette (Ctrl/Cmd+K or `/`).
- **Videos**: `signal-contours.mp4` and `market-terrain.mp4` (original, silent, seamless 10-second loops from `scripts/render_extra_films.py`, same optional dependencies as the brand film) join `aluminium-motion.mp4`. The overview reel has play/pause, scrub, speed and fullscreen controls; every other tab shows an ambient banner loop. Films play only while visible and motion is on.
