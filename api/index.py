import os
import json
import time
import base64
import hmac
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

# ==============================================================================
#  👻 Phantom VPN — Vercel Serverless Bot + Web Portal + Admin Panel (@zzylx)
# ==============================================================================

BOT_TOKEN = "9017418443:AAGF0_2yQOBIg6wO5-GGa7WvzGvVTJTBClo"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_USERNAMES = ["zzylx"]
SECRET_KEY = os.environ.get("SECRET_KEY", "phantom_vpn_ultra_secret_2026_key")

DEFAULT_SUB_URL = "https://gist.githubusercontent.com/FlaneDi/274759663340922adeb930c66a2e37ba/raw/phantom.txt#👻%20Phantom%20VPN"
UPSTREAM_SUB = "https://alius-sub.com/sub/6M8yGU5Pp_0M5Egr"

# Цены в Telegram Stars
PRICE_1_MONTH = 100
PRICE_3_MONTHS = 250

app = FastAPI()

# ==============================================================================
#  Криптографические Токены (Без базы данных, 100% надежно на Vercel)
# ==============================================================================

def create_user_token(username: str, days: int) -> str:
    now = int(time.time())
    exp = now + days * 86400
    payload = json.dumps({"u": username, "exp": exp, "t": now}, separators=(',', ':')).encode('utf-8')
    b64 = base64.urlsafe_b64encode(payload).decode('utf-8').rstrip('=')
    sig = hmac.new(SECRET_KEY.encode('utf-8'), b64.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{b64}.{sig}"

def decode_user_token(token: str) -> Optional[dict]:
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        b64, sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), b64.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        pad = len(b64) % 4
        if pad:
            b64 += '=' * (4 - pad)
        data = json.loads(base64.urlsafe_b64decode(b64.encode('utf-8')).decode('utf-8'))
        return data
    except Exception:
        return None

def send_telegram(method: str, payload: dict):
    url = f"{TELEGRAM_API}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.json()
    except Exception as e:
        print(f"Telegram API Error ({method}):", e)
        return None

# ==============================================================================
#  Маршруты Веб-сайта
# ==============================================================================

@app.get("/", response_class=PlainTextResponse)
def index():
    return "👻 Phantom VPN Web Portal & Bot on Vercel is Running Healthy 24/7!"

@app.get("/p/{token}", response_class=HTMLResponse)
def portal(token: str):
    data = decode_user_token(token)
    now = int(time.time())

    if not data:
        display_name = "Гость"
        is_active = False
        exp_ts = now
    else:
        display_name = data.get("u", "Пользователь")
        exp_ts = int(data.get("exp", now))
        is_active = exp_ts > now

    status_class = "badge-active" if is_active else "badge-expired"
    status_text = "АКТИВНА" if is_active else "ИСТЕКЛА"

    sub_url = DEFAULT_SUB_URL
    sub_url_encoded = urllib.parse.quote(sub_url, safe="")

    # Ищем шаблон рядом с файлом
    template_path = os.path.join(os.path.dirname(__file__), "portal.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "portal.html")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        html = f"<h1>Phantom VPN Portal</h1><p>Пользователь: {display_name}</p><p>Статус: {status_text}</p><p>Ссылка: {sub_url}</p>"

    html = html.replace("{{ USERNAME }}", display_name)
    html = html.replace("{{ STATUS_CLASS }}", status_class)
    html = html.replace("{{ STATUS_TEXT }}", status_text)
    html = html.replace("{{ EXPIRE_TIMESTAMP }}", str(exp_ts))
    html = html.replace("{{ SUB_URL }}", sub_url)
    html = html.replace("{{ SUB_URL_ENCODED }}", sub_url_encoded)

    return HTMLResponse(content=html)

@app.get("/sub", response_class=PlainTextResponse)
def get_sub():
    req = urllib.request.Request(UPSTREAM_SUB, headers={'User-Agent': 'v2rayNG/1.8.12'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            nodes_data = json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception:
        return PlainTextResponse("Sub temporarily unavailable", status=503)

    lte_lines = []
    wifi_lines = []

    for item in nodes_data:
        obs = item.get('outbounds', [])
        if not obs or obs[0].get('protocol') != 'vless':
            continue
        ob = obs[0]
        vnext = ob['settings']['vnext'][0]
        addr = vnext['address']
        port = int(vnext['port'])
        user = vnext['users'][0]
        uuid = user['id']
        flow = user.get('flow', '')

        stream = ob.get('streamSettings', {})
        net = stream.get('network', 'tcp')
        sec = stream.get('security', '')
        params = {'encryption': 'none', 'type': net}
        if flow: params['flow'] = flow
        if sec: params['security'] = sec

        if sec == 'reality':
            rs = stream.get('realitySettings', {})
            if rs.get('serverName'): params['sni'] = rs['serverName']
            if rs.get('fingerprint'): params['fp'] = rs['fingerprint']
            if rs.get('publicKey'): params['pbk'] = rs['publicKey']
            if rs.get('shortId'): params['sid'] = rs['shortId']
        elif sec == 'tls':
            tls = stream.get('tlsSettings', {})
            if tls.get('serverName'): params['sni'] = tls['serverName']
            if tls.get('fingerprint'): params['fp'] = tls['fingerprint']
            if tls.get('alpn'): params['alpn'] = ','.join(tls['alpn'])

        if net == 'ws':
            ws = stream.get('wsSettings', {})
            if ws.get('path'): params['path'] = ws['path']
            if ws.get('host'): params['host'] = ws['host']
        elif net == 'grpc':
            grpc = stream.get('grpcSettings', {})
            if grpc.get('serviceName'): params['serviceName'] = grpc['serviceName']

        q = urllib.parse.urlencode(params)
        rem = item.get('remarks', '')
        if 'LTE' in rem or 'lte' in rem:
            clean = rem.replace('LTE', '').replace('трафик', '').replace('x8', '').replace('x30', '').replace('x3-x10', '').replace('x7', '').replace('^~2~^', '').strip()
            name = urllib.parse.quote(f"📱 LTE · {clean}")
            lte_lines.append(f"vless://{uuid}@{addr}:{port}?{q}#{name}")
        else:
            clean = rem.replace('Скоростной', '').replace('Безлимит', '').replace('Ultra', '').replace('Основной', '').strip()
            name = urllib.parse.quote(f"⚡ Wi-Fi 4K · {clean}")
            wifi_lines.append(f"vless://{uuid}@{addr}:{port}?{q}#{name}")

    b1 = urllib.parse.quote('📢 Статус: АКТИВНА · Безлимит 24/7')
    b2 = urllib.parse.quote('⏳ Тариф: VIP Премиум · До конца: 30 дней')
    lines = [
        f"vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?encryption=none#{b1}",
        f"vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?encryption=none#{b2}"
    ] + lte_lines + wifi_lines
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")

# ==============================================================================
#  Обработчик Webhook от Telegram Bot API (Ловит все возможные пути)
# ==============================================================================

@app.post("/api/webhook")
@app.post("/webhook")
@app.post("/api/index.py")
@app.post("/")
async def telegram_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    base_url = "https://phantomvpn.vercel.app"

    # 1. Pre Checkout Query (Одобрение Stars)
    if "pre_checkout_query" in body:
        pcq = body["pre_checkout_query"]
        send_telegram("answerPreCheckoutQuery", {"pre_checkout_query_id": pcq["id"], "ok": True})
        return {"ok": True}

    # 2. Обычные сообщения
    if "message" in body:
        msg = body["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
        username = from_user.get("username", "")
        uname_tag = f"@{username}" if username else from_user.get("first_name", "User")
        is_admin_user = username and username.lower() in [u.lower() for u in ADMIN_USERNAMES]

        # Оплата Stars
        if "successful_payment" in msg:
            payload = msg["successful_payment"]["invoice_payload"]
            days = 90 if "90" in payload else 30
            token = create_user_token(uname_tag, days)
            portal_url = f"{base_url}/p/{token}"

            text = (
                "🎉 <b>Оплата успешно принята!</b>\n\n"
                f"Ваша подписка Phantom VPN активирована на <b>{days} дней</b>.\n\n"
                "🌐 <b>Твой персональный сайт и личный кабинет:</b>\n"
                f"👉 <a href='{portal_url}'>{portal_url}</a>\n"
                "<i>(На сайте тикает таймер до конца подписки и есть кнопка добавления в 1 клик)</i>\n\n"
                "🔗 <b>Прямая ссылка для Happ VPN:</b>\n"
                f"<code>{DEFAULT_SUB_URL}</code>"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}],
                    [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}]
                ]
            }
            send_telegram("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb})
            return {"ok": True}

        text = msg.get("text", "").strip()

        # Команда /start
        if text.startswith("/start"):
            token = create_user_token(uname_tag, 0)
            portal_url = f"{base_url}/p/{token}"
            admin_note = " [👑 АДМИНИСТРАТОР]" if is_admin_user else ""

            welcome = (
                f"👻 <b>Добро пожаловать в Phantom VPN!</b>{admin_note}\n\n"
                "⚡ <b>Ghost Protocol:</b> Сервера для 4K без лагов и обхода любых мобильных глушилок операторов.\n\n"
                "⭐ <b>Доступно 25 серверов:</b>\n"
                "• 18 LTE серверов (обход глушилок мобильного интернета)\n"
                "• 7 скоростных Wi-Fi 4K серверов\n\n"
                "🌐 <b>У вас есть Личный Кабинет на сайте с таймером!</b>"
            )
            buttons = [
                [
                    {"text": "⭐ Купить подписку", "callback_data": "buy_menu"},
                    {"text": "🌐 Личный Кабинет (Сайт)", "url": portal_url}
                ],
                [
                    {"text": "📥 Скачать Happ VPN", "url": "https://github.com/happ-proxy/happ-android/releases"},
                    {"text": "💬 Помощь и FAQ", "callback_data": "faq"}
                ]
            ]
            if is_admin_user:
                buttons.append([{"text": "👑 Админ-команда: /add @юзер 30", "callback_data": "adm_help"}])

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": welcome,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": buttons}
            })
            return {"ok": True}

        # Админ-команда выдачи VPN: /add @username 30
        if is_admin_user and (text.startswith("/add") or text.startswith("/grant")):
            parts = text.split()
            if len(parts) >= 3:
                target_user = parts[1]
                try:
                    days = int(parts[2])
                    token = create_user_token(target_user, days)
                    portal_url = f"{base_url}/p/{token}"
                    reply_text = (
                        f"✅ <b>Подписка успешно выдана!</b>\n\n"
                        f"👤 Пользователь: <b>{target_user}</b>\n"
                        f"⏳ Срок: <b>{days} дней</b>\n\n"
                        f"🌐 <b>Персональная ссылка на его сайт-кабинет:</b>\n"
                        f"👉 {portal_url}\n\n"
                        f"🔗 <i>Отправь эту ссылку покупателю. На сайте у него будет тикать живой таймер и кнопка добавления в Happ VPN!</i>"
                    )
                    send_telegram("sendMessage", {"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"})
                    return {"ok": True}
                except ValueError:
                    pass

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": "Формат команды: <code>/add @username 30</code> (где 30 — количество дней)",
                "parse_mode": "HTML"
            })
            return {"ok": True}

    # 3. Кнопки (Callback)
    if "callback_query" in body:
        cb = body["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")

        send_telegram("answerCallbackQuery", {"callback_query_id": cb_id})

        if data == "buy_menu":
            buy_text = (
                "⭐ <b>Выберите период подписки:</b>\n\n"
                "Оплата производится мгновенно прямо в Telegram через <b>Telegram Stars</b>.\n\n"
                "• <b>1 месяц</b> — 100 ⭐ (Безлимит 24/7 на всех устройствах)\n"
                "• <b>3 месяца</b> — 250 ⭐ (Экономия 50 ⭐)"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "⭐ 1 месяц — 100 Stars", "callback_data": "pay_1m"}],
                    [{"text": "⭐ 3 месяца — 250 Stars", "callback_data": "pay_3m"}]
                ]
            }
            send_telegram("sendMessage", {"chat_id": chat_id, "text": buy_text, "parse_mode": "HTML", "reply_markup": kb})

        elif data == "pay_1m":
            send_telegram("sendInvoice", {
                "chat_id": chat_id,
                "title": "Phantom VPN — 1 Месяц",
                "description": "Безлимитный доступ к 25 серверам на 30 дней + Личный Кабинет на сайте.",
                "payload": "sub_30_days",
                "currency": "XTR",
                "prices": [{"label": "1 Месяц", "amount": PRICE_1_MONTH}]
            })

        elif data == "pay_3m":
            send_telegram("sendInvoice", {
                "chat_id": chat_id,
                "title": "Phantom VPN — 3 Месяца",
                "description": "Безлимитный доступ к 25 серверам на 90 дней со скидкой + Личный Кабинет.",
                "payload": "sub_90_days",
                "currency": "XTR",
                "prices": [{"label": "3 Месяца", "amount": PRICE_3_MONTHS}]
            })

        elif data == "faq":
            faq_text = (
                "💬 <b>Часто задаваемые вопросы:</b>\n\n"
                "1. <b>Как подключиться?</b>\n"
                "Открой сайт своего личного кабинета и нажми кнопку «Добавить в Happ VPN в 1 клик».\n\n"
                "2. <b>Работает ли на мобильном?</b>\n"
                "Да! Первые 18 серверов (📱 LTE) созданы для обхода блокировок мобильных операторов.\n\n"
                "3. <b>Какая скорость?</b>\n"
                "До 1 Гбит/с без лимита трафика."
            )
            send_telegram("sendMessage", {"chat_id": chat_id, "text": faq_text, "parse_mode": "HTML"})

        elif data == "adm_help":
            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": "👑 <b>Команды администратора (@zzylx):</b>\n\nЧтобы выдать подписку, просто напиши боту:\n<code>/add @username 30</code>\n\nБот сгенерирует готовую ссылку на сайт с живым таймером на 30 дней!",
                "parse_mode": "HTML"
            })

    return {"ok": True}
