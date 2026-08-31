# mliuschi.github.io

Personal academic site. Plain Jekyll with **no plugins**, built natively by
GitHub Pages — so publishing is just `git push`, with no CI to break.

## Everyday edits

| To change | Edit |
|---|---|
| Short bio (homepage) | `index.md` (markdown, below the front matter) |
| Long bio (`/about/`) | `about.md` |
| News | `_data/news.yml` — add a block at the top |
| Publications | `_bibliography/papers.bib` |
| Which papers are on the homepage, and their order | `_data/selected.yml` |
| Name, role, affiliation, email, social links | `_config.yml` |
| CV | replace `assets/pdf/Miguel_Liu_Schiaffini_CV.pdf`; the link path is `cv_path` in `_config.yml` |
| Colours, fonts, spacing | `assets/css/site.css` (`:root` at the top) |

Then commit and push. The site is live in about 30 seconds.

## Adding a publication

1. Paste the BibTeX into `_bibliography/papers.bib`. Useful extra fields:

   ```bibtex
   @article{mykey2026,
     title={...},
     author={Liu-Schiaffini*, Miguel and Coauthor*, Someone},
     journal={International Conference on Machine Learning},
     year={2026},
     arxiv={2601.01234},            % bare id
     code={https://github.com/...},
     html={https://...},            % published version
     pdf={https://...},             % direct PDF
     venue={ICML},                  % short label for the pill (optional)
     award={Spotlight},             % optional
     preview={mykey.png},           % names the thumbnail files
     thumb={figure}                 % or {paper}; omit for automatic
   }
   ```

   A `*` after a surname marks equal contribution and renders as ✳ with a
   legend on the publications page.

2. Generate its page-1 preview thumbnail:

   ```bash
   python3 bin/make_paper_thumbs.py
   ```

3. Regenerate the publication data:

   ```bash
   python3 bin/bib2yml.py
   ```

   (The pre-commit hook does this for you — see below.)

4. Add the citation key to `_data/selected.yml` if it should appear on the homepage.

## Local preview

```bash
docker compose up
```

Then open <http://localhost:8080>. Live-reloads on save. The container installs
the same `github-pages` gem GitHub itself runs, so preview matches production.

Nothing needs to be installed on the host — no Ruby, no Node.

## One-time setup

```bash
bash bin/install-hooks.sh
```

Installs a pre-commit hook that regenerates `_data/publications.yml` whenever
you commit a change to `papers.bib`, so the two cannot drift apart. If the hook
is ever missing (say, a fresh clone), the failure mode is a stale publication
list, not a broken site — `python3 bin/bib2yml.py` fixes it.

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

Each publication shows one of two images, controlled by an optional `thumb=`
field in its BibTeX entry:

| `thumb=` | Shows |
|---|---|
| `figure` | The paper's own figure, from `assets/img/publication_preview/` |
| `paper` | The generated page-1 preview of the PDF |
| *omitted* | Automatic — the paper preview if one exists, otherwise the figure |

```bibtex
@article{li2022learning,
  ...
  preview={mno.png},
  thumb={figure},        % this figure reads well small, so keep it
}
```

Re-run `python3 bin/bib2yml.py` after changing it (or just commit — the hook
does it).

Rule of thumb: use `figure` when the figure is one strong visual — a single
field, a clean schematic, a logo. Dense multi-panel figures turn to mush at
150px, so those are better off as the paper preview. Currently two entries are
pinned to `figure` (`li2022learning`, `kossaifi2024library`); everything else is
automatic.

If you ask for something unavailable — `thumb={paper}` on a paper with no
generated preview, or a typo — the script warns and falls back to whatever image
does exist, rather than rendering an empty box.

## How it fits together

```
_bibliography/papers.bib   source of truth for publications
        │  bin/bib2yml.py  (pre-commit hook)
        ▼
_data/publications.yml     generated, committed — do not hand-edit
        │
        ▼
publications.html / _layouts/home.html   render via _includes/publication.html
```

Images are generated once and committed, so the build never touches the network:

- `bin/make_images.py` — square avatar from `assets/img/miguel.jpeg`, plus
  figure thumbnails from `assets/img/publication_preview/`
- `bin/make_paper_thumbs.py` — page-1 paper previews into `assets/img/paper/`

Two papers have no open-access PDF and therefore keep their figure thumbnail:
the IEEE TGRS ice paper (paywalled) and the ICML workshop paper (OpenReview
blocks automated download). Both are noted in `make_paper_thumbs.py`.

## Deployment

GitHub Pages builds `master` natively. Repo **Settings → Pages** must be set to
*Deploy from a branch* → **`master`**, folder **`/ (root)`**.

There are no GitHub Actions workflows, and the `gh-pages` branch is no longer
used.
