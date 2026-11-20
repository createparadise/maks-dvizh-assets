# -*- coding: utf-8 -*-
"""Автоответ на слово «ТЕЛО» в сообщениях группы. Запускается планировщиком каждые 10 минут (не висит в памяти).

  python reply_telo.py            ответить всем новым «ТЕЛО»
  python reply_telo.py --dry-run  только показать, кому ушёл бы ответ

Берёт НЕОТВЕЧЕННЫЕ диалоги (messages.getConversations filter=unanswered). Если последнее входящее
содержит «тело» (регистр, ё, пробелы, знаки — не важны) — шлёт текст из telo_reply.txt.
Остальные неотвеченные не трогает — их читает Дима. Ответ сам снимает «неотвеченное»,
поэтому после выключенного ПК бот догонит всех при следующем запуске. Лог: logs/telo.log.
"""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.parse

from factory_common import HERE, http, load_config, now_msk, path_in

VK_API = "https://api.vk.com/method/"
VK_V = "5.199"
LOOKALIKE = str.maketrans("aeopcxkmhbty", "аеорсхкмнвту")  # латиница, похожая на кириллицу


def log(msg):
    line = "%s %s" % (now_msk().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    with open(path_in("logs", "telo.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_telo(text):
    t = (text or "").lower().replace("ё", "е").translate(LOOKALIKE)
    return "тело" in re.sub(r"[^а-я]", "", t)


def vk(token, method, params):
    params = dict(params, v=VK_V, access_token=token)
    for _ in range(3):
        _, _, raw = http("POST", VK_API + method, {"Content-Type": "application/x-www-form-urlencoded"},
                         urllib.parse.urlencode(params).encode("utf-8"), timeout=60)
        res = json.loads(raw)
        if res.get("error", {}).get("error_code") == 6:
            time.sleep(1.2)
            continue
        return res
    return res


def main():
    ap = argparse.ArgumentParser(description="Автоответ на ТЕЛО")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    token = cfg.get("vk_group_token", "")
    if not token:
        log("ОШИБКА: нет токена сообщества — впиши vk_group_token в config.json (права «Сообщения»)")
        raise SystemExit(1)
    reply_path = os.path.join(HERE, "telo_reply.txt")
    if not os.path.exists(reply_path):
        log("ОШИБКА: нет файла telo_reply.txt рядом со скриптом")
        raise SystemExit(1)
    with open(reply_path, encoding="utf-8-sig") as f:
        reply = f.read().strip()
    if not reply:
        log("ОШИБКА: telo_reply.txt пустой")
        raise SystemExit(1)
    group_id = abs(int(cfg["group_id"]))
    items, offset = [], 0
    while True:
        res = vk(token, "messages.getConversations",
                 {"group_id": group_id, "filter": "unanswered", "count": 200, "offset": offset})
        if "error" in res:
            e = res["error"]
            hint = {5: "токен неверный или отозван", 15: "включи «Сообщения сообщества» и право «Сообщения» у токена",
                    27: "нужен токен СООБЩЕСТВА, не пользователя", 917: "у токена нет доступа к беседам"}
            log("ОШИБКА VK %s: %s (%s)" % (e.get("error_code"), e.get("error_msg"), hint.get(e.get("error_code"), "")))
            raise SystemExit(1)
        batch = res["response"].get("items", [])
        items += batch
        offset += len(batch)
        if len(batch) < 200 or offset >= res["response"].get("count", 0):
            break
    sent = 0
    for it in items:
        peer = it["conversation"]["peer"]
        last = it.get("last_message", {})
        if peer.get("type") != "user" or last.get("out") == 1 or not is_telo(last.get("text")):
            continue
        uid = peer["id"]
        if a.dry_run:
            log("[проверка] ответил бы id%s на «%s»" % (uid, (last.get("text") or "")[:40]))
            continue
        rid = int(hashlib.sha1(("%s:%s" % (uid, last.get("id") or last.get("conversation_message_id"))).encode()).hexdigest()[:8], 16) & 0x7FFFFFFF
        r = vk(token, "messages.send", {"group_id": group_id, "peer_id": uid, "random_id": rid, "message": reply})
        if "error" in r:
            log("ошибка ответа id%s: %s %s" % (uid, r["error"].get("error_code"), r["error"].get("error_msg")))
        else:
            sent += 1
            log("ответил id%s на «%s»" % (uid, (last.get("text") or "")[:40]))
        time.sleep(0.35)
    log("проверено неотвеченных: %d, ответов «ТЕЛО»: %d" % (len(items), sent))


if __name__ == "__main__":
    main()
