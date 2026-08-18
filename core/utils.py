# core/utils.py
import smtplib
import ctypes
import sys
import time
from email.mime.text import MIMEText
from email.utils import formatdate
from core.config import CONFIG

def send_email(subject, body, to_addr=None):
    """发送邮件（用于反馈和测试）"""
    if not CONFIG["email"]["enable"]:
        return False
    if to_addr is None:
        to_addr = CONFIG["email"]["receiver"]
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = CONFIG["email"]["sender"]
        msg["To"] = to_addr
        msg["Date"] = formatdate(localtime=True)
        server = smtplib.SMTP_SSL(CONFIG["email"]["smtp_server"], CONFIG["email"]["smtp_port"])
        server.login(CONFIG["email"]["sender"], CONFIG["email"]["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"发送邮件失败: {e}")
        return False

def prevent_sleep():
    if sys.platform == 'win32':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            print("已阻止系统休眠（屏幕可正常关闭）")
        except Exception as e:
            print(f"防休眠失败: {e}")

def allow_sleep():
    if sys.platform == 'win32':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print("已恢复系统休眠")
        except:
            pass