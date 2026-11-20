# -*- coding: utf-8 -*-
"""Короткий вертикальный ролик (5 с) через LLM Mart → videos/dayN.mp4

  python gen_video.py --day 8
  python gen_video.py --text "..." --out videos/test.mp4

API: POST /videos → опрос GET /videos/{id} до completed → GET /videos/{id}/content.
Деньги списываются только когда ролик готов (status completed).
"""
import argparse
import json
import os
import time

from factory_common import HERE, die, llm, load_config, log_spend, now_msk, path_in, short_error


def prompt_for_day(day):
    meta = os.path.join(HERE, "posts", "day%d.json" % day)
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            m = json.load(f)
        if m.get("video_prompt"):
            return m["video_prompt"]
        if m.get("image_prompt"):
            return m["image_prompt"] + " Gentle natural motion, steady camera."
    die("нет posts/day%d.json с video_prompt — сначала write_week.py" % day)


def main():
    ap = argparse.ArgumentParser(description="Ролик 5 с через LLM Mart")
    ap.add_argument("--day", type=int)
    ap.add_argument("--text")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config()
    if not (a.day or a.text):
        die("укажи --day N или --text \"...\"")
    prompt = a.text or prompt_for_day(a.day)
    out = a.out or path_in("videos", "day%s.mp4" % (a.day or now_msk().strftime("%Y%m%d-%H%M")))
    payload = {"model": cfg["video_model"],
               "prompt": prompt + " One single continuous full-frame shot filling the whole frame, no split screen, no collage, no stacked or repeated panels. Photorealistic, no text on screen.",
               "duration": int(cfg["video_seconds"]), "resolution": cfg["video_resolution"],
               "aspect_ratio": cfg["video_aspect_ratio"]}
    if cfg.get("video_provider_only"):  # у других площадок LLM Mart нет маршрута /videos (404/402)
        payload["provider"] = {"only": cfg["video_provider_only"]}
    st, hd, raw = llm(cfg, "POST", "/videos", payload)
    if st not in (200, 201, 202):
        die("LLM Mart (видео) ответил %s: %s" % (st, short_error(raw)))
    job = json.loads(raw)
    vid = job["id"]
    print("Задача %s принята, жду готовности (обычно 1–4 мин)…" % vid)
    t0 = time.time()
    while True:
        time.sleep(10)
        st, hd, raw = llm(cfg, "GET", "/videos/%s" % vid)
        job = json.loads(raw) if st == 200 else {"status": "poll_error_%s" % st}
        s = job.get("status")
        if s == "completed":
            break
        if s in ("failed", "cancelled", "expired"):
            die("ролик не получился: %s" % (job.get("error") or s))
        if time.time() - t0 > 1200:
            die("ролик делается дольше 20 минут, id %s — проверь позже" % vid)
    st, hd2, data = llm(cfg, "GET", "/videos/%s/content" % vid, timeout=600)
    if st != 200 or len(data) < 1000:
        die("не скачался ролик: %s" % st)
    with open(out, "wb") as f:
        f.write(data)
    cost = log_spend("видео %sс" % cfg["video_seconds"], cfg["video_model"], hd2 if hd2.get("X-Billing-Cost") else hd,
                     os.path.basename(out))
    print("Готово: %s (%d КБ, %s с) · списано: %s ₽" % (out, len(data) // 1024,
                                                       job.get("seconds") or job.get("duration") or "?", cost or "см. кабинет"))


if __name__ == "__main__":
    main()
