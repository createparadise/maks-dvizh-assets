# -*- coding: utf-8 -*-
"""7 постов следующей недели по scenarios-30.md + persona.md (папка neuroblog) → posts/dayN.txt

  python write_week.py            следующие 7 дней плана (номер дня хранится в state.json)
  python write_week.py --start 8  начать с дня 8

Каждый пост заканчивается призывом «Напиши ТЕЛО в сообщения группы» (cta_text из config.json).
Ссылки и промокода в публичных постах НЕТ — их получает в личку тот, кто написал ТЕЛО (reply_telo.py).
Тексты можно поправить руками в posts/dayN.txt до публикации.
"""
import argparse
import json
import os
import re

from factory_common import HERE, die, llm, load_config, load_state, log_spend, path_in, save_state, short_error


def read_src(cfg, name, required):
    for d in (os.path.join(HERE, cfg["neuroblog_dir"]), HERE):
        p = os.path.normpath(os.path.join(d, name))
        if os.path.exists(p):
            with open(p, encoding="utf-8-sig") as f:
                return f.read()
    if required:
        die("не найден %s (ищу в папке neuroblog и рядом со скриптом)" % name)
    return ""


def pick_days(scen, days):
    """Вырезает из scenarios-30.md блоки «День N»; если формат другой — отдаёт файл целиком."""
    parts = re.split(r"(?im)^(?=\s*(?:#+\s*)?(?:\*\*)?\s*(?:день|day)\s*\d+)", scen)
    found = {}
    for p in parts:
        m = re.match(r"(?i)\s*(?:#+\s*)?(?:\*\*)?\s*(?:день|day)\s*(\d+)", p)
        if m:
            found[int(m.group(1))] = p.strip()
    plan_len = max(found) if found else 30
    want = [((d - 1) % plan_len) + 1 for d in days]
    if found and all(w in found for w in want):
        return "\n\n".join(found[w] for w in want), plan_len
    return scen, plan_len


def clean(text):
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)
    text = re.sub(r"(?m)^.*https?://\S+.*$\n?", "", text)  # ссылки ставим только свои
    return text.strip()


def main():
    ap = argparse.ArgumentParser(description="7 постов недели")
    ap.add_argument("--start", type=int)
    a = ap.parse_args()
    cfg = load_config()
    state = load_state()
    start = a.start or state.get("next_day", 1)
    n = int(cfg["posts_per_week"])
    days = list(range(start, start + n))
    persona = read_src(cfg, "persona.md", True)
    scen_all = read_src(cfg, "scenarios-30.md", True)
    channel = read_src(cfg, "channel.md", False)
    scen, plan_len = pick_days(scen_all, days)
    repeat = start > plan_len
    system = ("Ты — автор ВК-сообщества «Макс Движ» (короткие тренировки, энергия, здоровое тело). "
              "Пиши по-русски, живо, от первого лица персонажа, без воды и без медицинских обещаний. "
              "Простой текст для ВКонтакте: без markdown, без звёздочек и решёток, 1–3 эмодзи, абзацы короткие. "
              "Не вставляй никаких ссылок и промокодов — их добавит система.")
    user = (
        "ПЕРСОНАЖ:\n%s\n\nКАНАЛ:\n%s\n\nСЦЕНАРИИ:\n%s\n\n"
        "Напиши %d постов — по одному на дни плана %s%s. Каждый пост 600–1100 знаков: цепляющая первая строка, "
        "польза (конкретное упражнение или приём на 1–10 минут), личная нотка, вывод. "
        "Последней строкой текста — призыв: «%s»\n"
        "Для каждого поста дай image_prompt — АНГЛИЙСКОЕ описание фото к посту (люди, место, действие, свет; "
        "без текста на картинке) и video_prompt — английское описание 5-секундного вертикального ролика (одно действие).\n"
        "Ответ — только JSON: {\"posts\":[{\"day\":N,\"title\":\"...\",\"text\":\"...\",\"image_prompt\":\"...\",\"video_prompt\":\"...\"}]}"
    ) % (persona[:6000], channel[:2000], scen[:14000], n, ", ".join(map(str, days)),
         " (план уже пройден по кругу — дай новый поворот темы, не повторяй формулировки)" if repeat else "",
         cfg["cta_text"])
    payload = {"model": cfg["text_model"], "messages": [{"role": "system", "content": system},
                                                         {"role": "user", "content": user}],
               "temperature": 0.8, "max_tokens": 9000, "response_format": {"type": "json_object"}}
    st, hd, raw = llm(cfg, "POST", "/chat/completions", payload, timeout=600)
    if st == 400:  # модель/площадка не знает json_object — просим JSON словами
        payload.pop("response_format")
        st, hd, raw = llm(cfg, "POST", "/chat/completions", payload, timeout=600)
    if st != 200:
        die("LLM Mart (текст) ответил %s: %s" % (st, short_error(raw)))
    resp = json.loads(raw)
    content = resp["choices"][0]["message"].get("content") or ""
    m = re.search(r"\{.*\}", content, re.S)
    try:
        posts = json.loads(m.group(0))["posts"]
    except Exception:
        die("модель вернула не JSON, повтори запуск. Начало ответа: %s" % content[:300])
    cost = log_spend("посты недели", cfg["text_model"], hd, "дни %d–%d" % (days[0], days[-1]))
    tail = cfg["cta_text"]
    for d, p in zip(days, posts):
        body = clean(p.get("text", ""))
        body = "\n".join(l for l in body.splitlines() if "ТЕЛО" not in l).strip()
        with open(path_in("posts", "day%d.txt" % d), "w", encoding="utf-8") as f:
            f.write(body + "\n\n" + tail + "\n")
        with open(path_in("posts", "day%d.json" % d), "w", encoding="utf-8") as f:
            json.dump({"day": d, "title": p.get("title", ""), "image_prompt": p.get("image_prompt", ""),
                       "video_prompt": p.get("video_prompt", "")}, f, ensure_ascii=False, indent=2)
        print("posts/day%d.txt — %s" % (d, p.get("title", "")))
    state["next_day"] = days[0] + len(posts[:n])
    save_state(state)
    u = resp.get("usage", {})
    print("Готово: %d постов · токены %s/%s · списано: %s ₽" % (
        len(posts[:n]), u.get("prompt_tokens"), u.get("completion_tokens"), cost or "см. кабинет"))


if __name__ == "__main__":
    main()
