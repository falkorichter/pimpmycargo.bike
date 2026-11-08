#!/usr/bin/env python3
"""Convert the raw Instagram + Tumblr exports in _import/ into Jekyll posts.

Usage: python3 tools/import.py            (run from the repo root)

Reads:
  _import/instagram/posts_raw.json, _import/instagram/media/*
  _import/tumblr/posts_raw.json
Writes:
  _posts/*.md
  assets/media/instagram/*, assets/media/tumblr/*   (full size)
  assets/thumbs/*                                    (640px grid thumbnails, via macOS `sips`)
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMP = os.path.join(ROOT, "_import")
POSTS = os.path.join(ROOT, "_posts")
MEDIA = os.path.join(ROOT, "assets", "media")
THUMBS = os.path.join(ROOT, "assets", "thumbs")
IG_USER = "pimpmycargo.bike"


def yaml_str(s):
    return json.dumps(s or "", ensure_ascii=False)


def make_thumb(src, name):
    """Create a 640px-wide JPEG thumbnail (cached)."""
    os.makedirs(THUMBS, exist_ok=True)
    dest = os.path.join(THUMBS, os.path.splitext(name)[0] + ".jpg")
    if not os.path.exists(dest):
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "640", src, "--out", dest],
                       check=False, capture_output=True)
    return "/assets/thumbs/" + os.path.basename(dest) if os.path.exists(dest) else None


def write_post(date, slug, fm, body):
    os.makedirs(POSTS, exist_ok=True)
    fname = f"{date:%Y-%m-%d}-{slug}.md"
    lines = ["---", "layout: post"]
    for k, v in fm.items():
        if v is None or v == [] or v == "":
            continue
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        lines.append(f"  {'- ' if first else '  '}{ik}: {yaml_str(iv) if isinstance(iv, str) else json.dumps(iv)}")
                        first = False
                else:
                    lines.append(f"  - {yaml_str(item)}")
        elif isinstance(v, str):
            lines.append(f"{k}: {yaml_str(v)}")
        else:
            lines.append(f"{k}: {json.dumps(v)}")
    lines.append("---")
    with open(os.path.join(POSTS, fname), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n" + body.strip() + "\n")


# ---------------------------------------------------------------- Instagram

def ig_caption_html(text):
    text = html.escape(text or "")
    text = re.sub(r"@([A-Za-z0-9_.]*[A-Za-z0-9_])",
                  r'<a href="https://www.instagram.com/\1/">@\1</a>', text)
    text = re.sub(r"(?<![\w&])#(\w+)", r'<span class="hashtag">#\1</span>', text)
    paras = [p.replace("\n", "<br>\n") for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(f"<p>{p}</p>" for p in paras)


def import_instagram():
    raw = os.path.join(IMP, "instagram", "posts_raw.json")
    if not os.path.exists(raw):
        print("no instagram export, skipping"); return 0
    posts = json.load(open(raw, encoding="utf-8"))
    src_dir = os.path.join(IMP, "instagram", "media")
    dst_dir = os.path.join(MEDIA, "instagram")
    os.makedirs(dst_dir, exist_ok=True)
    missing = 0
    for n in posts:
        code = n["code"]
        date = datetime.fromtimestamp(n["taken_at"], tz=timezone.utc)
        items = n.get("carousel_media") or [n]
        media = []
        for i, it in enumerate(items):
            img, vid = f"{code}_{i}.jpg", f"{code}_{i}.mp4"
            entry = {}
            if os.path.exists(os.path.join(src_dir, img)):
                shutil.copy2(os.path.join(src_dir, img), os.path.join(dst_dir, img))
                entry["src"] = f"/assets/media/instagram/{img}"
            else:
                missing += 1
            if os.path.exists(os.path.join(src_dir, vid)):
                shutil.copy2(os.path.join(src_dir, vid), os.path.join(dst_dir, vid))
                entry["video"] = f"/assets/media/instagram/{vid}"
            if entry:
                alt = it.get("accessibility_caption")
                if alt:
                    entry["alt"] = alt
                media.append(entry)
        caption = (n.get("caption") or {}).get("text", "")
        first_img = next((m["src"] for m in media if "src" in m), None)
        thumb = make_thumb(os.path.join(ROOT, first_img.lstrip("/")), first_img.split("/")[-1]) if first_img else None
        title = (caption.split("\n")[0][:80] if caption else f"Instagram {code}")
        loc = (n.get("location") or {}).get("name")
        fm = {
            "title": title,
            "date": date.strftime("%Y-%m-%d %H:%M:%S +0000"),
            "source": "instagram",
            "original_url": f"https://www.instagram.com/p/{code}/",
            "location": loc,
            "thumb": thumb,
            "is_video": any("video" in m for m in media),
            "media": media,
            "tags": sorted(set(re.findall(r"(?<![\w&])#(\w+)", caption))),
        }
        write_post(date, f"ig-{code}", fm, ig_caption_html(caption))
    print(f"instagram: {len(posts)} posts, {missing} missing media items")
    return len(posts)


# ---------------------------------------------------------------- Tumblr

def apply_formatting(text, fmts):
    """Render an NPF text block's inline formatting (bold/italic/link) to HTML."""
    if not fmts:
        return html.escape(text)
    opens, closes = {}, {}
    for f in fmts:
        t = f.get("type")
        if t == "bold":
            o, c = "<strong>", "</strong>"
        elif t == "italic":
            o, c = "<em>", "</em>"
        elif t == "strikethrough":
            o, c = "<s>", "</s>"
        elif t == "link":
            o, c = f'<a href="{html.escape(f.get("url", ""))}">', "</a>"
        elif t == "mention":
            o, c = f'<a href="{html.escape((f.get("blog") or {}).get("url", ""))}">', "</a>"
        else:
            continue
        opens.setdefault(f["start"], []).append(o)
        closes.setdefault(f["end"], []).insert(0, c)
    out = []
    for i, ch in enumerate(text + "\0"):
        out.extend(closes.get(i, []))
        out.extend(opens.get(i, []))
        if ch != "\0":
            out.append(html.escape(ch))
    return "".join(out)


def tumblr_download(url, name):
    dst_dir = os.path.join(MEDIA, "tumblr")
    os.makedirs(dst_dir, exist_ok=True)
    dest = os.path.join(dst_dir, name)
    if not os.path.exists(dest):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/jpeg,image/*"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                f.write(r.read())
        except Exception as e:  # noqa: BLE001
            print("  failed", url, e); return None
    return dest


def youtube_id(url):
    m = re.search(r"(?:youtu\.be/|v=|embed/|shorts/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def import_tumblr():
    raw = os.path.join(IMP, "tumblr", "posts_raw.json")
    if not os.path.exists(raw):
        print("no tumblr export, skipping"); return 0
    posts = [p for p in json.load(open(raw, encoding="utf-8")) if p.get("object_type") == "post"]
    for p in posts:
        pid = p["id_string"]
        date = datetime.fromtimestamp(p["timestamp"], tz=timezone.utc)
        blocks = list(p.get("content") or [])
        for t in p.get("trail") or []:
            blocks += t.get("content") or []
        media, body, embeds = [], [], []
        list_open = None
        for b in blocks:
            typ = b.get("type")
            sub = b.get("subtype")
            if typ == "text" and sub in ("ordered-list-item", "unordered-list-item"):
                tag = "ol" if sub.startswith("ordered") else "ul"
                if list_open != tag:
                    if list_open:
                        body.append(f"</{list_open}>")
                    body.append(f"<{tag}>"); list_open = tag
                body.append(f"<li>{apply_formatting(b.get('text', ''), b.get('formatting'))}</li>")
                continue
            if list_open:
                body.append(f"</{list_open}>"); list_open = None
            if typ == "text":
                txt = apply_formatting(b.get("text", ""), b.get("formatting"))
                if not txt.strip():
                    continue
                tag = {"heading1": "h2", "heading2": "h3", "quote": "blockquote",
                       "indented": "blockquote", "chat": "pre"}.get(sub, "p")
                body.append(f"<{tag}>{txt}</{tag}>")
            elif typ == "image":
                m = (b.get("media") or [{}])[0]
                url = m.get("url")
                if not url:
                    continue
                name = f"{pid}_{len(media)}" + (os.path.splitext(url.split("?")[0])[1].replace(".pnj", ".png").replace(".gifv", ".gif") or ".jpg")
                if tumblr_download(url, name):
                    entry = {"src": f"/assets/media/tumblr/{name}"}
                    if b.get("alt_text"):
                        entry["alt"] = b["alt_text"]
                    media.append(entry)
            elif typ == "video":
                yid = youtube_id(b.get("url"))
                if yid:
                    embeds.append(yid)
                elif (b.get("media") or {}).get("url"):
                    vurl = b["media"]["url"]
                    name = f"{pid}_{len(media)}.mp4"
                    if tumblr_download(vurl, name):
                        media.append({"video": f"/assets/media/tumblr/{name}"})
                elif b.get("url"):
                    body.append(f'<p><a href="{html.escape(b["url"])}">{html.escape(b["url"])}</a></p>')
            elif typ == "link":
                body.append(f'<p class="link-card"><a href="{html.escape(b.get("url", ""))}">'
                            f'{html.escape(b.get("title") or b.get("url", ""))}</a></p>')
        if list_open:
            body.append(f"</{list_open}>")
        # Thumbnail: first image, else YouTube poster
        thumb = None
        if media and "src" in media[0]:
            thumb = make_thumb(os.path.join(ROOT, media[0]["src"].lstrip("/")), media[0]["src"].split("/")[-1])
        elif embeds:
            yt = f"yt_{embeds[0]}.jpg"
            src = tumblr_download(f"https://img.youtube.com/vi/{embeds[0]}/hqdefault.jpg", yt)
            thumb = make_thumb(src, yt) if src else None
        summary = (p.get("summary") or "").strip().split("\n")[0][:80]
        fm = {
            "title": summary or f"Tumblr {pid}",
            "date": date.strftime("%Y-%m-%d %H:%M:%S +0000"),
            "source": "tumblr",
            "original_url": p.get("post_url"),
            "thumb": thumb,
            "is_video": bool(embeds) or any("video" in m for m in media),
            "media": media,
            "youtube": embeds,
            "tags": p.get("tags") or [],
        }
        slug = re.sub(r"[^a-z0-9-]", "", (p.get("slug") or "").lower())[:50].strip("-")
        write_post(date, f"tumblr-{pid}" + (f"-{slug}" if slug else ""), fm, "\n".join(body))
    print(f"tumblr: {len(posts)} posts")
    return len(posts)


if __name__ == "__main__":
    if os.path.isdir(POSTS) and "--keep" not in sys.argv:
        for f in os.listdir(POSTS):
            if f.endswith(".md") and ("-ig-" in f or "-tumblr-" in f):
                os.remove(os.path.join(POSTS, f))
    import_tumblr()
    import_instagram()
