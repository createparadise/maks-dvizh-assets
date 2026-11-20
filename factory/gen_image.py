# -*- coding: utf-8 -*-
"""Картинка к посту через LLM Mart → images/dayN.png

  python gen_image.py --day 8            картинка к posts/day8 (промпт из day8.json или текст поста)
  python gen_image.py --today            картинка дня: пост, который выходит сегодня
  python gen_image.py --text "..." --out images/test.png   свой промпт
"""
import argparse
import base64
import json
import os

from factory_common import HERE, die, http, llm, load_config, load_state, log_spend, now_msk, path_in, short_error

STYLE = ("Photorealistic lifestyle photo, natural light, real people, authentic skin texture, "
         "35mm lens, shallow depth of field, clean uncluttered composition, vertical 4:5 frame. "
         "No text, no letters, no captions, no logos, no watermark.")


def prompt_for_day(day):
    meta = os.path.join(HERE, "posts", "day%d.json" % day)
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            m = json.load(f)
        if m.get("image_prompt"):
            return m["image_prompt"]
    txt = os.path.join(HERE, "posts", "day%d.txt" % day)
    if os.path.exists(txt):
        with open(txt, encoding="utf-8-sig") as f:
            return "A photo that illustrates this social media post (written in Russian): " + f.read()[:700]
    die("нет поста posts/day%d.txt — сначала запусти write_week.py" % day)


def today_day():
    """День, чей пост выходит сегодня по МСК; иначе первый пост без картинки."""
    st = load_state()
    today = now_msk().strftime("%Y-%m-%d")
    for d, rec in sorted(st.get("scheduled", {}).items(), key=lambda x: int(x[0])):
        if rec.get("when_msk", "").startswith(today):
            return int(d)
    posts = os.path.join(HERE, "posts")
    days = sorted(int(n[3:-4]) for n in os.listdir(posts) if n.startswith("day") and n.endswith(".txt")) if os.path.isdir(posts) else []
    for d in days:
        if not any(os.path.exists(os.path.join(HERE, "images", "day%d.%s" % (d, e))) for e in ("png", "jpg", "webp")):
            return d
    die("нет постов без картинки")


def sniff(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return "png"


def generate(cfg, prompt, out_path):
    payload = {
        "model": cfg["image_model"],
        "prompt": prompt.strip() + "\n" + STYLE,
        "n": 1,
        "aspect_ratio": cfg["image_aspect_ratio"],
        "resolution": cfg["image_resolution"],
        "output_format": "png",
    }
    if cfg.get("provider_only"):
        payload["provider"] = {"only": cfg["provider_only"]}
    st, hd, raw = llm(cfg, "POST", "/images/generations", payload)
    if st == 400 and "provider" in payload and "provider" in short_error(raw):
        payload.pop("provider")  # площадка недоступна — пусть роутер выберет сам
        st, hd, raw = llm(cfg, "POST", "/images/generations", payload)
    if st != 200:
        die("LLM Mart (картинка) ответил %s: %s" % (st, short_error(raw)))
    data = json.loads(raw)
    item = (data.get("data") or [{}])[0]
    if item.get("b64_json"):
        img = base64.b64decode(item["b64_json"])
    elif item.get("url", "").startswith("data:"):
        img = base64.b64decode(item["url"].split(",", 1)[1])
    elif item.get("url"):
        _, _, img = http("GET", item["url"])
    else:
        die("в ответе нет картинки: %s" % str(data)[:300])
    ext = sniff(img)
    base, _ = os.path.splitext(out_path)
    out_path = base + "." + ext
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(img)
    cost = log_spend("картинка", cfg["image_model"], hd, os.path.basename(out_path))
    print("Готово: %s (%d КБ) · списано: %s ₽ · площадка: %s" % (
        out_path, len(img) // 1024, cost or "см. кабинет", hd.get("X-LLMMart-Host", "?")))
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Картинка к посту через LLM Mart")
    ap.add_argument("--day", type=int)
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--text")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config()
    if a.text:
        prompt, day = a.text, None
    else:
        day = a.day or (today_day() if a.today else None)
        if not day:
            die("укажи --day N, --today или --text \"...\"")
        prompt = prompt_for_day(day)
        if a.today and any(os.path.exists(os.path.join(HERE, "images", "day%d.%s" % (day, e))) for e in ("png", "jpg", "webp")):
            print("Картинка к day%d уже есть — пропускаю" % day)
            return
    out = a.out or path_in("images", "day%s.png" % (day if day else now_msk().strftime("%Y%m%d-%H%M")))
    generate(cfg, prompt, out)


if __name__ == "__main__":
    main()
