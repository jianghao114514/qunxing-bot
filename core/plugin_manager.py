# core/plugin_manager.py
import os
import sys
import importlib
import inspect
from plugins.base import BasePlugin
from core.group_config import feature_enabled, plugin_feature_key

class PluginManager:
    def __init__(self, bot):
        self.bot = bot
        self.plugins = []
        self.load_plugins()

    def load_plugins(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(base_dir, "plugins")
        if not os.path.isdir(plugins_dir):
            print(f"插件目录不存在: {plugins_dir}")
            return
        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and filename != "base.py":
                self._load_one(plugins_dir, filename)
        self.plugins.sort(key=lambda p: p.priority)

    def _load_one(self, plugins_dir, filename):
        module_name = f"plugins.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BasePlugin) and obj != BasePlugin
                        and getattr(obj, "__module__", "") == module_name):
                    plugin = obj(self.bot)
                    self.plugins.append(plugin)
                    print(f"已加载插件: {plugin.name}")
        except Exception as e:
            print(f"加载插件 {filename} 失败: {e}")

    def reload_plugins(self):
        """热重载：重新加载已改动的插件模块、纳入新增的插件、移除已删除的插件"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(base_dir, "plugins")
        if not os.path.isdir(plugins_dir):
            print("插件目录不存在")
            return []
        removed = [p.name for p in self.plugins]
        self.plugins = []
        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and filename != "base.py":
                module_name = f"plugins.{filename[:-3]}"
                try:
                    module = sys.modules.get(module_name)
                    if module is None:
                        module = importlib.import_module(module_name)
                    else:
                        module = importlib.reload(module)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BasePlugin) and obj != BasePlugin
                                and getattr(obj, "__module__", "") == module_name):
                            plugin = obj(self.bot)
                            self.plugins.append(plugin)
                except Exception as e:
                    print(f"重载插件 {filename} 失败: {e}")
        self.plugins.sort(key=lambda p: p.priority)
        freed = set(removed) - {p.name for p in self.plugins}
        print(f"插件热重载完成：共 {len(self.plugins)} 个插件" +
              (f"，移除 {sorted(freed)}" if freed else ""))
        return self.plugins

    def process_message(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        for plugin in self.plugins:
            if not plugin.enabled:
                continue
            fkey = plugin_feature_key(plugin.name)
            if fkey is not None and not feature_enabled(group_id, fkey):
                continue
            try:
                if plugin.match(msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
                    return plugin.handle(msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot)
            except Exception as e:
                print(f"插件 {plugin.name} 处理出错: {e}")
        return False