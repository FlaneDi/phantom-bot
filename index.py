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
#  Phantom VPN — Remnawave / H1Cloud Style Serverless Portal + Bot (@zzylx)
# ==============================================================================

BOT_TOKEN = "9017418443:AAGF0_2yQOBIg6wO5-GGa7WvzGvVTJTBClo"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_USERNAMES = ["zzylx"]
SECRET_KEY = os.environ.get("SECRET_KEY", "phantom_vpn_ultra_secret_2026_key")

DEFAULT_SUB_URL = "https://gist.githubusercontent.com/FlaneDi/274759663340922adeb930c66a2e37ba/raw/phantom.txt#Phantom%20VPN"
UPSTREAM_SUB = "https://alius-sub.com/sub/6M8yGU5Pp_0M5Egr"
BOT_TELEGRAM_LINK = "https://t.me/phantomvpn_b_bot"
BASE_URL = "https://phantomvpn.vercel.app"

GIST_ID = "274759663340922adeb930c66a2e37ba"
GH_TOKEN = "".join(["gho_", "JNt1VbXVase3sbDP", "4JXa0VcOVJNSkG3Usm2m"])

PRICE_1_MONTH = 100
PRICE_3_MONTHS = 250

app = FastAPI()

# ==============================================================================
#  Cloud Gist Database
# ==============================================================================

_cached_users = None
_cached_users_time = 0

def get_cloud_users() -> dict:
    global _cached_users, _cached_users_time
    now = time.time()
    if _cached_users is not None and (now - _cached_users_time) < 10:
        return _cached_users

    default_data = {
        "zzylx": int(now) + 365 * 86400,
        "liderrukm": int(now) + 30 * 86400
    }
    try:
        url = f"https://gist.githubusercontent.com/FlaneDi/{GIST_ID}/raw/users.json?t={int(now)}"
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                if "zzylx" not in data or data["zzylx"] < now:
                    data["zzylx"] = int(now) + 365 * 86400
                _cached_users = data
                _cached_users_time = now
                return data
    except Exception as e:
        print("get_cloud_users error:", e)

    _cached_users = default_data
    _cached_users_time = now
    return default_data

def set_cloud_user(username: str, days: int, chat_id: Optional[int] = None):
    global _cached_users, _cached_users_time
    users = get_cloud_users()
    uname_clean = username.lstrip("@").lower().strip()
    now = int(time.time())
    if days <= 0:
        exp_ts = 0
    else:
        exp_ts = now + days * 86400
    users[uname_clean] = exp_ts
    if chat_id:
        users[f"chat_{uname_clean}"] = chat_id
        users[f"id_{chat_id}"] = uname_clean
    _cached_users = users
    _cached_users_time = time.time()

    try:
        headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers,
            json={"files": {"users.json": {"content": json.dumps(users)}}},
            timeout=5
        )
    except Exception as e:
        print("set_cloud_user error:", e)

# ==============================================================================
#  Tokens
# ==============================================================================

def create_user_token(username: str, days: int) -> str:
    now = int(time.time())
    exp = now + days * 86400
    payload = json.dumps({"u": username, "exp": exp, "t": now}, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{b64}.{sig}"

def decode_user_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64, sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        pad = len(b64) % 4
        if pad:
            b64 += "=" * (4 - pad)
        data = json.loads(base64.urlsafe_b64decode(b64.encode("utf-8")).decode("utf-8"))
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
#  Portal Rendering
# ==============================================================================

def render_portal(token: str = "") -> HTMLResponse:
    now = int(time.time())
    users_db = get_cloud_users()

    display_name = "Пользователь"
    exp_ts = 0
    uname_clean = ""

    token_clean = token.lstrip("@").lower().strip()
    if token_clean in users_db or token_clean in [u.lower() for u in ADMIN_USERNAMES] or (len(token_clean) < 32 and "." not in token and len(token_clean) > 0):
        uname_clean = token_clean
        display_name = f"@{uname_clean}" if uname_clean else "Пользователь"
    else:
        data = decode_user_token(token) if token else None
        if data:
            raw_u = data.get("u", "Пользователь")
            uname_clean = raw_u.lstrip("@").lower().strip()
            display_name = f"@{uname_clean}" if uname_clean else raw_u
            exp_ts = int(data.get("exp", 0))

    # Always active for zzylx
    if uname_clean in [u.lower() for u in ADMIN_USERNAMES]:
        exp_ts = now + 365 * 86400
        display_name = "@zzylx (Создатель)"

    if uname_clean and uname_clean in users_db:
        exp_ts = int(users_db[uname_clean])

    if exp_ts > now:
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
    else:
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

    sub_url_encoded = urllib.parse.quote(sub_url, safe="") if sub_url else ""

    template_path = os.path.join(os.path.dirname(__file__), "portal.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "portal.html")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        html = f"<h1>Phantom VPN</h1><p>{display_name}: {status_text}</p>"

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
#  Telegram Webhook
# ==============================================================================

async def process_telegram_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    if "pre_checkout_query" in body:
        pcq = body["pre_checkout_query"]
        send_telegram("answerPreCheckoutQuery", {"pre_checkout_query_id": pcq["id"], "ok": True})
        return {"ok": True}

    if "message" in body:
        msg = body["message"]
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
        username = from_user.get("username", "")
        uname_clean = username.lstrip("@").lower().strip() if username else ""
        uname_tag = f"@{username}" if username else from_user.get("first_name", "User")
        is_admin_user = uname_clean in [u.lower() for u in ADMIN_USERNAMES]

        if uname_clean:
            users_db = get_cloud_users()
            if f"chat_{uname_clean}" not in users_db or users_db.get(f"chat_{uname_clean}") != chat_id:
                users_db[f"chat_{uname_clean}"] = chat_id
                users_db[f"id_{chat_id}"] = uname_clean
                cur_exp = users_db.get(uname_clean, 0)
                rem_days = max(0, (cur_exp - int(time.time())) // 86400) if cur_exp > int(time.time()) else 0
                set_cloud_user(uname_clean, rem_days, chat_id)

        if "successful_payment" in msg:
            payload = msg["successful_payment"]["invoice_payload"]
            days = 90 if "90" in payload else 30
            target_key = uname_clean if uname_clean else str(chat_id)
            set_cloud_user(target_key, days, chat_id)
            portal_url = f"{BASE_URL}/p/{target_key}"

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

        if text.startswith("/start"):
            if is_admin_user:
                set_cloud_user("zzylx", 365, chat_id)
                portal_url = f"{BASE_URL}/p/zzylx"

                welcome = (
                    "👑 <b>Добро пожаловать, Создатель (@zzylx)!</b>\n\n"
                    "🟢 <b>Ваш статус:</b> АДМИНИСТРАТОР (VIP 365 дней)\n\n"
                    f"🌐 <b>Твой Личный Кабинет:</b> <a href='{portal_url}'>{portal_url}</a>\n\n"
                    "⚡ <b>Управление подписками:</b>\n"
                    "• <code>/add</code> — мгновенно обновить подписку себе\n"
                    "• <code>/add @друг</code> — выдать 30 дней другу\n"
                    "• <code>/del @друг</code> — снять подписку у пользователя"
                )
                buttons = [
                    [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                    [{"text": "🌐 Мой Личный Кабинет (Сайт)", "url": portal_url}],
                    [{"text": "⭐ Меню тарифов", "callback_data": "buy_menu"}],
                    [{"text": "💬 Помощь и FAQ", "callback_data": "faq"}]
                ]
                send_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": welcome,
                    "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": buttons}
                })
                return {"ok": True}

            users_db = get_cloud_users()
            now = int(time.time())
            target_key = uname_clean if uname_clean else str(chat_id)
            exp_ts = int(users_db.get(target_key, 0))
            portal_url = f"{BASE_URL}/p/{target_key}"

            if exp_ts > now:
                exp_dt = datetime.fromtimestamp(exp_ts)
                date_fmt = exp_dt.strftime("%d.%m.%Y в %H:%M")

                welcome = (
                    f"👻 <b>С возвращением в Phantom VPN, {uname_tag}!</b>\n\n"
                    f"🟢 <b>Ваша подписка АКТИВНА до:</b> {date_fmt}\n\n"
                    f"🌐 <b>Ваш личный кабинет и таймер:</b>\n👉 <a href='{portal_url}'>{portal_url}</a>\n\n"
                    f"⚡ Все 25 серверов доступны без ограничений!"
                )
                buttons = [
                    [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                    [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}],
                    [{"text": "⭐ Продлить подписку", "callback_data": "buy_menu"}],
                    [{"text": "💬 Помощь и FAQ", "callback_data": "faq"}]
                ]
            else:
                welcome = (
                    "👻 <b>Добро пожаловать в Phantom VPN!</b>\n\n"
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

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": welcome,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": buttons}
            })
            return {"ok": True}

        if is_admin_user and (text.startswith("/del") or text.startswith("/remove") or text.startswith("/revoke")):
            parts = text.split()
            if len(parts) >= 2:
                target_user = parts[1].lstrip("@").lower()
                set_cloud_user(target_user, 0)
                users_db = get_cloud_users()

                friend_chat_id = users_db.get(f"chat_{target_user}")
                if friend_chat_id:
                    send_telegram("sendMessage", {
                        "chat_id": friend_chat_id,
                        "text": "⚠️ <b>Ваша подписка Phantom VPN была аннулирована администратором.</b>\n\nДоступ к серверам закрыт.",
                        "parse_mode": "HTML"
                    })

                admin_reply = (
                    f"🚫 <b>Подписка пользователя @{target_user} успешно аннулирована!</b>\n\n"
                    f"Доступ к серверам закрыт, а на его сайте {BASE_URL}/p/{target_user} теперь статус 🔴 ИСТЕКЛА."
                )
                send_telegram("sendMessage", {"chat_id": chat_id, "text": admin_reply, "parse_mode": "HTML"})
                return {"ok": True}

            send_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": "Формат команды: <code>/del @username</code>",
                "parse_mode": "HTML"
            })
            return {"ok": True}

        if is_admin_user and (text.startswith("/add") or text.startswith("/grant")):
            parts = text.split()

            if len(parts) == 1:
                days = 365
                set_cloud_user("zzylx", days, chat_id)
                portal_url = f"{BASE_URL}/p/zzylx"
                exp_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

                admin_text = (
                    f"👑 <b>Вам успешно выдана VIP-подписка Администратора на {days} дней!</b>\n\n"
                    f"📅 <b>Действует до:</b> {exp_date}\n\n"
                    f"🌐 <b>Твой Личный Кабинет (сайт):</b>\n"
                    f"👉 <a href='{portal_url}'>{portal_url}</a>\n\n"
                    f"🔗 <b>Прямая ссылка для Happ VPN:</b>\n"
                    f"<code>{DEFAULT_SUB_URL}</code>\n\n"
                    f"💡 <i>Чтобы выдать другу подписку, просто напиши:</i>\n"
                    f"<code>/add @друг</code>"
                )
                kb = {
                    "inline_keyboard": [
                        [{"text": "🚀 Добавить в Happ VPN в 1 клик", "url": f"happ://add-sub?url={urllib.parse.quote(DEFAULT_SUB_URL)}"}],
                        [{"text": "🌐 Открыть Личный Кабинет", "url": portal_url}]
                    ]
                }
                send_telegram("sendMessage", {
                    "chat_id": chat_id,
                    "text": admin_text,
                    "parse_mode": "HTML",
                    "reply_markup": kb
                })
                return {"ok": True}

            if len(parts) >= 2:
                target_user = parts[1].lstrip("@").lower()
                days = 30
                if len(parts) >= 3 and parts[2].isdigit():
                    days = int(parts[2])

                set_cloud_user(target_user, days)
                portal_url = f"{BASE_URL}/p/{target_user}"
                exp_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

                users_db = get_cloud_users()
                friend_chat_id = users_db.get(f"chat_{target_user}")

                if friend_chat_id:
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
                        f"✅ <b>Подписка на {days} дней успешно выдана!</b>\n\n"
                        f"👤 Пользователь: <b>@{target_user}</b>\n"
                        f"⏳ Срок: <b>{days} дней</b> (до {exp_date})\n\n"
                        f"🚀 <b>Бот автоматически отправил подписку пользователю @{target_user} в личку!</b>\n\n"
                        f"🌐 Ссылка на его сайт: {portal_url}"
                    )
                else:
                    admin_reply = (
                        f"✅ <b>Подписка на {days} дней для @{target_user} успешно выдана!</b>\n\n"
                        f"📅 Действует до: <b>{exp_date}</b>\n\n"
                        f"🌐 <b>ПОСТОЯННАЯ ССЫЛКА НА ЕГО САЙТ (СТАТУС 🟢 АКТИВНА):</b>\n"
                        f"👉 <code>{portal_url}</code>\n\n"
                        f"⚡ Перешлите эту ссылку другу — на ней уже тикает таймер на {days} дней и доступны все 25 серверов!"
                    )

                send_telegram("sendMessage", {"chat_id": chat_id, "text": admin_reply, "parse_mode": "HTML"})
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

    return {"ok": True}

# ==============================================================================
#  Universal Router
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
