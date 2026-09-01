#!/usr/bin/env python3
"""Prepare all generated images, and check the content files for problems.

Run this after editing _data/publications.yml (or replacing a source image):

    python3 bin/prepare.py            # do only the missing work
    python3 bin/prepare.py --force    # rebuild everything
    python3 bin/prepare.py --check    # report only, write nothing

Everything is incremental, so running it when nothing has changed is instant and
harmless. Text-only edits (titles, authors, venues, links, news, awards) need no
command at all — Jekyll reads those files directly.

What it does:
  1. avatar          assets/img/miguel.jpeg          -> assets/img/miguel-avatar.jpg
  2. figures         assets/img/publication_preview/ -> assets/img/pub/<id>.jpg
  3. paper previews  arXiv PDF, page 1               -> assets/img/paper/<id>.jpg
  4. checks          dangling ids, duplicates, missing and orphaned images

Needs Pillow (macOS system python3 has it). Paper previews additionally need
network access and macOS `qlmanage`; without either, that step is skipped with a
warning rather than failing.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "_data")
IMG = os.path.join(ROOT, "assets", "img")
SRC_PORTRAIT = os.path.join(IMG, "miguel.jpeg")
OUT_AVATAR = os.path.join(IMG, "miguel-avatar.jpg")
SRC_FIGS = os.path.join(IMG, "publication_preview")
OUT_FIGS = os.path.join(IMG, "pub")
OUT_PAPERS = os.path.join(IMG, "paper")

UA = "mliuschi.github.io site build (mliuschi@stanford.edu)"

# Face landmarks measured on the full-size original, in its pixel coordinates.
# Re-measure these if you replace miguel.jpeg.
FACE = dict(hair_top=522, chin=1551, left=548, right=1343)
HEAD_FRACTION = 0.68     # head height as a share of the square crop
FACE_HEIGHT = 0.46       # where the face centre sits vertically in the crop
AVATAR_PX = 480

PAD = 0.055              # white margin around a paper preview, as a share of page width

# For papers with no `arxiv` link but an open preprint elsewhere. Keyed by id.
PDF_OVERRIDES = {
    # Nature Machine Intelligence paper -> its arXiv preprint
    "nn_to_no": "https://arxiv.org/pdf/2506.10973",
}

# Known-unavailable, recorded so the gaps are intentional rather than a mystery:
#   ice_picking   IEEE TGRS, paywalled, no arXiv version found
#   constraints   OpenReview serves an HTML challenge page, not the PDF
NO_PDF = {"ice_picking", "constraints"}

warnings = []
notes = []


def warn(msg):
    warnings.append(msg)


# ───────────────────────────────────────────────────────────────── data loading

def load_data():
    try:
        import yaml
    except ImportError:
        sys.exit("error: PyYAML not available. Try: python3 -m pip install --user PyYAML")
    def read(name):
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or []
    return read("publications.yml"), read("selected.yml"), read("awards.yml")


def check(pubs, selected, awards):
    ids = []
    for i, p in enumerate(pubs):
        pid = p.get("id")
        if not pid:
            warn("publication #%d (%r) has no id" % (i + 1, (p.get("title") or "?")[:40]))
            continue
        ids.append(pid)
        for field in ("title", "authors", "venue", "year"):
            if not p.get(field):
                warn("%s: missing %s" % (pid, field))
        if p.get("thumb") not in (None, "figure", "paper"):
            warn("%s: thumb=%r is not figure or paper - will fall back to automatic"
                 % (pid, p["thumb"]))
        if not p.get("links"):
            warn("%s: no links, so the title and thumbnail won't be clickable" % pid)
        arxiv = (p.get("links") or {}).get("arxiv")
        if arxiv is not None and not isinstance(arxiv, str):
            # YAML reads an unquoted 2410.16290 as the float 2410.1629 and the
            # trailing zero vanishes silently.
            warn("%s: arxiv id is unquoted, so YAML read it as a %s and it is "
                 "now %s - any trailing zero is already lost. Put quotes around "
                 "the original id in the YAML."
                 % (pid, type(arxiv).__name__, arxiv))

    for pid in set(x for x in ids if ids.count(x) > 1):
        warn("duplicate id %r - _data/selected.yml can't tell them apart" % pid)

    for sid in selected or []:
        if sid not in ids:
            warn("_data/selected.yml lists %r, which is not an id in publications.yml" % sid)

    for a in awards or []:
        if not a.get("year") or not a.get("title"):
            warn("award entry missing year or title: %r" % a)
    if awards and not any(a.get("featured") for a in awards):
        notes.append("no awards are marked `featured: true`, so the homepage "
                     "Honors section will be empty")
    return ids


# ───────────────────────────────────────────────────────────────────── images

def newer(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)


def build_avatar(force):
    from PIL import Image
    if not os.path.exists(SRC_PORTRAIT):
        warn("%s is missing, so the avatar can't be built"
             % os.path.relpath(SRC_PORTRAIT, ROOT))
        return 0
    if not force and not newer(SRC_PORTRAIT, OUT_AVATAR):
        return 0
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
    print("  avatar    rebuilt  (%d bytes)" % os.path.getsize(OUT_AVATAR))
    return 1


def build_figures(force):
    """Figure thumbnails, flattened onto white: the source PNGs are RGBA but
    visually opaque, and PNG re-encoding at this size can make files larger."""
    from PIL import Image
    if not os.path.isdir(SRC_FIGS):
        return 0
    os.makedirs(OUT_FIGS, exist_ok=True)
    n = 0
    for name in sorted(os.listdir(SRC_FIGS)):
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        stem = name.rsplit(".", 1)[0]
        src = os.path.join(SRC_FIGS, name)
        dst = os.path.join(OUT_FIGS, stem + ".jpg")
        if not force and not newer(src, dst):
            continue
        im = Image.open(src)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            flat = Image.new("RGB", im.size, (255, 255, 255))
            flat.paste(im, mask=im.split()[-1])
            im = flat
        else:
            im = im.convert("RGB")
        im.thumbnail((420, 420), Image.LANCZOS)
        im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)
        print("  figure    %s" % stem)
        n += 1
    return n


def first_content_row(im, ignore_left_frac=0.10, thresh=225):
    """Row where real content starts. Papers pad the top of page 1 by very
    different amounts, so a fixed crop looks inconsistent. The left ~10% is
    skipped because arXiv stamps a vertical id down that margin."""
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


def build_paper(pid, url, keep_pdf):
    """curl the PDF -> qlmanage renders its vectors -> Pillow crops 4:3 on white."""
    from PIL import Image
    tmp = os.path.join(ROOT, ".pdftmp")
    os.makedirs(tmp, exist_ok=True)
    pdf = os.path.join(tmp, pid + ".pdf")
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", UA, url, "-o", pdf],
                           capture_output=True)
        if r.returncode != 0 or not os.path.exists(pdf) or os.path.getsize(pdf) < 20000:
            warn("%s: could not download %s" % (pid, url))
            return 0
        with open(pdf, "rb") as fh:
            if fh.read(5) != b"%PDF-":       # HTML error/challenge page
                warn("%s: %s did not return a PDF" % (pid, url))
                return 0
        qdir = os.path.join(tmp, "ql_" + pid)
        subprocess.run(["rm", "-rf", qdir], capture_output=True)
        os.makedirs(qdir, exist_ok=True)
        subprocess.run(["qlmanage", "-t", "-s", "1400", "-o", qdir, pdf],
                       capture_output=True)
        pngs = [f for f in os.listdir(qdir) if f.endswith(".png")]
        if not pngs:
            warn("%s: qlmanage could not render the PDF" % pid)
            return 0
        im = Image.open(os.path.join(qdir, pngs[0])).convert("RGB")
        w, h = im.size
        top = first_content_row(im)
        pad = int(w * PAD)
        cw = w + 2 * pad
        ch = int(cw * 3 / 4)
        canvas = Image.new("RGB", (cw, ch), (255, 255, 255))
        canvas.paste(im.crop((0, top, w, top + min(ch - pad, h - top))), (pad, pad))
        os.makedirs(OUT_PAPERS, exist_ok=True)
        out = os.path.join(OUT_PAPERS, pid + ".jpg")
        canvas.resize((640, 480), Image.LANCZOS) \
              .save(out, "JPEG", quality=84, optimize=True, progressive=True)
        print("  preview   %-22s (%d bytes)" % (pid, os.path.getsize(out)))
        return 1
    finally:
        # The PDFs are only an intermediate; keeping them was 49 MB of clutter.
        if not keep_pdf:
            subprocess.run(["rm", "-rf", tmp], capture_output=True)


def build_papers(pubs, force, keep_pdf):
    n = 0
    for p in pubs:
        pid = p.get("id")
        if not pid:
            continue
        out = os.path.join(OUT_PAPERS, pid + ".jpg")
        if not force and os.path.exists(out):
            continue
        url = PDF_OVERRIDES.get(pid)
        if not url and (p.get("links") or {}).get("arxiv"):
            url = "https://arxiv.org/pdf/%s" % p["links"]["arxiv"]
        if not url:
            if pid not in NO_PDF:
                notes.append("%s: no arXiv link, so no page-1 preview. Add one to "
                             "PDF_OVERRIDES in this script, or set thumb: figure." % pid)
            continue
        n += build_paper(pid, url, keep_pdf)
    return n


def check_images(pubs):
    have_fig = set(f.rsplit(".", 1)[0] for f in os.listdir(OUT_FIGS)) \
        if os.path.isdir(OUT_FIGS) else set()
    have_pap = set(f.rsplit(".", 1)[0] for f in os.listdir(OUT_PAPERS)) \
        if os.path.isdir(OUT_PAPERS) else set()
    ids = set(p["id"] for p in pubs if p.get("id"))

    for p in pubs:
        pid = p.get("id")
        if not pid:
            continue
        if pid not in have_fig and pid not in have_pap:
            warn("%s: no image at all - the row will render without a thumbnail" % pid)
        elif p.get("thumb") == "figure" and pid not in have_fig:
            warn("%s: thumb: figure but assets/img/pub/%s.jpg is missing" % (pid, pid))
        elif p.get("thumb") == "paper" and pid not in have_pap:
            warn("%s: thumb: paper but assets/img/paper/%s.jpg is missing" % (pid, pid))

    for orphan in sorted((have_fig | have_pap) - ids):
        notes.append("orphaned image %r - no publication uses that id" % orphan)

    # These two directories are generated. A hand-dropped source file here (a
    # .png, say) is silently ignored by the site, which looks only for <id>.jpg.
    for d, label in ((OUT_FIGS, "assets/img/pub"), (OUT_PAPERS, "assets/img/paper")):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.startswith("."):
                continue
            if not f.endswith(".jpg"):
                warn("%s/%s is not a .jpg. That directory is generated - put "
                     "source figures in assets/img/publication_preview/ and run "
                     "this script." % (label, f))


# ─────────────────────────────────────────────────────────────────────── main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="rebuild every image")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--keep-pdfs", action="store_true",
                    help="keep downloaded PDFs in .pdftmp instead of deleting them")
    args = ap.parse_args()

    pubs, selected, awards = load_data()
    print("%d publications, %d on the homepage, %d awards"
          % (len(pubs), len(selected or []), len(awards or [])))
    check(pubs, selected, awards)

    built = 0
    if not args.check:
        try:
            import PIL  # noqa: F401
        except ImportError:
            sys.exit("error: Pillow not available. Try: python3 -m pip install --user Pillow")
        built += build_avatar(args.force)
        built += build_figures(args.force)
        built += build_papers(pubs, args.force, args.keep_pdfs)

    check_images(pubs)

    print("\n%s" % ("nothing to build - everything is up to date" if built == 0
                    and not args.check else "%d image(s) written" % built))
    for n in notes:
        print("  note: %s" % n)
    for w in warnings:
        print("  ! %s" % w)
    if warnings:
        print("\n%d warning(s)." % len(warnings))
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
