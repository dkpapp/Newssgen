import os
import math
import subprocess
import tempfile
from datetime import timedelta
from PIL import Image, ImageDraw, ImageFont

# Grid rules helper
def grid_dimensions(n):
    if n <= 4:
        return (2, 2)
    if n <= 9:
        return (3, 3)
    if n <= 16:
        return (4, 4)
    return (5, 4)  # 17..20 -> 5 cols, 4 rows


def _format_timestamp(seconds):
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _ffmpeg_extract_frame(input_url, time_s, out_path):
    # Use -ss before -i for speed. If you need frame-accurate seeking, swap positions.
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(time_s),
        "-i",
        input_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode}): {proc.stderr}")


def _overlay_timestamp(image: Image.Image, timestamp_text: str):
    draw = ImageDraw.Draw(image)
    # Choose font size relative to image height
    font_size = max(12, image.height // 25)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    # Compute text size
    text_w, text_h = draw.textsize(timestamp_text, font=font)
    margin = max(6, image.height // 80)
    x = image.width - text_w - margin
    y = image.height - text_h - margin
    # Draw subtle outline for readability
    outline_color = "black"
    for ox, oy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        draw.text((x + ox, y + oy), timestamp_text, font=font, fill=outline_color)
    draw.text((x, y), timestamp_text, font=font, fill="white")
    return image


def _create_placeholder(cell_size):
    w, h = cell_size
    img = Image.new("RGB", (w, h), "black")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(12, h // 15))
    except Exception:
        font = ImageFont.load_default()
    text = "No Image"
    tw, th = draw.textsize(text, font=font)
    draw.text(((w - tw) / 2, (h - th) / 2), text, fill=(160, 160, 160), font=font)
    return img


def _fit_and_pad(img: Image.Image, target_size):
    target_w, target_h = target_size
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    out = Image.new("RGB", (target_w, target_h), "black")
    x = (target_w - img.width) // 2
    y = (target_h - img.height) // 2
    out.paste(img, (x, y))
    return out


def generate_screenshots(source, timestamps, mode="Grid", output_dir=None):
    """
    source: file path or remote URL/stream
    timestamps: iterable of seconds (floats or ints)
    mode: 'Normal' or 'Grid' (case-insensitive). Defaults to 'Grid'
    Returns:
      - Normal: list of image file paths
      - Grid: single image file path
    """
    mode = mode.lower()
    timestamps = list(timestamps)
    n = len(timestamps)
    if n < 1 or n > 20:
        raise ValueError("Number of screenshots must be between 1 and 20")

    tmpdir = output_dir or tempfile.mkdtemp(prefix="ssgen_")
    image_paths = []
    for idx, t in enumerate(timestamps, start=1):
        out_path = os.path.join(tmpdir, f"ss_{idx:02d}.jpg")
        _ffmpeg_extract_frame(source, t, out_path)
        image_paths.append(out_path)

    if mode == "normal":
        return image_paths

    # Grid mode:
    cols, rows = grid_dimensions(n)
    slots = cols * rows

    images = []
    for i, path in enumerate(image_paths):
        img = Image.open(path).convert("RGB")
        ts_text = _format_timestamp(timestamps[i])
        img = _overlay_timestamp(img, ts_text)
        images.append(img)

    max_w = max((im.width for im in images), default=640)
    max_h = max((im.height for im in images), default=360)
    cell_w, cell_h = max_w, max_h

    MAX_CELL = 1080
    if cell_w > MAX_CELL or cell_h > MAX_CELL:
        scale = min(MAX_CELL / cell_w, MAX_CELL / cell_h)
        cell_w = int(cell_w * scale)
        cell_h = int(cell_h * scale)

    cells = [_fit_and_pad(im, (cell_w, cell_h)) for im in images]

    while len(cells) < slots:
        cells.append(_create_placeholder((cell_w, cell_h)))

    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "black")
    for i, cell in enumerate(cells[:slots]):
        cx = (i % cols) * cell_w
        cy = (i // cols) * cell_h
        canvas.paste(cell, (cx, cy))

    out_path = os.path.join(tmpdir, "grid_screenshots.jpg")
    canvas.save(out_path, quality=92)
    return out_path
