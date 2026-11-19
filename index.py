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
#  👻 Phantom VPN — Remnawave / H1Cloud Style Serverless Portal + Bot (@zzylx)
# ==============================================================================

BOT_TOKEN = "9017418443:AAGF0_2yQOBIg6wO5-GGa7WvzGvVTJTBClo"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_USERNAMES = ["zzylx"]
SECRET_KEY = os.environ.get("SECRET_KEY", "phantom_vpn_ultra_secret_2026_key")

DEFAULT_SUB_URL = "https://gist.githubusercontent.com/FlaneDi/274759663340922adeb930c66a2e37ba/raw/phantom.txt#👻%20Phantom%20VPN"
UPSTREAM_SUB = "https://alius-sub.com/sub/6M8yGU5Pp_0M5Egr"
BOT_TELEGRAM_LINK = "https://t.me/PhantomVPN_bot"

PRICE_1_MONTH = 100
PRICE_3_MONTHS = 250

app = FastAPI()

# База данных пользователей в /tmp
DB_PATH = "/tmp/users_registry.json"

def load_db() -> dict:
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "usernames": {}}

def save_db(data: dict):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

# ==============================================================================
#  Криптографические Токены
# ==============================================================================

def create_user_token(username: str, days: int) -> str:
    now = int(time.time())
    exp = now + days * 86400
    payload = json.dumps({"u": username, "exp": exp, "t": now}, separators=(',', ':')).encode('utf-8')
    b64 = base64.urlsafe_b64encode(payload).decode('utf-8').rstrip('=')
    sig = hmac.new(SECRET_KEY.encode('utf-8'), b64.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{b64}.{sig}"

def decode_user_token(token: str) -> Optional[dict]:
    if not token:
        return None
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

def render_portal(token: str = "") -> HTMLResponse:
    data = decode_user_token(token) if token else None
    now = int(time.time())

    if not data:
        display_name = "Не авторизован"
        plan_title = "Нет активной подписки"
        is_active = False
        exp_ts = now
        status_class = "badge-expired"
        status_text = "🔴 НЕ АКТИВНА"
        active_display = "display: none;"
        expired_display = "display: flex;"
        servers_display = "display: none;"
        brand_dot_class = "offline"
        nav_badge_text = "Доступ закрыт"
        sub_url = ""
    else:
        display_name = data.get("u", "Пользователь")
        exp_ts = int(data.get("exp", 0))

        if now >= exp_ts:
            plan_title = "Подписка истекла"
            is_active = False
            status_class = "badge-expired"
            status_text = "🔴 ИСТЕКЛА"
            active_display = "display: none;"
            expired_display = "display: flex;"
            servers_display = "display: none;"
            brand_dot_class = "offline"
            nav_badge_text = "Подписка истекла"
            sub_url = ""
        else:
            plan_title = "VIP Премиум (Безлимит)"
            is_active = True
            status_class = "badge-active"
            status_text = "🟢 АКТИВНА"
            active_display = "display: block;"
            expired_display = "display: none;"
            servers_display = "display: block;"
            brand_dot_class = ""
            nav_badge_text = "⚡ 25 Нод Онлайн"
            sub_url = DEFAULT_SUB_URL

    sub_url_encoded = urllib.parse.quote(sub_url, safe="") if sub_url else ""

    template_path = os.path.join(os.path.dirname(__file__), "portal.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "portal.html")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        html = f"<h1>Phantom VPN Portal</h1><p>Пользователь: {display_name}</p><p>Статус: {status_text}</p>"

    html = html.replace("{{ USERNAME }}", display_name)
    html = html.replace("{{ PLAN_TITLE }}", plan_title)
    html = html.replace("{{ STATUS_CLASS }}", status_class)
    html = html.replace("{{ STATUS_TEXT }}", status_text)
    html = html.replace("{{ EXPIRE_TIMESTAMP }}", str(exp_ts))
    html = html.replace("{{ IS_ACTIVE_JS }}", "true" if is_active else "false")
    html = html.replace("{{ ACTIVE_DISPLAY }}", active_display)
    html = html.replace("{{ EXPIRED_DISPLAY }}", expired_display)
    html = html.replace("{{ SERVERS_DISPLAY }}", servers_display)
    html = html.replace("{{ BRAND_DOT_CLASS }}", brand_dot_class)
    html = html.replace("{{ NAV_BADGE_TEXT }}", nav_badge_text)
    html = html.replace("{{ SUB_URL }}", sub_url)
    html = html.replace("{{ SUB_URL_ENCODED }}", sub_url_encoded)
    html = html.replace("{{ BOT_URL }}", BOT_TELEGRAM_LINK)

    return HTMLResponse(content=html)

def render_sub() -> PlainTextResponse:
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
#  Обработка Telegram Webhook
# ==============================================================================

async def process_telegram_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    base_url = "https://phantomvpn.vercel.app"
    db = load_db()

    # Pre-checkout query
    if "pre_checkout_query" in body:
        pcq = body["pre_checkout_query"]
        send_telegram("answerPreCheckoutQuery", {"pre_checkout_query_id": pcq["id"], "ok": True})
        return {"ok": True}

    if "message" in body:
        msg = body["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
        username = from_user.get("username", "")
        uname_clean = username.lstrip("@").lower() if username else ""
        uname_tag = f"@{username}" if username else from_user.get("first_name", "User")
        is_admin_user = uname_clean in [u.lower() for u in ADMIN_USERNAMES]

        # Сохраняем chat_id пользователя в реестр
        if uname_clean:
            db["usernames"][uname_clean] = chat_id
        db["users"][str(chat_id)] = {
            "username": uname_clean,
            "first_name": from_user.get("first_name", "")
        }
        save_db(db)

        # Оплата Stars
        if "successful_payment" in msg:
            payload = msg["successful_payment"]["invoice_payload"]
            days = 90 if "90" in payload else 30
            token = create_user_token(uname_tag, days)
            portal_url = f"{base_url}/p/{token}"

            db["users"][str(chat_id)]["token"] = token
            save_db(db)

            text = (
                "🎉 <b>Оплата успешно принята!</b>\n\n"
                f"Ваша подписка Phantom VPN активирована на <b>{days} дней</b>.\n\n"
                "🌐 <b>Твой персональный сайт и личный кабинет (Remnawave):</b>\n"
                f"👉 <a href='{portal_url}'>{portal_url}</a>\n"
                "<i>(На сайте тикает таймер до конца подписки и есть кнопка добавления в 1 клик)</i>\n\n"
                "🔗 <b>Прямая ссылка для Happ VPN:</b>\n"
                f"<code>{DEFAULT_SUB_URL}</code>"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                    [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}]
                ]
            }
            send_telegram("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb})
            return {"ok": True}

        text = msg.get("text", "").strip()

        # Команда /start
        if text.startswith("/start"):
            # Проверяем, есть ли у пользователя уже активная подписка
            user_data = db["users"].get(str(chat_id), {})
            existing_token = user_data.get("token")
            token_info = decode_user_token(existing_token) if existing_token else None
            now = int(time.time())

            if token_info and int(token_info.get("exp", 0)) > now:
                # У пользователя УЖЕ ЕСТЬ подписка!
                token = existing_token
                portal_url = f"{base_url}/p/{token}"
                exp_dt = datetime.fromtimestamp(int(token_info["exp"]))
                date_fmt = exp_dt.strftime("%d.%m.%Y в %H:%M")

                welcome = (
                    f"👻 <b>С возвращением в Phantom VPN!</b>\n\n"
                    f"🟢 <b>Ваша подписка АКТИВНА до:</b> {date_fmt}\n\n"
                    f"🌐 <b>Ваш сайт и таймер:</b> <a href='{portal_url}'>Личный Кабинет</a>\n\n"
                    f"⚡ Все 25 серверов доступны без ограничений!"
                )
                buttons = [
                    [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                    [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}],
                    [{"text": "⭐ Продлить подписку", "callback_data": "buy_menu"}],
                    [{"text": "💬 Помощь и FAQ", "callback_data": "faq"}]
                ]
            else:
                # Подписки нет
                token = create_user_token(uname_tag, 0)
                portal_url = f"{base_url}/p/{token}"
                admin_note = " [👑 АДМИНИСТРАТОР]" if is_admin_user else ""

                welcome = (
                    f"👻 <b>Добро пожаловать в Phantom VPN!</b>{admin_note}\n\n"
                    "⚡ <b>Ghost Protocol:</b> Сервера для 4K без лагов и обхода любых мобильных глушилок операторов.\n\n"
                    "⭐ <b>Доступно 25 серверов:</b>\n"
                    "• 18 LTE серверов (обход глушилок мобильного интернета)\n"
                    "• 7 скоростных Wi-Fi 4K серверов\n\n"
                    "🌐 <b>У вас есть Личный Кабинет Remnawave с живым таймером!</b>"
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
                buttons.append([{"text": "👑 Выдать подписку: /add @юзер 30", "callback_data": "adm_help"}])

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": welcome,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": buttons}
            })
            return {"ok": True}

        # Выдача подписки админом: /add @username 30
        if is_admin_user and (text.startswith("/add") or text.startswith("/grant")):
            parts = text.split()
            if len(parts) >= 3:
                target_user = parts[1]
                target_clean = target_user.lstrip("@").lower()
                try:
                    days = int(parts[2])
                    token = create_user_token(f"@{target_clean}", days)
                    portal_url = f"{base_url}/p/{token}"
                    exp_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

                    # Проверяем, запускал ли друг бота (известен ли chat_id)
                    friend_chat_id = db["usernames"].get(target_clean)

                    if friend_chat_id:
                        # Сохраняем токен в базу друга
                        if str(friend_chat_id) in db["users"]:
                            db["users"][str(friend_chat_id)]["token"] = token
                            save_db(db)

                        # АВТОМАТИЧЕСКИ ОТПРАВЛЯЕМ ПОДПИСКУ ДРУГУ В ЛИЧКУ!
                        notify_friend = (
                            f"🎉 <b>Администратор @zzylx выдал вам VIP-подписку Phantom VPN на {days} дней!</b>\n\n"
                            f"📅 <b>Действует до:</b> {exp_date}\n\n"
                            f"🌐 <b>Твой персональный сайт и личный кабинет:</b>\n"
                            f"👉 <a href='{portal_url}'>{portal_url}</a>\n"
                            f"<i>(На сайте тикает таймер до конца подписки и есть кнопка добавления в 1 клик)</i>\n\n"
                            f"🔗 <b>Прямая ссылка для Happ VPN:</b>\n"
                            f"<code>{DEFAULT_SUB_URL}</code>"
                        )
                        kb_friend = {
                            "inline_keyboard": [
                                [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                                [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}]
                            ]
                        }
                        send_telegram("sendMessage", {
                            "chat_id": friend_chat_id,
                            "text": notify_friend,
                            "parse_mode": "HTML",
                            "reply_markup": kb_friend
                        })

                        admin_reply = (
                            f"✅ <b>Подписка успешно выдана!</b>\n\n"
                            f"👤 Пользователь: <b>@{target_clean}</b>\n"
                            f"⏳ Срок: <b>{days} дней</b> (до {exp_date})\n\n"
                            f"🚀 <b>Бот автоматически отправил сообщение и ссылку пользователю @{target_clean} в личные сообщения!</b>\n\n"
                            f"🌐 Ссылка на его сайт: {portal_url}"
                        )
                    else:
                        admin_reply = (
                            f"✅ <b>Подписка на {days} дней создана!</b>\n\n"
                            f"👤 Пользователь: <b>@{target_clean}</b>\n"
                            f"⏳ Срок: <b>{days} дней</b> (до {exp_date})\n\n"
                            f"⚠️ <i>Пользователь @{target_clean} ещё не запускал этого бота (/start), поэтому правила Telegram запрещают боту писать ему первым.</i>\n\n"
                            f"👉 <b>Отправь ему эту готовую ссылку на сайт:</b>\n"
                            f"{portal_url}\n\n"
                            f"<i>Либо попроси его нажать /start в боте, и в следующий раз бот будет присылать ему всё сам!</i>"
                        )

                    send_telegram("sendMessage", {"chat_id": chat_id, "text": admin_reply, "parse_mode": "HTML"})
                    return {"ok": True}
                except ValueError:
                    pass

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": "Формат команды: <code>/add @username 30</code>",
                "parse_mode": "HTML"
            })
            return {"ok": True}

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
                "text": "👑 <b>Команды администратора (@zzylx):</b>\n\nЧтобы выдать подписку, напиши:\n<code>/add @username 30</code>\n\nЕсли пользователь уже нажимал /start, бот автоматически отправит ему подписку в личку!",
                "parse_mode": "HTML"
            })

    return {"ok": True}

# ==============================================================================
#  УНИВЕРСАЛЬНЫЙ РОУТЕР
# ==============================================================================

@app.api_route("/{full_path:path}", methods=["GET", "POST", "HEAD"])
async def universal_handler(full_path: str, request: Request):
    if request.method == "POST":
        return await process_telegram_webhook(request)

    if request.query_params.get("action") == "sub" or "/sub" in full_path:
        return render_sub()

    token = request.query_params.get("token", "")
    if not token and "/p/" in full_path:
        token = full_path.split("/p/")[-1].split("?")[0].strip("/")

    if not token:
        for h in ["x-forwarded-uri", "x-invoke-path"]:
            val = request.headers.get(h, "")
            if "/p/" in val:
                token = val.split("/p/")[-1].split("?")[0].strip("/")
                break

    return render_portal(token)
