"""Render two original, silent, seamless 10-second loops for the workspace pages.

Optional authoring dependencies: numpy, Pillow, imageio-ffmpeg (not app dependencies).
Both films are decorative artwork, not footage or live data.
"""
from pathlib import Path
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw
import imageio_ffmpeg

OUT = Path(__file__).resolve().parents[1] / 'app/static/media'
WIDTH, HEIGHT, FPS, SECONDS = 960, 540, 24, 10
FRAMES = FPS * SECONDS
GREEN = np.array([104, 232, 137], dtype=float)
RED = np.array([231, 78, 94], dtype=float)
ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
NX, NY = xs / WIDTH - .5, ys / HEIGHT - .5


def contour_field(phase):
    """Interference of travelling waves, thresholded into thin contour lines."""
    field = np.zeros((HEIGHT, WIDTH))
    for index, (fx, fy, speed) in enumerate(((7, 3, 1), (-4, 8, 1), (5, -6, 2), (9, 9, 1))):
        field += np.sin(fx * NX * 2 * math.pi + fy * NY * 2 * math.pi + speed * phase + index)
    radial = np.hypot(NX * 1.6, NY) * 14
    field += np.sin(radial - phase)
    lines = np.exp(-((np.abs(np.sin(field * 1.7)) - 1) ** 2) * 420)
    vignette = np.clip(1.15 - np.hypot(NX * 1.1, NY * 1.4) * 1.5, 0, 1)
    glow = lines * vignette
    frame = np.zeros((HEIGHT, WIDTH, 3))
    frame += np.array([4, 9, 6]) + glow[..., None] * GREEN * .85
    hot = np.clip(np.sin(field * .9 + phase) - .93, 0, 1) * 10 * vignette
    frame += hot[..., None] * RED * .55
    return Image.fromarray(np.clip(frame, 0, 255).astype('uint8'))


def terrain_frame(phase):
    """Perspective wireframe surface whose wave pattern repeats exactly each loop."""
    image = Image.new('RGB', (WIDTH, HEIGHT), (4, 9, 6))
    draw = ImageDraw.Draw(image)
    rows, cols = 34, 46
    points = np.zeros((rows, cols, 2))
    heights = np.zeros((rows, cols))
    for row in range(rows):
        depth = row / (rows - 1)
        scale = .28 + depth * 1.1
        for col in range(cols):
            lateral = col / (cols - 1) - .5
            lift = (math.sin(lateral * 9 + phase) * math.cos(depth * 7 - phase)
                    + .5 * math.sin(lateral * 17 - 2 * phase + depth * 5)) * 26 * scale
            points[row, col] = (WIDTH / 2 + lateral * WIDTH * 1.45 * scale, 150 + depth * 430 - lift)
            heights[row, col] = lift
    for row in range(rows):
        for col in range(cols - 1):
            level = float(np.clip((heights[row, col] / (30 * (.28 + row / rows)) + 1) / 2, 0, 1))
            tint = tuple(int(c) for c in (30 + level * 74, 70 + level * 162, 42 + level * 95))
            fade = .25 + .75 * row / rows
            colour = tuple(int(c * fade) for c in tint)
            draw.line([tuple(points[row, col]), tuple(points[row, col + 1])], fill=colour, width=1)
    for col in range(cols):
        for row in range(rows - 1):
            fade = .2 + .7 * row / rows
            colour = tuple(int(c * fade) for c in (46, 112, 66))
            draw.line([tuple(points[row, col]), tuple(points[row + 1, col])], fill=colour, width=1)
    return image


def encode(name, render):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{WIDTH}x{HEIGHT}', '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'fast', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               str(OUT / f'{name}.mp4')]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for number in range(FRAMES):
        image = render(2 * math.pi * number / FRAMES)
        if number == 0:
            image.save(OUT / f'{name}-poster.jpg', quality=88)
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait():
        raise RuntimeError(f'Video encoding failed for {name}')
    print(OUT / f'{name}.mp4')


if __name__ == '__main__':
    encode('signal-contours', contour_field)
    encode('market-terrain', terrain_frame)
