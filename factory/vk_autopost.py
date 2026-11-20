# -*- coding: utf-8 -*-
"""Ставит посты posts/dayN.txt в ОТЛОЖЕННЫЕ на стене сообщества (VK API wall.post, токен сообщества).

  python vk_autopost.py             поставить все новые посты (по одному в день, 08:00 МСК)
  python vk_autopost.py --dry-run   только показать, что уйдёт в VK (без токена тоже работает)

Токен сообщества умеет wall.post на стену своего сообщества, но НЕ умеет загружать фото на стену,
читать и править посты. Поэтому посты уходят текстом; свои картинки (images/) — вручную или агентом через браузер.
В публичных постах НЕТ ссылки и промокода — только призыв «Напиши ТЕЛО в сообщения группы»;
ссылку с кодом получает в личку тот, кто написал ТЕЛО (reply_telo.py).
"""
import argparse
import datetime
import hashlib
import json
import os
import time
import urllib.parse

from factory_common import HERE, MSK, die, http, load_config, load_state, now_msk, save_state

VK_API = "https://api.vk.com/method/"
VK_V = "5.199"


def vk(cfg, method, params, dry):
    params = dict(params, v=VK_V)
    if dry:
        return {"response": {"post_id": 0}}
    params["access_token"] = cfg["vk_group_token"]
    for _ in range(3):
        st, _, raw = http("POST", VK_API + method, {"Content-Type": "application/x-www-form-urlencoded"},
                          urllib.parse.urlencode(params).encode("utf-8"), timeout=60)
        res = json.loads(raw)
        if res.get("error", {}).get("error_code") == 6:  # слишком часто — ждём секунду
            time.sleep(1.2)
            continue
        return res
    return res


def ensure_tail(text, cfg):
    """Без ссылок и промокода в публичном посте; в конце — призыв «ТЕЛО»."""
    lines = [l for l in text.strip().splitlines()
             if "lava.top" not in l and cfg["course_url"] not in l and cfg["promo_code"] not in l]
    t = "\n".join(lines).strip()
    if "ТЕЛО" not in t:
        t += "\n\n" + cfg["cta_text"]
    return t


def slots(cfg, state, n):
    hh, mm = (int(x) for x in cfg["post_time_msk"].split(":"))
    now = now_msk()
    first = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if first < now + datetime.timedelta(minutes=30):
        first += datetime.timedelta(days=1)
    last = state.get("last_slot", 0)
    if last:
        after = datetime.datetime.fromtimestamp(last, MSK) + datetime.timedelta(days=1)
        after = after.replace(hour=hh, minute=mm)
        if after > first:
            first = after
    return [first + datetime.timedelta(days=i) for i in range(n)]


def main():
    ap = argparse.ArgumentParser(description="Отложенные посты VK")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    cfg = load_config()
    dry = a.dry_run or not cfg.get("vk_group_token")
    if dry and not a.dry_run:
        print("Токена сообщества нет в config.json (vk_group_token) — СУХОЙ ПРОГОН, в VK ничего не уйдёт.\n")
    state = load_state()
    posts_dir = os.path.join(HERE, "posts")
    days = sorted(int(n[3:-4]) for n in os.listdir(posts_dir)
                  if n.startswith("day") and n.endswith(".txt")) if os.path.isdir(posts_dir) else []
    days = [d for d in days if str(d) not in state["scheduled"]][: a.limit or cfg["posts_per_week"]]
    if not days:
        print("Новых постов нет (posts/dayN.txt). Сначала запусти write_week.py")
        return
    owner = -abs(int(cfg["group_id"]))
    for day, when in zip(days, slots(cfg, state, len(days))):
        with open(os.path.join(posts_dir, "day%d.txt" % day), encoding="utf-8-sig") as f:
            text = ensure_tail(f.read(), cfg)
        ts = int(when.timestamp())
        params = {"owner_id": owner, "from_group": 1, "message": text, "publish_date": ts,
                  "guid": hashlib.sha1(("%s|%s|%s" % (owner, ts, text)).encode("utf-8")).hexdigest()[:32]}
        print("— day%d → %s МСК (publish_date=%d)" % (day, when.strftime("%a %d.%m %H:%M"), ts))
        if dry:
            shown = {k: v for k, v in params.items() if k != "message"}
            print("  wall.post %s v=%s" % (json.dumps(shown, ensure_ascii=False), VK_V))
            print("  текст (%d симв.):\n    %s\n" % (len(text), text.replace("\n", "\n    ")))
            continue
        res = vk(cfg, "wall.post", params, dry)
        err = res.get("error")
        if err:
            hint = {5: "токен неверный или отозван", 214: "нет права «Стена» у токена или owner_id без минуса",
                    15: "доступ запрещён", 27: "метод недоступен токену сообщества", 9: "флуд-контроль, повтори позже"}
            die("VK %s: %s (%s)" % (err.get("error_code"), err.get("error_msg"), hint.get(err.get("error_code"), "")))
        post_id = res["response"]["post_id"]
        state["scheduled"][str(day)] = {"post_id": post_id, "publish_date": ts, "when_msk": when.strftime("%Y-%m-%d %H:%M")}
        state["last_slot"] = max(state.get("last_slot", 0), ts)
        save_state(state)
        print("  ✓ в отложенных: https://vk.com/wall%d_%d" % (owner, post_id))
        time.sleep(0.4)


if __name__ == "__main__":
    main()
