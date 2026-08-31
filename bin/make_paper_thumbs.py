#!/usr/bin/env python3
"""Render page-1 previews of each paper into assets/img/paper/.

Pipeline, all macOS built-ins plus Pillow:
    curl the PDF  ->  qlmanage -t (renders the PDF's vectors, so it is genuinely
    sharp rather than upscaled)  ->  Pillow crop to 4:3 with white margins  ->  JPEG

PDF sources are derived automatically from each entry's `arxiv=` field. Papers
without an open-access PDF need an entry in PDF_OVERRIDES, or they simply keep
their figure thumbnail.

Run:  python3 bin/make_paper_thumbs.py
      python3 bin/make_paper_thumbs.py --force    (ignore the PDF cache)

Output is committed, so GitHub Pages never touches the network. Re-run only when
you add a paper.
"""
import os
import re
import subprocess
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("error: Pillow not available. Try: python3 -m pip install --user Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
from bib2yml import split_entries, parse_fields  # noqa: E402  (shared parser)

BIB = os.path.join(ROOT, "_bibliography", "papers.bib")
OUTDIR = os.path.join(ROOT, "assets", "img", "paper")
CACHE = os.path.join(ROOT, ".pdfcache")          # gitignored
UA = "mliuschi.github.io site build (mliuschi@stanford.edu)"

# For papers whose bib entry has no `arxiv=` field but do have an open preprint.
# Verify the rendered preview is the version you want to show.
PDF_OVERRIDES = {
    # Nature Reviews Physics paper -> its arXiv preprint
    "azizzadenesheli2024neural": "https://arxiv.org/pdf/2309.15325",
}

# Known-unavailable, documented so the gap is intentional rather than a mystery:
#   liu2022ice              IEEE TGRS, paywalled, no arXiv version found
#   duruisseaux2024towards  OpenReview serves an HTML challenge page, not the PDF

PAD = 0.055        # white margin added around the page slice, as a share of page width


def pdf_url(key, fields):
    if key in PDF_OVERRIDES:
        return PDF_OVERRIDES[key]
    if fields.get("arxiv"):
        return "https://arxiv.org/pdf/%s" % fields["arxiv"]
    return None


def fetch(url, dest, force=False):
    if not force and os.path.exists(dest) and os.path.getsize(dest) > 20000:
        return True
    r = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", UA, url, "-o", dest],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) < 20000:
        return False
    with open(dest, "rb") as fh:                  # reject HTML error/challenge pages
        return fh.read(5) == b"%PDF-"


def render_page1(pdf, key):
    qdir = os.path.join(CACHE, "ql_" + key)
    subprocess.run(["rm", "-rf", qdir], capture_output=True)
    os.makedirs(qdir, exist_ok=True)
    subprocess.run(["qlmanage", "-t", "-s", "1400", "-o", qdir, pdf],
                   capture_output=True)
    pngs = [f for f in os.listdir(qdir) if f.endswith(".png")]
    return os.path.join(qdir, pngs[0]) if pngs else None


def first_content_row(im, ignore_left_frac=0.10, thresh=225):
    """Row where real content starts.

    Papers pad the top of page 1 by very different amounts (76-212px observed),
    so a fixed crop looks inconsistent. The left ~10% is skipped because arXiv
    stamps a vertical ID down that margin, which would count as content at row 0.
    """
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    x0 = int(w * ignore_left_frac)
    for y in range(0, int(h * 0.5), 2):
        dark = 0
        for x in range(x0, w, 4):
            if px[x, y] < thresh:
                dark += 1
                if dark >= 3:
                    return max(0, y - int(h * 0.012))
    return 0


def crop43(png, out):
    """4:3 preview with generous white margins.

    The page's own margins are tight, so cropping flush to the content looks
    cramped. Compositing the slice onto a larger white canvas reads as a wider
    page margin.
    """
    im = Image.open(png).convert("RGB")
    w, h = im.size
    top = first_content_row(im)
    pad = int(w * PAD)
    cw = w + 2 * pad
    ch = int(cw * 3 / 4)
    canvas = Image.new("RGB", (cw, ch), (255, 255, 255))
    canvas.paste(im.crop((0, top, w, top + min(ch - pad, h - top))), (pad, pad))
    canvas.resize((640, 480), Image.LANCZOS) \
          .save(out, "JPEG", quality=84, optimize=True, progressive=True)
    return os.path.getsize(out)


def main():
    force = "--force" in sys.argv
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    with open(BIB, "r", encoding="utf-8") as fh:
        text = re.sub(r"\A\s*---\s*\n\s*---\s*\n", "", fh.read())

    ok, skipped, failed = [], [], []
    for _t, key, body in split_entries(text):
        f = parse_fields(body)
        stem = (f.get("preview") or "").rsplit(".", 1)[0]
        url = pdf_url(key, f)
        if not stem:
            skipped.append((key, "no preview= filename to name the output"))
            continue
        if not url:
            skipped.append((key, "no open-access PDF"))
            continue
        sys.stdout.write("  %-24s " % key)
        sys.stdout.flush()
        pdf = os.path.join(CACHE, key + ".pdf")
        if not fetch(url, pdf, force):
            print("FETCH FAILED  (%s)" % url)
            failed.append((key, "fetch"))
            continue
        png = render_page1(pdf, key)
        if not png:
            print("RENDER FAILED")
            failed.append((key, "render"))
            continue
        n = crop43(png, os.path.join(OUTDIR, stem + ".jpg"))
        print("ok  %6d bytes" % n)
        ok.append(key)

    print("\n  %d generated, %d skipped, %d failed" % (len(ok), len(skipped), len(failed)))
    for k, why in skipped:
        print("    - %s: %s (keeps its figure)" % (k, why))
    for k, why in failed:
        print("    ! %s: %s (keeps its figure)" % (k, why))
    if ok:
        total = sum(os.path.getsize(os.path.join(OUTDIR, f))
                    for f in os.listdir(OUTDIR) if f.endswith(".jpg"))
        print("  %.1f KB in %s" % (total / 1024, os.path.relpath(OUTDIR, ROOT)))
    print("\n  Now run: python3 bin/bib2yml.py   (picks up which previews exist)")


if __name__ == "__main__":
    main()
