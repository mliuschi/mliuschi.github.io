#!/usr/bin/env python3
"""Generate the site's derived images from their originals.

    assets/img/miguel.jpeg                  -> assets/img/miguel-avatar.jpg  (square headshot)
    assets/img/publication_preview/*.png    -> assets/img/pub/*.jpg          (figure thumbnails)

Run:  python3 bin/make_images.py

Needs Pillow (macOS system python3 already has it). Everything it writes is
committed, so this only needs re-running when you add or replace an original.
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("error: Pillow not available. Try: python3 -m pip install --user Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "img")
SRC_PORTRAIT = os.path.join(IMG, "miguel.jpeg")
OUT_AVATAR = os.path.join(IMG, "miguel-avatar.jpg")
SRC_FIGS = os.path.join(IMG, "publication_preview")
OUT_FIGS = os.path.join(IMG, "pub")

# Face landmarks measured on the full-size original, in its pixel coordinates.
# Re-measure these if you replace miguel.jpeg.
FACE = dict(hair_top=522, chin=1551, left=548, right=1343)
HEAD_FRACTION = 0.68     # head height as a share of the square crop
FACE_HEIGHT = 0.46       # where the face centre sits vertically in the crop
AVATAR_PX = 480          # 2x of the ~132px rendered size


def build_avatar():
    if not os.path.exists(SRC_PORTRAIT):
        print("  ! %s missing, skipping avatar" % os.path.relpath(SRC_PORTRAIT, ROOT))
        return
    im = Image.open(SRC_PORTRAIT).convert("RGB")
    w, h = im.size
    cx = (FACE["left"] + FACE["right"]) // 2
    cy = (FACE["hair_top"] + FACE["chin"]) // 2
    side = int((FACE["chin"] - FACE["hair_top"]) / HEAD_FRACTION)
    left = max(0, min(cx - side // 2, w - side))
    top = max(0, min(cy - int(FACE_HEIGHT * side), h - side))
    im.crop((left, top, left + side, top + side)) \
      .resize((AVATAR_PX, AVATAR_PX), Image.LANCZOS) \
      .save(OUT_AVATAR, "JPEG", quality=86, optimize=True, progressive=True)
    print("  avatar  %-28s %6d bytes" % (os.path.relpath(OUT_AVATAR, ROOT),
                                         os.path.getsize(OUT_AVATAR)))


def build_figures():
    """Figure thumbnails. Converted to JPEG on white: the source PNGs are RGBA
    but visually opaque, and PNG re-encoding at this size can make files larger."""
    if not os.path.isdir(SRC_FIGS):
        print("  ! %s missing, skipping figures" % os.path.relpath(SRC_FIGS, ROOT))
        return
    os.makedirs(OUT_FIGS, exist_ok=True)
    total = 0
    for name in sorted(os.listdir(SRC_FIGS)):
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        stem = name.rsplit(".", 1)[0]
        src = Image.open(os.path.join(SRC_FIGS, name))
        if src.mode in ("RGBA", "LA", "P"):
            src = src.convert("RGBA")
            flat = Image.new("RGB", src.size, (255, 255, 255))
            flat.paste(src, mask=src.split()[-1])
            src = flat
        else:
            src = src.convert("RGB")
        src.thumbnail((420, 420), Image.LANCZOS)
        out = os.path.join(OUT_FIGS, stem + ".jpg")
        src.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        total += os.path.getsize(out)
    n = len(os.listdir(OUT_FIGS))
    print("  figures %-28s %6d bytes across %d files"
          % (os.path.relpath(OUT_FIGS, ROOT), total, n))


if __name__ == "__main__":
    build_avatar()
    build_figures()
