# core/ws_client.py
import websocket
import json
import threading
import time
import re
import uuid
from core.config import CONFIG, FEATURE_SWITCHES, SYSTEM_CONFIG, MEMORY_CONFIG, load_config, currency_name
from core.database import (
    get_cached_user, update_cached_user, unload_inactive_users,
    get_current_persona, set_current_persona, get_persona_type,
    get_yandere_last_interact, set_yandere_last_interact,
    add_stardust, is_friend, set_friend_cache, record_nickname
)
from core.ai import call_ai_with_fallback, call_with_messages
from core.plugin_manager import PluginManager
from core.utils import prevent_sleep

# 全局变量
main_ws = None
should_reconnect = True
reconnect_attempts = 0
connected_successfully = False
start_time = time.time()
ai_health_state = True
last_reminder_time = time.time()
_last_member_fetch = {}
reminder_check_interval = 3600
last_group_increase = {}
processed_messages = {}
MESSAGE_CACHE_EXPIRE = 5
# WS action 回包匹配
_pending_actions = {}
_pending_actions_lock = threading.Lock()
_action_cond = threading.Condition(_pending_actions_lock)
_send_lock = threading.Lock()

class Bot:
    def __init__(self):
        self.ws = None
        self.plugin_manager = PluginManager(self)

    def send_msg(self, group_id, message):
        data = {"action": "send_group_msg", "params": {"group_id": int(group_id), "message": message}}
        with _send_lock:
            self.ws.send(json.dumps(data, ensure_ascii=False))

    def send_private_msg(self, user_id, message):
        data = {"action": "send_private_msg", "params": {"user_id": int(user_id), "message": message}}
        with _send_lock:
            self.ws.send(json.dumps(data, ensure_ascii=False))

    def send_reply(self, msg_type, group_id, user_qq, message, at_user=False):
        if msg_type == 'group':
            if at_user:
                self.send_msg(group_id, f"[CQ:at,qq={user_qq}] {message}")
            else:
                self.send_msg(group_id, message)
        else:
            self.send_private_msg(user_qq, message)

    def request_action(self, action, params=None, timeout=6):
        """通过已建立的 websocket 发送 OneBot 动作，等待 echo 回包（线程安全）"""
        if self.ws is None:
            return None
        echo = str(uuid.uuid4())
        with _pending_actions_lock:
            _pending_actions[echo] = None
        try:
            with _send_lock:
                self.ws.send(json.dumps({"action": action, "params": params or {}, "echo": echo}))
        except Exception as e:
            print(f"发送动作 {action} 失败: {e}")
            with _pending_actions_lock:
                _pending_actions.pop(echo, None)
            return None
        deadline = time.time() + timeout
        # _action_cond 的底层锁就是 _pending_actions_lock，无需再重复加锁
        with _action_cond:
            while True:
                resp = _pending_actions.get(echo)
                if resp is not None:
                    _pending_actions.pop(echo, None)
                    return resp
                remaining = deadline - time.time()
                if remaining <= 0:
                    _pending_actions.pop(echo, None)
                    return None
                _action_cond.wait(min(remaining, 0.5))

    def refresh_friends(self):
        """通过 ws 拉取好友列表并写入缓存（优于写死的 HTTP token）"""
        resp = self.request_action("get_friend_list", timeout=8)
        if resp and resp.get("status") == "ok" and isinstance(resp.get("data"), list):
            set_friend_cache([str(f["user_id"]) for f in resp["data"]])
            return True
        return False

    def _maybe_fetch_nicknames(self, group_id):
        """每 30 分钟拉一次群成员列表，批量记录昵称（面板用户管理显示真名）"""
        now = time.time()
        if now - _last_member_fetch.get(group_id, 0) < 1800:
            return
        _last_member_fetch[group_id] = now

        def _job():
            try:
                resp = self.request_action("get_group_member_list", {"group_id": group_id}, timeout=8)
                if resp and resp.get("status") == "ok" and isinstance(resp.get("data"), list):
                    for m in resp["data"]:
                        name = m.get("card") or m.get("nickname") or ""
                        if name:
                            record_nickname(m["user_id"], name)
            except Exception:
                pass
        threading.Thread(target=_job, daemon=True).start()

    def process_message(self, msg_type, group_id, user_qq, nickname, raw_message):
        raw_message = raw_message.strip()
        if not raw_message:
            return
        record_nickname(user_qq, nickname)
        is_at_bot = False
        clean_message = re.sub(r'\[CQ:[^]]+\]', '', raw_message).strip()
        if msg_type == 'group':
            at_pattern = f'\\[CQ:at,qq={CONFIG["bot_qq"]}\\]'
            if re.search(at_pattern, raw_message):
                is_at_bot = True
                remaining = re.sub(at_pattern, '', raw_message).strip()
                clean_message = re.sub(r'\[CQ:[^]]+\]', '', remaining).strip()
            else:
                return
        lower_msg = clean_message.lower()

        current_persona = get_current_persona(user_qq)
        if get_persona_type(current_persona) == "yandere":
            set_yandere_last_interact(user_qq, time.time(), current_persona)

        handled = self.plugin_manager.process_message(
            msg_type, group_id, user_qq, nickname,
            raw_message, clean_message, is_at_bot
        )
        if not handled and FEATURE_SWITCHES.get("aichat", True):
            from plugins.aichat import AIChatPlugin
            plugin = AIChatPlugin(self)
            plugin.handle(msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
        except:
            return
        # OneBot 动作回包（带 echo，无 post_type）→ 唤醒等待线程
        if "echo" in data and "post_type" not in data:
            with _pending_actions_lock:
                _pending_actions[data["echo"]] = data
            with _action_cond:
                _action_cond.notify_all()
            return
        if data.get("post_type") == "message":
            msg_id = data.get("message_id")
            if msg_id:
                now = time.time()
                for k in list(processed_messages.keys()):
                    if now - processed_messages[k] > MESSAGE_CACHE_EXPIRE:
                        del processed_messages[k]
                if msg_id in processed_messages:
                    return
                processed_messages[msg_id] = now
        if data.get("post_type") == "message" and data.get("message_type") == "group":
            self._maybe_fetch_nicknames(data["group_id"])
            threading.Thread(target=self.process_message, args=(
                'group', data["group_id"], data["sender"]["user_id"],
                data["sender"]["nickname"], data["raw_message"]
            )).start()
        elif data.get("post_type") == "message" and data.get("message_type") == "private":
            threading.Thread(target=self.process_message, args=(
                'private', None, data["sender"]["user_id"],
                data["sender"]["nickname"], data["raw_message"]
            )).start()
        elif data.get("post_type") == "notice" and data.get("notice_type") == "group_increase":
            group_id = data["group_id"]
            user_id = data["user_id"]
            key = (group_id, user_id)
            now = time.time()
            if key in last_group_increase and now - last_group_increase[key] < 5:
                return
            last_group_increase[key] = now
            add_stardust(user_id, CONFIG["welcome_bonus"])
            bonus = CONFIG["welcome_bonus"]
            msg = (CONFIG.get("welcome_message") or "").strip()
            if not msg:
                msg = "[CQ:at,qq={qq}] 欢迎！送你 {bonus} {currency}。"
            msg = (msg.replace("{qq}", str(user_id))
                      .replace("{bonus}", str(bonus))
                      .replace("{currency}", currency_name()))
            self.send_msg(group_id, msg)

    def on_open(self, ws):
        global main_ws, reconnect_attempts, connected_successfully
        reconnect_attempts = 0
        connected_successfully = True
        main_ws = ws
        self.ws = ws
        print(f"连接成功！{CONFIG.get('system_name', '群星')}系统已就绪。")
        print(f"群主 QQ: {CONFIG['master_qq']}")
        print(f"机器人 QQ: {CONFIG['bot_qq']}")
        print(f"Web UI: http://127.0.0.1:{CONFIG['web_port']}")
        prevent_sleep()
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()
        threading.Thread(target=self.check_ai_health_loop, daemon=True).start()
        threading.Thread(target=self.reminder_thread, daemon=True).start()
        threading.Thread(target=unload_inactive_users, daemon=True).start()
        from plugins.yandere_active import yandere_active_thread
        threading.Thread(target=yandere_active_thread, args=(self,), daemon=True).start()

    def heartbeat_thread(self):
        global should_reconnect
        while should_reconnect:
            time.sleep(30)
            try:
                with _send_lock:
                    self.ws.send(json.dumps({"action": "get_status"}))
            except:
                break

    def check_ai_health_loop(self):
        global ai_health_state
        while should_reconnect:
            time.sleep(3600)
            try:
                test = call_ai_with_fallback("Hello", system_override="友好的AI助手")
                ai_health_state = bool(test)
                if not test:
                    self.send_private_msg(CONFIG["master_qq"], "AI健康检查警告：所有API不可用")
            except:
                ai_health_state = False

    def reminder_thread(self):
        global last_reminder_time
        while should_reconnect:
            time.sleep(reminder_check_interval)
            if time.time() - last_reminder_time >= CONFIG["reminder_days"] * 86400:
                self.send_private_msg(CONFIG["master_qq"], f"请每隔 {CONFIG['reminder_days']} 天重新扫码登录机器人。")
                last_reminder_time = time.time()

    def on_error(self, ws, error):
        print(f"WebSocket错误: {error}")

    def on_close(self, ws, code, reason):
        print(f"连接关闭: {reason} (code: {code})")

    def run(self):
        global should_reconnect, reconnect_attempts, connected_successfully, main_ws
        print("启动机器人...")
        load_config()
        from web.web_server import start_web_server
        threading.Thread(target=start_web_server, daemon=True).start()
        print(f"Web UI: http://127.0.0.1:{CONFIG['web_port']}")
        while should_reconnect:
            try:
                ws = websocket.WebSocketApp(
                    CONFIG["ws_url"],
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                main_ws = ws
                ws.run_forever()
            except KeyboardInterrupt:
                print("用户中断，正在退出...")
                should_reconnect = False
                break
            except Exception as e:
                print(f"连接异常: {e}")
                reconnect_attempts += 1
            if should_reconnect:
                print(f"{CONFIG['reconnect_delay']}秒后重连...（{reconnect_attempts}/{CONFIG['max_reconnect_attempts']}）")
                if reconnect_attempts > CONFIG["max_reconnect_attempts"]:
                    print("重连次数超限，停止重连")
                    should_reconnect = False
                    break
                time.sleep(CONFIG["reconnect_delay"])