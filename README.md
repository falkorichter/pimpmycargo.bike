# pimpmycargo.bike

Self-hosted archive of the former Instagram (@pimpmycargo.bike) and Tumblr (pimpmycargobike) accounts,
rendered as an Instagram-style Jekyll site.

## Run locally

```sh
bundle install            # Ruby 3.1.2, see .ruby-version
bundle exec jekyll serve  # http://localhost:4000
```

## New posts

Add a file to `_posts/` named `YYYY-MM-DD-some-slug.md`:

```yaml
---
layout: post
title: "Short title"
date: 2026-11-09 12:00:00 +0100
source: pimpmycargo.bike
thumb: /assets/thumbs/my-photo.jpg     # square-cropped in the grid
media:
  - src: /assets/media/my-photo.jpg
  - src: /assets/media/poster.jpg
    video: /assets/media/clip.mp4
youtube: [GYViDK3GNEM]                  # optional
tags: [urbanarrow]
---
<p>Caption text…</p>
```

## Re-importing

`_import/` (git-ignored) holds the raw exports pulled from Instagram's and Tumblr's web APIs.
`python3 tools/import.py` regenerates every `*-ig-*` / `*-tumblr-*` post, copies the media into
`assets/media/` and creates grid thumbnails in `assets/thumbs/` (uses macOS `sips`).
