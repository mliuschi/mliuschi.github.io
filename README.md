# mliuschi.github.io

Personal academic site. Plain Jekyll with **no plugins**, built natively by
GitHub Pages — so publishing is just `git push`, with no CI to break.

## Everyday edits

| To change | Edit |
|---|---|
| Short bio (homepage) | `index.md` (markdown, below the front matter) |
| Long bio (`/about/`) | `about.md` |
| News | `_data/news.yml` — add a block at the top |
| Publications | `_data/publications.yml` |
| Which papers are on the homepage, and their order | `_data/selected.yml` (list of `id`s) |
| Honors & awards | `_data/awards.yml` — `featured: true` puts one on the homepage |
| Name, role, affiliation, email, social links | `_config.yml` |
| CV | replace `assets/pdf/Miguel_Liu_Schiaffini_CV.pdf`; the link path is `cv_path` in `_config.yml` |
| Colours, fonts, spacing | `assets/css/site.css` (`:root` at the top) |

Then commit and push. The site is live in about 30 seconds.

## Adding a publication

1. Add an entry to `_data/publications.yml`:

   ```yaml
   - id: mykey
     title: Some Paper Title
     authors: M. Liu-Schiaffini*, S. Coauthor*, A. Third
     venue: ICML
     year: 2026
     award: Spotlight            # optional
     thumb: figure               # optional: figure | paper
     links:
       arxiv: 2601.01234         # bare id
       html: https://...         # published version
       pdf: https://...
       code: https://github.com/...
       project: https://...
   ```

   Write author initials yourself. A trailing `*` marks equal contribution and
   renders as ✳ with a legend on the publications page; your own name is bolded
   automatically (`author_short` in `_config.yml`). Links render in a fixed
   order with fixed labels.

   `id` is the reference handle used by `_data/selected.yml`, and also names both
   thumbnails: `assets/img/pub/<id>.jpg` and `assets/img/paper/<id>.jpg`.

2. Add the `id` to `_data/selected.yml` if it belongs on the homepage.

3. Build its thumbnail:

   ```bash
   python3 bin/prepare.py
   ```

Text-only changes — titles, authors, venues, links, news, awards, ordering —
need **no command at all.** Jekyll reads these files directly, so the preview
updates as soon as you save.

## bin/prepare.py

The only script. It builds every generated image and checks the content files:

```bash
python3 bin/prepare.py           # do only the missing work (usually instant)
python3 bin/prepare.py --force   # rebuild every image
python3 bin/prepare.py --check   # report problems, write nothing
```

It generates the circular avatar from `assets/img/miguel.jpeg`, the figure
thumbnails from `assets/img/publication_preview/`, and the page-1 paper previews
by downloading each arXiv PDF and rendering it. Downloaded PDFs are deleted
afterwards (`--keep-pdfs` to keep them).

It also warns about dangling ids in `selected.yml`, duplicate ids, entries with
no image, and orphaned images left behind by a deleted publication.

Two papers have no open-access PDF and so use their figure instead: the IEEE
TGRS ice paper (paywalled) and the ICML workshop paper (OpenReview blocks
automated download). Both are recorded in `NO_PDF` in the script. If a paper has
an open preprint that isn't in its `arxiv` field, add it to `PDF_OVERRIDES`.

## Local preview

```bash
docker compose up
```

Then open <http://localhost:8080>. Live-reloads on save. The container installs
the same `github-pages` gem GitHub itself runs, so preview matches production.

Nothing needs to be installed on the host — no Ruby, no Node.

## Design knobs

All in `assets/css/site.css`, in the `:root` block at the very top:

| Want to change | Variable |
|---|---|
| Accent colour (links, pills, hover glow) | `--accent`, and `--wash` / `--glow` (tinted versions of it) |
| Page background | `--bg` |
| Text colours | `--ink` (headings), `--soft` (body), `--muted` (dates, authors) |
| Hairline colours | `--rule`, `--rule-2` |
| Equal-contribution glyph | `--eq` — currently `"\2733"` (✳). Try `"*"`, `"\2020"` (†), `"\2727"` (✧), `"\25C7"` (◇) |

Other layout values, further down the same file:

- Page width — `.wrap { max-width: 58rem }`
- Body-text width — body text now runs the full page width. To pull it back in,
  add `max-width: 46rem` to `.prose` (and `.ledger .what` for news)
- Thumbnail size — `.pub { grid-template-columns: 12rem 1fr }`

## Figure vs. paper-preview thumbnail

Each publication shows one of two images, controlled by an optional `thumb`
field in `_data/publications.yml`:

| `thumb` | Shows |
|---|---|
| `figure` | The paper's own figure, from `assets/img/pub/<id>.jpg` |
| `paper` | The generated page-1 preview, `assets/img/paper/<id>.jpg` |
| *omitted* | Automatic — the paper preview if one exists, otherwise the figure |

```yaml
- id: mno
  ...
  thumb: figure        # this figure reads well small, so keep it
```

Takes effect immediately — no command needed, since Jekyll checks which images
exist on disk at build time.

Rule of thumb: use `figure` when the figure is one strong visual — a single
field, a clean schematic, a logo. Dense multi-panel figures turn to mush at
150px, so those are better off as the paper preview. Two entries are currently
pinned to `figure` (`mno`, `neuraloperator_logo`).

If you ask for something unavailable — `thumb: paper` on a paper with no
generated preview — the page falls back to whatever image does exist rather than
rendering an empty box, and `bin/prepare.py --check` tells you about it.

## How it fits together

There is no build step for content. Every page renders straight from a file you
edit:

```
_data/publications.yml  ──┐
_data/selected.yml      ──┤
_data/news.yml          ──┼──>  Jekyll  ──>  the site
_data/awards.yml        ──┤
index.md / about.md     ──┘
```

Images are the only generated artefacts, and they are committed, so the build
never touches the network. `bin/prepare.py` makes them.

Pages: `/` (home), `/about/`, `/news/`, `/publications/`, and `/honors/` — which
is deliberately not in the nav, reached from the homepage arrow.

## Deployment

GitHub Pages builds `master` natively. Repo **Settings → Pages** must be set to
*Deploy from a branch* → **`master`**, folder **`/ (root)`**.

There are no GitHub Actions workflows, and the `gh-pages` branch is no longer
used.
