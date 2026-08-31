#!/usr/bin/env python3
"""Convert _bibliography/papers.bib -> _data/publications.yml

BibTeX is the single source of truth for publications. GitHub Pages' native
Jekyll build cannot parse BibTeX, so this script does the conversion and the
generated YAML is committed. Standard library only: no bibtexparser, no
jekyll-scholar, nothing to install.

Run manually:
    python3 bin/bib2yml.py

Or let the pre-commit hook run it for you:
    bash bin/install-hooks.sh

Recognised BibTeX fields (only title/author/year are required):
    journal / booktitle   full venue name
    venue                 short venue label for the tag (overrides VENUE_MAP)
    arxiv                 bare id, e.g. 2402.16845
    code, html, pdf       URLs
    html_label            label for the `html` link (default "HTML")
    preview               figure filename in assets/img/publication_preview/
    award / award_name    award text, shown as a pill
    thumb                 `figure` to show the paper's own figure, `paper` to show
                          the generated page-1 preview. Omit for automatic
                          (paper preview if one exists, else the figure).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIB = os.path.join(ROOT, "_bibliography", "papers.bib")
OUT = os.path.join(ROOT, "_data", "publications.yml")
FIG_DIR = os.path.join(ROOT, "assets", "img", "pub")
PAPER_DIR = os.path.join(ROOT, "assets", "img", "paper")

ME = "Liu-Schiaffini"

# Long venue name -> short tag for the pill. A `venue={...}` field always wins.
VENUE_MAP = [
    (r"arxiv preprint",                                      "Preprint"),
    (r"international conference on machine learning",         "ICML"),
    (r"advances in neural information processing systems",    "NeurIPS"),
    (r"computer vision (and|&) pattern recognition",          "CVPR"),
    (r"international conference on learning representations", "ICLR"),
    (r"nature reviews physics",                               "Nature Rev. Physics"),
    (r"ieee transactions on geoscience and remote sensing",   "IEEE TGRS"),
    (r"icml.*ai for science workshop",                        "ICML Workshop"),
    (r"nature machine intelligence",                           "Nature Mach. Intell."),
    (r"journal of chemical physics",                           "J. Chem. Phys."),
]

# Surname particles that belong with the family name, not the given names.
PARTICLES = {"van", "von", "de", "der", "den", "del", "della", "di", "da",
             "dos", "du", "la", "le", "bin", "ibn", "ter", "ten"}


# ───────────────────────────────────────────────────────────── bibtex parsing

def split_entries(text):
    """Yield (type, key, body) for each @entry{...}, brace-balanced."""
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        etype, key = m.group(1).lower(), m.group(2)
        i = text.index("{", m.start())
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield etype, key, text[i + 1:j]


def parse_fields(body):
    """Parse `name = {value}` / `name = "value"` pairs, brace-aware."""
    out, i, n = {}, 0, len(body)
    while i < n:
        m = re.compile(r"([A-Za-z_-]+)\s*=\s*").search(body, i)
        if not m:
            break
        name, j = m.group(1).lower(), m.end()
        while j < n and body[j] in " \t\r\n":
            j += 1
        if j >= n:
            break
        if body[j] == "{":
            depth, k = 0, j
            while k < n:
                if body[k] == "{":
                    depth += 1
                elif body[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            val, i = body[j + 1:k], k + 1
        elif body[j] == '"':
            k = body.index('"', j + 1)
            val, i = body[j + 1:k], k + 1
        else:
            k = j
            while k < n and body[k] != ",":
                k += 1
            val, i = body[j:k], k
        out[name] = re.sub(r"\s+", " ", val).strip()
    return out


def shorten(full):
    """'Clare E Singer' -> 'C. Singer';  'Jan van Dijk' -> 'J. van Dijk'."""
    toks = full.split()
    if len(toks) < 2:
        return full
    start = len(toks) - 1
    for i, t in enumerate(toks[1:], 1):
        if t.lower() in PARTICLES:
            start = i
            break
    return "%s. %s" % (toks[0][0], " ".join(toks[start:]))


def parse_authors(raw):
    """-> [{full, short, equal, me}]. Preserves the '*' equal-contribution mark
    across the 'Last, First' -> 'First Last' flip."""
    # collapse a repeated separator ('... and and Liu-Schiaffini, Miguel'), which
    # would otherwise glue 'and' onto the next surname
    raw = re.sub(r"\band\s+and\b", "and", raw)
    out = []
    for part in re.split(r"\s+and\s+", raw):
        part = part.strip().rstrip(",").strip()
        if not part:
            continue
        if part.lower() in ("others", "et al", "et al."):
            out.append(dict(full="et al.", short="et al.", equal=False, me=False))
            continue
        equal = False
        if "," in part:
            last, first = part.split(",", 1)
            last, first = last.strip(), first.strip()
            if last.endswith("*"):
                last, equal = last[:-1].strip(), True
            full = ("%s %s" % (first, last)).strip()
        else:
            full = part
        if full.endswith("*"):
            full, equal = full[:-1].strip(), True
        out.append(dict(full=full, short=shorten(full), equal=equal,
                        me=(ME in full)))
    return out


def authors_html(authors):
    """First-initial + surname, owner bolded, equal mark as an empty <sup>
    whose glyph comes from CSS so it can be changed in one place."""
    parts = []
    for a in authors:
        name = a["short"]
        if a["me"]:
            name = "<strong>%s</strong>" % name
        if a["equal"]:
            name += '<sup class="eq"></sup>'
        parts.append(name)
    return ", ".join(parts)


def venue_of(f):
    if f.get("venue"):
        return f["venue"], f["venue"]
    full = f.get("journal") or f.get("booktitle") or ""
    for pat, short in VENUE_MAP:
        if re.search(pat, full.lower()):
            return full, short
    return full, full


def links_of(f):
    out = []
    if f.get("arxiv"):
        out.append(("arXiv", "https://arxiv.org/abs/%s" % f["arxiv"]))
    if f.get("html"):
        # `html_label={...}` overrides this, e.g. for a project page.
        out.append((f.get("html_label") or "HTML", f["html"]))
    if f.get("pdf"):
        out.append(("PDF", f["pdf"]))
    if f.get("code"):
        out.append(("Code", f["code"]))
    return out


# ───────────────────────────────────────────────────────────── yaml emitting

def yq(s):
    """Quote a scalar for YAML (double-quoted, escapes preserved)."""
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


def main():
    if not os.path.exists(BIB):
        sys.exit("error: %s not found" % BIB)
    with open(BIB, "r", encoding="utf-8") as fh:
        text = fh.read()
    # strip the Jekyll front-matter fence left over from jekyll-scholar
    text = re.sub(r"\A\s*---\s*\n\s*---\s*\n", "", text)

    rows, warnings = [], []
    for _etype, key, body in split_entries(text):
        f = parse_fields(body)
        if not f.get("title") or not f.get("author"):
            warnings.append("%s: missing title or author - skipped" % key)
            continue
        if re.search(r"\band\s+and\b", f["author"]):
            warnings.append("%s: duplicated 'and' in author list "
                            "(worked around, but worth fixing)" % key)

        authors = parse_authors(f["author"])
        venue_full, venue_short = venue_of(f)
        links = links_of(f)
        if not links:
            warnings.append("%s: no arxiv/html/pdf/code link" % key)

        stem = (f.get("preview") or "").rsplit(".", 1)[0]
        figure = stem + ".jpg" if stem and os.path.exists(
            os.path.join(FIG_DIR, stem + ".jpg")) else None
        paper = stem + ".jpg" if stem and os.path.exists(
            os.path.join(PAPER_DIR, stem + ".jpg")) else None
        if not stem:
            warnings.append("%s: no preview= field, so no thumbnail" % key)

        # Which image to show, from the entry's optional `thumb=` field:
        #   figure  the paper's own figure         (assets/img/pub/)
        #   paper   the generated page-1 preview   (assets/img/paper/)
        #   absent  auto: paper preview if one exists, else the figure
        want = (f.get("thumb") or "auto").strip().lower()
        if want not in ("figure", "paper", "auto"):
            warnings.append("%s: thumb={%s} is not one of figure/paper/auto "
                            "- treating as auto" % (key, want))
            want = "auto"

        if want == "figure" and figure:
            thumb = "figure"
        elif want == "paper" and paper:
            thumb = "paper"
        else:
            if want == "figure" and not figure:
                warnings.append("%s: thumb={figure} but no figure image found" % key)
            if want == "paper" and not paper:
                warnings.append("%s: thumb={paper} but no page-1 preview exists "
                                "(run bin/make_paper_thumbs.py)" % key)
            # fall back to whatever we actually have
            thumb = "paper" if paper else ("figure" if figure else "none")

        rows.append(dict(
            key=key, title=f["title"].replace("{", "").replace("}", ""),
            authors_html=authors_html(authors),
            venue=venue_full, venue_short=venue_short,
            year=int(re.sub(r"\D", "", f.get("year", "0")) or 0),
            award=f.get("award_name") or f.get("award") or None,
            figure=figure, paper=paper, thumb=thumb, links=links,
        ))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# GENERATED FILE - do not edit by hand.\n")
        fh.write("# Source: _bibliography/papers.bib\n")
        fh.write("# Regenerate: python3 bin/bib2yml.py\n")
        for r in rows:
            fh.write("- key: %s\n" % yq(r["key"]))
            fh.write("  title: %s\n" % yq(r["title"]))
            fh.write("  authors_html: %s\n" % yq(r["authors_html"]))
            fh.write("  venue: %s\n" % yq(r["venue"]))
            fh.write("  venue_short: %s\n" % yq(r["venue_short"]))
            fh.write("  year: %d\n" % r["year"])
            fh.write("  award: %s\n" % (yq(r["award"]) if r["award"] else "null"))
            fh.write("  thumb: %s\n" % yq(r["thumb"]))
            fh.write("  figure: %s\n" % (yq(r["figure"]) if r["figure"] else "null"))
            fh.write("  paper: %s\n" % (yq(r["paper"]) if r["paper"] else "null"))
            fh.write("  links:\n")
            for label, url in r["links"]:
                fh.write("    - label: %s\n      url: %s\n" % (yq(label), yq(url)))

    # cross-check the hand-maintained homepage order
    sel_path = os.path.join(ROOT, "_data", "selected.yml")
    if os.path.exists(sel_path):
        keys = {r["key"] for r in rows}
        listed = re.findall(r"^\s*-\s*([A-Za-z0-9_:.-]+)\s*$",
                            open(sel_path).read(), re.M)
        for k in listed:
            if k not in keys:
                warnings.append("_data/selected.yml lists '%s', "
                                "which is not in papers.bib" % k)

    print("wrote %s (%d publications)" % (os.path.relpath(OUT, ROOT), len(rows)))
    n_paper = sum(1 for r in rows if r["thumb"] == "paper")
    print("  thumbnails: %d paper preview, %d figure, %d none"
          % (n_paper, sum(1 for r in rows if r["thumb"] == "figure"),
             sum(1 for r in rows if r["thumb"] == "none")))
    for w in warnings:
        print("  ! %s" % w)


if __name__ == "__main__":
    main()
