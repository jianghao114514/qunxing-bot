# web/web_server.py
import sys
import queue
import threading
import time
import os
import json
import io
import csv
import logging
import glob
import subprocess
import urllib.request
import psutil
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_socketio import SocketIO, emit
from core.config import CONFIG, FEATURE_SWITCHES, SYSTEM_CONFIG, PERSONALITIES, MEMORY_CONFIG, CUSTOM_MENU_TEXTS, get_all_providers, save_providers
from core.database import (
    get_cached_user, get_user_stardust, get_user_cards_count, get_last_signin,
    refresh_friend_list, is_friend, add_stardust, get_stardust, get_current_persona,
    set_current_persona, get_long_memory, update_long_memory, update_cached_user,
    delete_user, get_nickname
)
from core.ai import call_ai_with_fallback
from core.utils import send_email
from core.ws_client import main_ws, ai_health_state   # 关键导入
from core.napcat_finder import find_exe, scan_napcat_exe
from core.version import app_version

# 屏蔽 werkzeug 的每次请求访问日志（GET /api/status 之类）
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('QUNXING_SECRET', __import__('secrets').token_hex(16))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

log_queue = queue.Queue(maxsize=500)
log_listeners = {}
start_time = time.time()
_stardust_cache = [0]
_stardust_cache_ts = 0.0
_auth_failures = [0]
_auth_lock_until = 0.0

class QueueWriter:
    def write(self, text):
        if text.strip():
            log_queue.put(text.strip())
    def flush(self):
        pass

def redirect_stdout_to_queue():
    sys.stdout = QueueWriter()
    sys.stderr = QueueWriter()

def broadcast_log():
    while True:
        msg = log_queue.get()
        for listener in list(log_listeners.values()):
            try:
                listener(msg)
            except:
                pass

@socketio.on('connect')
def handle_connect():
    # socket.io 同样受面板密码保护（query 里的 token 与密码一致才放行）
    password = CONFIG.get("web_password", "")
    if password:
        token = ""
        try:
            token = request.args.get("token", "") or (request.headers.get("X-Auth-Token") or "")
        except Exception:
            pass
        if token != password:
            return False   # 拒绝连接
    sid = request.sid
    def send_log(msg):
        socketio.emit('log', {'data': msg}, to=sid)
    log_listeners[sid] = send_log

@socketio.on('disconnect')
def handle_disconnect():
    log_listeners.pop(request.sid, None)

# 面板访问认证（设置了 web_password 后启用）
@app.before_request
def check_auth():
    if request.path.startswith('/api') and request.path != '/api/auth':
        password = CONFIG.get("web_password", "")
        if password and request.headers.get("X-Auth-Token") != password:
            return jsonify({'error': '未授权', 'code': 'UNAUTHORIZED'}), 401
    return None

@app.route('/api/auth', methods=['POST'])
def api_auth():
    global _auth_lock_until
    password = CONFIG.get("web_password", "")
    if not password:
        return jsonify({'success': True})
    # 简单限速：失败 5 次后锁 60 秒，防本地暴力破解
    now = time.time()
    if now - _auth_lock_until < 0:
        return jsonify({'success': False, 'error': '尝试过于频繁，请 1 分钟后再试'}), 429
    if request.json.get('password') == password:
        _auth_failures[0] = 0
        return jsonify({'success': True})
    _auth_failures[0] += 1
    if _auth_failures[0] >= 5:
        _auth_failures[0] = 0
        _auth_lock_until = now + 60
    return jsonify({'success': False, 'error': '密码错误'}), 401

# 前端模板从独立文件加载（web/template.html），修改后刷新页面即生效
def get_template():
    """读取前端页面模板（web/template.html），支持热更新"""
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    cls = []
    quality = CONFIG.get("web_ui_quality", "high")
    if quality == "fast":
        cls.append("perf-fast")
    elif quality == "balanced":
        cls.append("perf-bal")
    theme = CONFIG.get("web_theme", "light")
    if theme == "dark":
        cls.append("theme-dark")
    else:
        cls.append("theme-light")
    tpl = tpl.replace("<body>", '<body class="' + " ".join(cls) + '">', 1)
    return tpl

@app.route('/')
def index():
    return get_template(), 200, {'Content-Type': 'text/html', 'Cache-Control': 'no-store'}


@app.route('/api/status')
def api_status():
    global _stardust_cache_ts
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    # 总星尘统计较贵（扫全部用户文件），缓存 30 秒
    now = time.time()
    if now - _stardust_cache_ts > 30:
        total = 0
        for f in os.listdir(CONFIG["users_dir"]):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(CONFIG["users_dir"], f), "r", encoding="utf-8") as fp:
                        total += json.load(fp).get("stardust", 0)
                except Exception:
                    pass
        _stardust_cache[0] = total
        _stardust_cache_ts = now
    total = _stardust_cache[0]
    return jsonify({
        'ai_health': ai_health_state,
        'bot_qq': CONFIG['bot_qq'],
        'master_qq': CONFIG['master_qq'],
        'system_name': CONFIG.get('system_name', '群星'),
        'version': app_version(),
        'ui_quality': CONFIG.get('web_ui_quality', 'high'),
        'theme': CONFIG.get('web_theme', 'light'),
        'guide_auto': CONFIG.get('web_guide_auto', True),
        'uptime': int(time.time() - start_time),
        'total_stardust': total,
        'model': '多API',
        'cpu_percent': cpu,
        'memory_percent': mem.percent
    })

@app.route('/api/users')
def api_users():
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '')
    users = []
    for f in os.listdir(CONFIG["users_dir"]):
        if f.endswith(".json"):
            uid = f[:-5]
            if search and search not in uid:
                continue
            data = get_cached_user(uid)
            users.append({'qq': uid, 'nickname': data.get('nickname','') or '未记录',
                          'stardust': data.get('stardust',0), 'cards': len(data.get('cards',[])),
                          'last_signin': data.get('last_signin','未签到'),
                          'persona': data.get('current_persona','default')})
    users.sort(key=lambda x: x['qq'])
    total = len(users)
    users = users[(page-1)*per_page:page*per_page]
    return jsonify({'users': users, 'total': total, 'page': page, 'per_page': per_page})

def _check_qq(qq):
    """QQ 号必须是纯数字，防止路径/glob 注入"""
    if not str(qq).isdigit():
        return False
    return True


@app.route('/api/user/<qq>')
def api_user_detail(qq):
    if not _check_qq(qq):
        return jsonify({'success': False, 'error': 'QQ号格式错误'}), 400
    data = get_cached_user(qq)
    planet = data.get('planet') or {}
    return jsonify({
        'qq': qq,
        'nickname': get_nickname(qq) or qq,
        'stardust': data.get('stardust', 0),
        'cards': data.get('cards', []),
        'last_signin': data.get('last_signin', '未签到'),
        'persona': data.get('current_persona', 'default'),
        'planet': {'name': planet.get('name',''), 'level': planet.get('level',1),
                   'stage': planet.get('stage',1), 'energy': planet.get('energy',0),
                   'streak': planet.get('streak',0)} if planet else None,
    })

@app.route('/api/user/<qq>/stardust', methods=['POST'])
def api_user_set_stardust(qq):
    if not _check_qq(qq):
        return jsonify({'success': False, 'error': 'QQ号格式错误'}), 400
    try:
        amount = int(request.json.get('stardust'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': '参数错误'}), 400
    data = get_cached_user(qq)
    data['stardust'] = max(0, amount)
    update_cached_user(qq, data)
    from core.config import save_config
    save_config()
    return jsonify({'success': True, 'stardust': data['stardust']})

@app.route('/api/user/<qq>/delete', methods=['POST'])
def api_user_delete(qq):
    if not _check_qq(qq):
        return jsonify({'success': False, 'error': 'QQ号格式错误'}), 400
    from core.database import delete_user
    delete_user(qq)
    return jsonify({'success': True})

@app.route('/api/features')
def api_features():
    name_map = {'signin':'签到','draw':'抽卡','tarot':'塔罗','aichat':'AI聊天','weather':'天气','joke':'笑话','kfc':'疯狂星期四','emo':'每日emo','random_img':'随机美图','random_waifu':'每日老婆','persona':'AI人设','feedback':'问题反馈','gift':'赠送碎片','query':'背包查询','planet':'星球养成','profile':'星空名片'}
    features = FEATURE_SWITCHES
    return jsonify({name_map.get(k,k): v for k,v in features.items()})

@app.route('/api/toggle', methods=['POST'])
def api_toggle():
    data = request.json
    cn = data.get('feature')
    rev = {'签到':'signin','抽卡':'draw','塔罗':'tarot','AI聊天':'aichat','天气':'weather','笑话':'joke','疯狂星期四':'kfc','每日emo':'emo','随机美图':'random_img','每日老婆':'random_waifu','AI人设':'persona','问题反馈':'feedback','赠送碎片':'gift','背包查询':'query','星球养成':'planet','星空名片':'profile'}
    feat = rev.get(cn, cn)
    FEATURE_SWITCHES[feat] = data.get('enabled')
    from core.config import save_config
    save_config()
    return jsonify({'success': True})

def _mask_secret(v):
    """脱敏：空值原样返回；非空只保留前 4 个星号 + 末 4 位"""
    if not v:
        return ''
    s = str(v)
    return '****' + (s[-4:] if len(s) > 4 else s)


@app.route('/api/config')
def api_config():
    sysc = SYSTEM_CONFIG
    email = CONFIG.get("email", {}) or {}
    return jsonify({
        'web_password': _mask_secret(CONFIG.get('web_password', '')),
        'web_desktop_enabled': CONFIG.get('web_desktop_enabled', True),
        'web_auto_open_browser': CONFIG.get('web_auto_open_browser', True),
        'ws_url': CONFIG.get('ws_url', ''),
        'api_key': _mask_secret(CONFIG.get('api_key', '')),
        'base_url': CONFIG.get('base_url', ''),
        'model_name': CONFIG.get('model_name', ''),
        'friend_api_token': _mask_secret(CONFIG.get('friend_api_token', '')),
        'welcome_message': CONFIG.get('welcome_message', ''),
        'bot_qq': CONFIG.get('bot_qq', ''),
        'master_qq': CONFIG.get('master_qq', ''),
        'bot_display_name': CONFIG.get('bot_display_name', ''),
        'currency_name': CONFIG.get('currency_name', '星尘'),
        'app_id': CONFIG.get('app_id', ''),
        'app_secret': _mask_secret(CONFIG.get('app_secret', '')),
        'app_token': _mask_secret(CONFIG.get('app_token', '')),
        'email': {
            'enable': email.get('enable', True),
            'smtp_server': email.get('smtp_server', ''),
            'smtp_port': email.get('smtp_port', 465),
            'sender': email.get('sender', ''),
            'password': _mask_secret(email.get('password', '')),
            'receiver': email.get('receiver', ''),
        },
        'signin_min_reward': sysc.get('signin_min_reward',10),
        'signin_max_reward': sysc.get('signin_max_reward',100),
        'draw_cost': sysc.get('draw_cost',100),
        'tarot_cost': sysc.get('tarot_cost',15),
        'memory_timeout_seconds': MEMORY_CONFIG['timeout_seconds'],
        'memory_max_messages': MEMORY_CONFIG['max_messages_before_summary'],
        'memory_mode': sysc.get('memory_mode', 'ai_summary'),
        'ssr_prob': sysc.get('ssr_prob', 0.05),
        'sr_prob': sysc.get('sr_prob', 0.15),
        'r_prob': sysc.get('r_prob', 0.8),
        'yandere_active_enabled': sysc.get('yandere_active_enabled', True),
        'yandere_active_min_interval': sysc.get('yandere_active_min_interval', 1800),
        'yandere_active_max_interval': sysc.get('yandere_active_max_interval', 10800),
        'yandere_active_cooldown': sysc.get('yandere_active_cooldown', 60),
        'yandere_typing_min': sysc.get('yandere_typing_min', 1.5),
        'yandere_typing_max': sysc.get('yandere_typing_max', 5.0),
        'yandere_active_start_hour': sysc.get('yandere_active_start_hour', 8),
        'yandere_active_end_hour': sysc.get('yandere_active_end_hour', 23),
        'yandere_active_skip_prob': sysc.get('yandere_active_skip_prob', 0.2),
        'yandere_session_max_msgs': sysc.get('yandere_session_max_msgs', 12),
        'yandere_session_max_minutes': sysc.get('yandere_session_max_minutes', 40)
    })

@app.route('/api/config', methods=['POST'])
def api_update_config():
    data = request.json
    key = data.get('key')
    value = data.get('value')
    sysc = SYSTEM_CONFIG
    if key in ['signin_min_reward','signin_max_reward','draw_cost','tarot_cost']:
        sysc[key] = int(value)
    elif key == 'web_password':
        # 脱敏值（**** 开头）说明前端只是回显，不覆盖真实密码
        if str(value).startswith('****'):
            pass
        else:
            CONFIG["web_password"] = str(value)
    elif key == 'web_ui_quality':
        val = str(value).strip().lower()
        CONFIG["web_ui_quality"] = val if val in ('high', 'balanced', 'fast') else 'high'
    elif key == 'web_theme':
        val = str(value).strip().lower()
        CONFIG["web_theme"] = val if val in ('light', 'dark') else 'light'
    elif key in ['web_desktop_enabled', 'web_desktop_disable_gpu', 'web_auto_open_browser']:
        CONFIG[key] = str(value).strip().lower() in ('true', '1', 'yes', 'on')
    elif key in ['bot_display_name', 'currency_name', 'welcome_message']:
        CONFIG[key] = str(value)
    elif key in ['ws_url', 'base_url', 'model_name', 'bot_qq', 'master_qq']:
        CONFIG[key] = str(value)
    elif key in ['api_key', 'friend_api_token']:
        if not str(value).startswith('****'):
            CONFIG[key] = str(value)
    elif key in ['app_id']:
        CONFIG[key] = str(value)
    elif key in ['app_secret', 'app_token']:
        if not str(value).startswith('****'):
            CONFIG[key] = str(value)
    elif key in ['web_port', 'welcome_bonus', 'reconnect_delay', 'max_history', 'reminder_days']:
        CONFIG[key] = int(value)
    elif key.startswith('email_'):
        email = CONFIG.setdefault("email", {})
        sub = key[6:]
        if sub == 'enable':
            email[sub] = str(value).strip().lower() in ('true', '1', 'yes', 'on')
        elif sub == 'smtp_port':
            email[sub] = int(value)
        elif sub == 'password' and str(value).startswith('****'):
            pass
        else:
            email[sub] = str(value)
    elif key == 'memory_timeout_seconds':
        MEMORY_CONFIG['timeout_seconds'] = int(value)
        sysc['memory_timeout_seconds'] = int(value)
    elif key == 'memory_max_messages':
        MEMORY_CONFIG['max_messages_before_summary'] = int(value)
        sysc['memory_max_messages'] = int(value)
    elif key in ['memory_mode', 'ssr_prob', 'sr_prob', 'r_prob', 'yandere_active_enabled',
                 'yandere_active_min_interval', 'yandere_active_max_interval', 'yandere_active_cooldown',
                 'yandere_typing_min', 'yandere_typing_max', 'yandere_active_start_hour',
                 'yandere_active_end_hour', 'yandere_active_skip_prob',
                 'yandere_session_max_msgs', 'yandere_session_max_minutes']:
        if key in ['yandere_active_min_interval', 'yandere_active_max_interval', 'yandere_active_cooldown',
                   'yandere_active_start_hour', 'yandere_active_end_hour',
                   'yandere_session_max_msgs', 'yandere_session_max_minutes']:
            value = int(value)
        elif key in ['yandere_typing_min', 'yandere_typing_max', 'yandere_active_skip_prob']:
            value = float(value)
        elif key in ['yandere_active_enabled']:
            value = str(value).strip().lower() in ('true', '1', 'yes', 'on')
        sysc[key] = value
    from core.config import save_config
    save_config()
    return jsonify({'success': True})

@app.route('/api/personalities')
def api_personalities():
    result = {}
    for name, obj in PERSONALITIES.items():
        result[name] = {"prompt": obj.get("prompt", ""), "type": obj.get("type", "normal")}
    return jsonify(result)

@app.route('/api/personalities', methods=['POST'])
def api_update_personalities():
    data = request.json or {}
    # 兼容前端包装格式 {personalities: {...}} 与裸字典两种写法
    if isinstance(data, dict) and "personalities" in data and isinstance(data["personalities"], dict):
        data = data["personalities"]
    if not isinstance(data, dict) or not data:
        return jsonify({'error': '人设列表为空，已拒绝保存（防止误清空）'}), 400
    new_personalities = {}
    for name, obj in data.items():
        if not name or name == "personalities":
            continue
        if isinstance(obj, dict):
            ptype = obj.get("type", "normal")
            if ptype not in ("normal", "yandere"):
                ptype = "normal"
            new_personalities[name] = {"prompt": obj.get("prompt", ""), "type": ptype}
        else:
            new_personalities[name] = {"prompt": obj, "type": "normal"}
    if not new_personalities:
        return jsonify({'error': '人设列表为空，已拒绝保存（防止误清空）'}), 400
    # 原地更新共享对象，保证 core.config 及各插件引用立即同步
    PERSONALITIES.clear()
    PERSONALITIES.update(new_personalities)
    from core.config import save_config
    save_config()
    return jsonify({'success': True})

@app.route('/api/add_persona', methods=['POST'])
def api_add_persona():
    name = request.json.get('name')
    prompt = request.json.get('prompt')
    ptype = request.json.get('type', 'normal')
    if not name or not prompt:
        return jsonify({'error': '缺少参数'}), 400
    if name in PERSONALITIES:
        return jsonify({'error': '已存在'}), 400
    PERSONALITIES[name] = {"prompt": prompt, "type": ptype}
    from core.config import save_config
    save_config()
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    signin_data = {}
    stardust_list = []
    cards_list = []
    tier_dist = {t: 0 for t in ['SSR', 'SR', 'R']}
    total_users = 0
    for f in os.listdir(CONFIG["users_dir"]):
        if not f.endswith(".json"):
            continue
        total_users += 1
        try:
            data = get_cached_user(f[:-5])
        except Exception:
            continue
        last = data.get('last_signin')
        if last:
            signin_data[last[:10]] = signin_data.get(last[:10], 0) + 1
        stardust_list.append(data.get('stardust', 0))
        cards = data.get('cards', [])
        cards_list.append(len(cards))
        for card in cards:
            tier = str(card).split('-')[0].strip().upper()
            if tier in tier_dist:
                tier_dist[tier] += 1

    # 近 7 天签到趋势（缺的天补 0，保证曲线完整）
    trend = []
    for i in range(6, -1, -1):
        d = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
        trend.append({'date': d[5:], 'count': signin_data.get(d, 0)})

    # 星尘分布（含 5000+ 兜底桶）
    ranges = [0, 50, 100, 500, 1000, 5000]
    labels = ['0-50', '51-100', '101-500', '501-1000', '1000-5000', '5000+']
    dist = [0] * len(labels)
    for sd in stardust_list:
        idx = len(labels) - 1
        for i in range(len(ranges) - 1):
            if ranges[i] <= sd < ranges[i + 1]:
                idx = i
                break
        dist[idx] += 1

    signed_today = signin_data.get(today, 0)
    return jsonify({
        'total_users': total_users,
        'total_stardust': sum(stardust_list),
        'total_cards': sum(cards_list),
        'signed_today': signed_today,
        'signin_trend': trend,
        'stardust_distribution': dist,
        'range_labels': labels,
        'tier_distribution': tier_dist,
    })

@app.route('/api/export')
def api_export():
    typ = request.args.get('type', 'users')
    output = io.StringIO()
    if typ == 'users':
        writer = csv.writer(output)
        writer.writerow(['QQ号','星尘碎片','卡牌数量','最后签到'])
        for f in os.listdir(CONFIG["users_dir"]):
            if f.endswith(".json"):
                uid = f[:-5]
                data = get_cached_user(uid)
                writer.writerow([uid, data.get('stardust',0), len(data.get('cards',[])), data.get('last_signin','')])
        filename = 'users_export.csv'
    elif typ == 'signin':
        writer = csv.writer(output)
        writer.writerow(['QQ号','最后签到时间'])
        for f in os.listdir(CONFIG["users_dir"]):
            if f.endswith(".json"):
                uid = f[:-5]
                data = get_cached_user(uid)
                writer.writerow([uid, data.get('last_signin','')])
        filename = 'signin_export.csv'
    else:
        return jsonify({'error':'无效类型'}),400
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=filename)

@app.route('/api/providers')
def api_providers():
    provs = get_all_providers()
    today = datetime.now().date().isoformat()
    result = []
    for p in provs:
        used = p.get('used_today',0) if p.get('last_reset_date') == today else 0
        result.append({
            'id': p.get('id'),
            'name': p.get('name'),
            'model_name': p.get('model_name'),
            'priority': p.get('priority',100),
            'enabled': p.get('enabled',True),
            'max_requests_per_day': p.get('max_requests_per_day',0),
            'used_today': used,
            'fail_count': p.get('fail_count',0),
            'is_public_welfare': p.get('is_public_welfare',False),
            'provider_name': p.get('provider_name',''),
            'admin_url': p.get('admin_url','')
        })
    return jsonify(result)

def _valid_public_url(url):
    """只允许 http/https 且非本机/内网/云元数据地址，防 SSRF"""
    try:
        from urllib.parse import urlparse
        u = urlparse(str(url))
        if u.scheme not in ('http', 'https') or not u.netloc:
            return False
        host = u.hostname or ''
        if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return False
        if host.endswith('.internal') or host.endswith('.local'):
            return False
        # 常见云元数据地址
        if host == '169.254.169.254' or host == 'metadata.google.internal':
            return False
        import ipaddress
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        except ValueError:
            pass  # 域名，交由 DNS 解析层判断
        return True
    except Exception:
        return False


@app.route('/api/provider/<int:pid>')
def api_provider_detail(pid):
    for p in get_all_providers():
        if p.get('id') == pid:
            return jsonify({
                'id': p['id'],
                'name': p['name'],
                'api_key': _mask_secret(p.get('api_key', '')),
                'base_url': p.get('base_url',''),
                'model_name': p.get('model_name',''),
                'priority': p.get('priority',100),
                'max_requests_per_day': p.get('max_requests_per_day',0),
                'is_public_welfare': p.get('is_public_welfare',False),
                'provider_name': p.get('provider_name',''),
                'admin_url': p.get('admin_url','')
            })
    return jsonify({'error':'Not found'}),404

@app.route('/api/update_provider', methods=['POST'])
def api_update_provider():
    data = request.json
    provs = get_all_providers()
    pid = data.get('id')
    new_url = data.get('base_url', '')
    if new_url and not _valid_public_url(new_url):
        return jsonify({'success': False, 'error': 'base_url 必须是公网 http/https 地址'}), 400
    for p in provs:
        if p.get('id') == pid:
            new_key = data.get('api_key', '')
            if str(new_key).startswith('****'):
                new_key = p.get('api_key', '')
            p.update({
                'name': data.get('name', p.get('name', '')),
                'api_key': new_key,
                'base_url': new_url or p.get('base_url', ''),
                'model_name': data.get('model_name', p.get('model_name', '')),
                'priority': data.get('priority', p.get('priority', 100)),
                'max_requests_per_day': data.get('max_requests_per_day', 0),
                'is_public_welfare': data.get('is_public_welfare', False),
                'provider_name': data.get('provider_name', ''),
                'admin_url': data.get('admin_url', '')
            })
            break
    save_providers(provs)
    return jsonify({'success':True})

@app.route('/api/update_priority', methods=['POST'])
def api_update_priority():
    data = request.json
    provs = get_all_providers()
    for p in provs:
        if p.get('id') == data['id']:
            p['priority'] = data['priority']
            break
    save_providers(provs)
    return jsonify({'success':True})

@app.route('/api/toggle_api', methods=['POST'])
def api_toggle_api():
    data = request.json
    provs = get_all_providers()
    for p in provs:
        if p.get('id') == data['id']:
            p['enabled'] = data['enabled']
            break
    save_providers(provs)
    return jsonify({'success':True})

@app.route('/api/delete_api', methods=['POST'])
def api_delete_api():
    data = request.json
    provs = get_all_providers()
    provs = [p for p in provs if p.get('id') != data['id']]
    save_providers(provs)
    return jsonify({'success':True})

@app.route('/api/test_api', methods=['POST'])
def api_test_api():
    data = request.json
    provs = get_all_providers()
    p = next((x for x in provs if x.get('id') == data['id']), None)
    if not p:
        return jsonify({'success':False,'message':'API不存在'})
    try:
        import openai
        client = openai.OpenAI(api_key=p.get('api_key'), base_url=p.get('base_url'), timeout=10)
        resp = client.chat.completions.create(model=p['model_name'], messages=[{"role":"user","content":"Hello"}])
        if resp.choices:
            return jsonify({'success':True,'message':'测试成功'})
        return jsonify({'success':False,'message':'空响应'})
    except Exception as e:
        return jsonify({'success':False,'message':str(e)})

@app.route('/api/add_provider', methods=['POST'])
def api_add_provider():
    data = request.json
    if not _valid_public_url(data.get('base_url', '')):
        return jsonify({'success': False, 'error': 'base_url 必须是公网 http/https 地址'}), 400
    provs = get_all_providers()
    new_id = max([p.get('id',0) for p in provs], default=0) + 1
    new_provider = {
        'id': new_id,
        'name': data['name'],
        'api_key': data.get('api_key',''),
        'base_url': data['base_url'],
        'model_name': data['model_name'],
        'priority': data.get('priority',100),
        'max_requests_per_day': data.get('max_requests_per_day',0),
        'enabled': True,
        'used_today': 0,
        'fail_count': 0,
        'last_reset_date': None,
        'is_public_welfare': data.get('is_public_welfare',False),
        'auth_type': 'bearer',
        'timeout': 30,
        'provider_name': data.get('provider_name',''),
        'admin_url': data.get('admin_url','')
    }
    provs.append(new_provider)
    save_providers(provs)
    return jsonify({'success':True})

@app.route('/api/menu_texts')
def api_menu_texts():
    default_texts = {
        'signin': '签到 - 每日签到获取星尘碎片',
        'draw': '抽卡 / 十连抽 - 消耗100/1000碎片抽卡（十连有额外奖励）',
        'tarot': '塔罗 [问题] - 消耗15碎片占卜运势',
        'weather': '天气 城市名 - 查询实时天气',
        'joke': '笑话 - 随机笑话（每次不同）',
        'kfc': '疯狂星期四 - 生成V我50段子',
        'emo': 'emo - 深夜emo语录',
        'random_img': '随机美图 - 随机二次元图片',
        'random_waifu': '每日老婆 - 每日老婆图片',
        'persona': '切换人设 [名称] / 可用人设 - AI人设管理',
        'gift': '赠送 @某人 数量 - 赠送星尘碎片',
        'query': '背包 / 查询 / 碎片 - 查看资产',
        'planet': '领养星球 / 照料星球 / 拜访好友 - 养一颗自己的星球',
        'profile': '我的名片 - 查看自己的星空名片',
        'feedback': '反馈 内容 - 提交建议',
        'aichat': '@机器人 任意文字 - AI聊天'
    }
    result = {}
    for k, default in default_texts.items():
        result[k] = CUSTOM_MENU_TEXTS.get(k, default)
    return jsonify(result)

@app.route('/api/update_menu_text', methods=['POST'])
def api_update_menu_text():
    data = request.json
    feature = data.get('feature')
    text = data.get('text')
    if not feature:
        return jsonify({'success': False, 'error': '参数错误'}), 400
    if not text.strip():
        CUSTOM_MENU_TEXTS.pop(feature, None)
    else:
        CUSTOM_MENU_TEXTS[feature] = text.strip()
    from core.config import save_config
    save_config()
    return jsonify({'success': True})

@app.route('/api/yandere_whitelist', methods=['GET'])
def get_yandere_whitelist():
    with open(CONFIG["config_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data.get("yandere_whitelist", []))

@app.route('/api/yandere_whitelist/add', methods=['POST'])
def add_yandere_whitelist():
    qq = request.json.get('qq')
    if not qq or not qq.isdigit():
        return jsonify({'success': False, 'error': '无效的QQ号'}), 400
    with open(CONFIG["config_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    whitelist = data.get("yandere_whitelist", [])
    if qq not in whitelist:
        whitelist.append(qq)
        data["yandere_whitelist"] = whitelist
        with open(CONFIG["config_file"], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'QQ号已在白名单中'})

@app.route('/api/yandere_whitelist/remove', methods=['POST'])
def remove_yandere_whitelist():
    qq = request.json.get('qq')
    if not qq:
        return jsonify({'success': False, 'error': '缺少参数'}), 400
    with open(CONFIG["config_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    whitelist = data.get("yandere_whitelist", [])
    if qq in whitelist:
        whitelist.remove(qq)
        data["yandere_whitelist"] = whitelist
        with open(CONFIG["config_file"], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'QQ号不在白名单中'})

# ============ NapCat 管理 ============

def _find_napcat_webui_json():
    """定位 NapCat webui.json（含端口/登录令牌）。napcat_exe 目录已知则从其推断，否则搜索常见位置"""
    candidates = []
    exe = CONFIG.get("napcat_exe", "")
    if exe:
        base = os.path.dirname(os.path.dirname(exe))  # bootmain/.. -> napcat 根
        candidates.append(os.path.join(base, "NapCat*Shell"))
        candidates.append(base)
    candidates.append("D:\\napcat\\NapCat*Shell")
    candidates.append(os.path.expanduser("~\\napcat\\NapCat*Shell"))
    for c in candidates:
        for p in sorted(glob.glob(os.path.join(c, "versions", "*", "resources", "app", "napcat", "config", "webui.json")), reverse=True):
            if os.path.exists(p):
                return p
    return None


def _napcat_webui_info():
    """返回 NapCat WebUI 信息（端口/令牌/地址），读不到返回 None"""
    p = _find_napcat_webui_json()
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        port = int(d.get("port", 6099))
        token = str(d.get("token", "") or "")
        return {"port": port, "token": token,
                "url": "http://127.0.0.1:{}/webui?token={}".format(port, token)}
    except Exception:
        return None


def _napcat_exe_cached():
    """获取 NapCat 启动器路径：优先配置值；缺失/失效时自动扫描，找到则回写配置"""
    exe = find_exe(CONFIG.get("napcat_exe", ""))
    if exe and exe != CONFIG.get("napcat_exe", ""):
        CONFIG["napcat_exe"] = exe
        try:
            from core.config import save_config
            save_config()
        except Exception:
            pass
    return exe


def _napcat_running():
    """NapCat 是否在运行：启动器进程或带 NapCat 标记的 QQ 进程"""
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = p.info.get("name") or ""
            if name == "NapCatWinBootMain.exe":
                return True
            if name == "QQ.exe" and "--enable-logging" in " ".join(p.cmdline()):
                return True
        except Exception:
            pass
    return False


def _napcat_webui_ready(port, timeout=2):
    try:
        urllib.request.urlopen("http://127.0.0.1:{}/webui".format(port), timeout=timeout)
        return True
    except Exception:
        return False


@app.route('/api/napcat/status')
def api_napcat_status():
    info = _napcat_webui_info()
    running = _napcat_running()
    port = info["port"] if info else None
    ready = _napcat_webui_ready(port) if port else False
    exe = _napcat_exe_cached()
    return jsonify({
        'running': running,
        'ready': ready,
        'port': port,
        'token': info["token"] if info else "",
        'url': info["url"] if info else None,
        'exe': exe or ""
    })


@app.route('/api/napcat/start', methods=['POST'])
def api_napcat_start():
    """启动 NapCat：快捷登录机器人 QQ，若已在运行则直接返回"""
    exe = _napcat_exe_cached()
    if not exe:
        return jsonify({'success': False, 'error': '未找到 NapCatWinBootMain.exe（已自动扫描常见位置），请确认 NapCat 已安装'}), 400
    if _napcat_running():
        return jsonify({'success': True, 'already': True})
    qq = CONFIG.get("napcat_qq") or CONFIG.get("bot_qq") or ""
    if not qq:
        return jsonify({'success': False, 'error': '未配置机器人 QQ（napcat_qq / bot_qq）'}), 400
    try:
        subprocess.Popen([exe, str(qq)], cwd=os.path.dirname(exe))
        return jsonify({'success': True, 'message': 'NapCat 启动中...'})
    except Exception as e:
        return jsonify({'success': False, 'error': '启动失败：' + str(e)}), 500


@app.route('/api/restart', methods=['POST'])
def api_restart():
    """一键重启：1 秒后在此进程外拉起新的 main.py，然后强制退出当前进程"""
    import subprocess
    from pathlib import Path
    main_path = Path(CONFIG["config_file"]).parent.parent / "main.py"
    if not main_path.exists():
        return jsonify({'error': '找不到 main.py'}), 500

    def _do_restart():
        time.sleep(1.0)
        try:
            from core.database import flush_all
            flush_all()   # 落盘所有待写数据，避免重启丢最后几秒的修改
            env = dict(os.environ)
            env["QUNXING_NO_UI"] = "1"   # 后台重启：不弹桌面窗口/浏览器，界面在原网页恢复
            subprocess.Popen([sys.executable, str(main_path)],
                             cwd=str(main_path.parent), env=env)
            print(">>> 重启中：已拉起新进程，退出旧进程")
        except Exception as e:
            print(f"重启失败: {e}")
            return
        os._exit(0)

    threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify({'success': True, 'message': '正在重启...'})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """停止机器人：落盘数据后退出进程（不弹窗口，网页提示即可）"""
    import os

    def _do_stop():
        time.sleep(0.8)
        try:
            from core.database import flush_all
            flush_all()
        except Exception:
            pass
        print(">>> 机器人已停止")
        os._exit(0)

    threading.Thread(target=_do_stop, daemon=True).start()
    return jsonify({'success': True, 'message': '正在停止...'})

def start_web_server():
    redirect_stdout_to_queue()
    threading.Thread(target=broadcast_log, daemon=True).start()
    socketio.run(app, host='127.0.0.1', port=CONFIG["web_port"], debug=False, use_reloader=False)