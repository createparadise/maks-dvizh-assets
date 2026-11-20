# -*- coding: utf-8 -*-
"""Общие функции контент-фабрики «Макс Движ». Только стандартная библиотека Python 3."""
import csv
import datetime
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MSK = datetime.timezone(datetime.timedelta(hours=3))

DEFAULTS = {
    "llmmart_key": "",
    "llmmart_base_url": "https://llmmart.ru/api/v1",
    "vk_group_token": "",
    "group_id": 243312492,
    "promo_code": "DVIZH",
    "course_url": "https://app.lava.top/products/de794317-9fc1-4ea6-ada5-e03861dd6af7/79e960db-58cd-429d-8b36-fb3402cc0e43?currency=RUB&promoCode=DVIZH",
    "ref_text": "Программа \"Идеальное тело за 10 минут\" — по коду {promo_code} скидка 10%: {course_url}",
    "cta_text": "👉 Напиши ТЕЛО в сообщения группы — пришлю программу на 3 дня.",
    "text_model": "moonshotai/kimi-k3.1-pro",
    "image_model": "black-forest-labs/flux-3-image-klein",
    "image_aspect_ratio": "4:5",
    "image_resolution": "1K",
    "video_model": "x-ai/grok-imagine-video-1.5-lite",
    "video_seconds": 5,
    "video_resolution": "720p",
    "video_aspect_ratio": "9:16",
    "provider_only": [],
    "video_provider_only": ["ru_openrouter"],
    "post_time_msk": "08:00",
    "posts_per_week": 7,
    "neuroblog_dir": "..",
}


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


def load_config():
    """config.json рядом со скриптами. Переменные окружения LLMMART_KEY / VK_GROUP_TOKEN сильнее файла."""
    cfg = dict(DEFAULTS)
    path = os.path.join(HERE, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            cfg.update(json.load(f))
    if os.environ.get("LLMMART_KEY"):
        cfg["llmmart_key"] = os.environ["LLMMART_KEY"].strip()
    if os.environ.get("VK_GROUP_TOKEN"):
        cfg["vk_group_token"] = os.environ["VK_GROUP_TOKEN"].strip()
    return cfg


def ref_line(cfg):
    return cfg["ref_text"].format(promo_code=cfg["promo_code"], course_url=cfg["course_url"])


def now_msk():
    return datetime.datetime.now(MSK)


def path_in(*parts):
    p = os.path.join(HERE, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def load_state():
    p = os.path.join(HERE, "state.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"next_day": 1, "scheduled": {}, "last_slot": 0}


def save_state(state):
    with open(os.path.join(HERE, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _ssl_context():
    ctx = ssl.create_default_context()
    try:
        import certifi  # если установлен — добавим его корневые сертификаты
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def http(method, url, headers=None, body=None, timeout=300):
    """Возвращает (код, заголовки, байты). Ошибки HTTP не бросает."""
    data = None
    h = {"User-Agent": "maks-dvizh-factory/1.0"}
    h.update(headers or {})
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        elif isinstance(body, bytes):
            data = body
        else:
            data = str(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except urllib.error.URLError as e:
        die("нет связи с %s: %s" % (url.split("/")[2], e.reason))


def llm(cfg, method, path, payload=None, timeout=300):
    key = cfg.get("llmmart_key", "")
    if not key:
        die("нет ключа LLM Mart — впиши llmmart_key в config.json")
    url = cfg["llmmart_base_url"].rstrip("/") + path
    return http(method, url, {"Authorization": "Bearer " + key}, payload, timeout)


def log_spend(what, model, headers, note=""):
    """Пишет трату в logs/spend.csv. Сумма в рублях — из заголовка X-Billing-Cost LLM Mart."""
    cost = headers.get("X-Billing-Cost", "") if headers is not None else ""
    host = headers.get("X-LLMMart-Host", "") if headers is not None else ""
    p = path_in("logs", "spend.csv")
    new = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if new:
            w.writerow(["время МСК", "что", "модель", "₽ (X-Billing-Cost)", "площадка", "заметка"])
        w.writerow([now_msk().strftime("%Y-%m-%d %H:%M"), what, model, cost, host, note])
    return cost


def short_error(raw):
    try:
        j = json.loads(raw)
        e = j.get("error", j)
        return e.get("message") if isinstance(e, dict) else str(e)
    except Exception:
        return raw[:300].decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)[:300]
