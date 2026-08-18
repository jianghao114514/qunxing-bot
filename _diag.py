import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import core.config as cfg
cfg.load_config()

print("SYSTEM_CONFIG yandere keys:")
for k in ("yandere_active_enabled", "yandere_active_min_interval", "yandere_active_max_interval",
          "yandere_active_cooldown", "yandere_active_start_hour", "yandere_active_end_hour",
          "yandere_active_skip_prob"):
    print("  ", k, "=", cfg.SYSTEM_CONFIG.get(k))

data = json.load(open(cfg.CONFIG["config_file"], encoding="utf-8"))
print("yandere_whitelist:", data.get("yandere_whitelist"))

master = str(cfg.CONFIG["master_qq"])
import core.database as db
ud = db.get_cached_user(master)
print("master file:", master)
print("  current_persona:", ud.get("current_persona"))
mems = ud.get("persona_memories", {})
print("  personas:", list(mems.keys()))
for p in mems:
    y = mems[p].get("yandere", {})
    print(f"    {p}: level={y.get('level')} next_active={y.get('next_active_time')} dT={time.time()-y.get('next_active_time',0):.0f}s last_interact={y.get('last_interact_time')} dT={time.time()-y.get('last_interact_time',0):.0f}s")

# 好友检测
print("is_friend(master):", d.is_friend(master))
print("friend list count:", len(d.refresh_friend_list()))