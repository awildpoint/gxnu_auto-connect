import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

import pystray
import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import messagebox, scrolledtext, ttk


OPERATORS = ["校园网", "移动", "联通", "电信"]


class CampusNetworkGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("校园网自动认证工具")
        self.root.geometry("620x420")
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self.base_dir = os.path.dirname(
            os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        )
        self.resource_dir = getattr(
            sys,
            "_MEIPASS",
            os.path.dirname(os.path.abspath(__file__)),
        )
        self.config_file = os.path.join(self.base_dir, "config.json")
        self.log_file = os.path.join(self.base_dir, "log.txt")

        self.set_window_icon()

        self.config = {}
        self.running = True
        self.closing = False
        self.online_status = "未检测"
        self.last_check_time = ""

        self.login_lock = threading.Lock()
        self.tray_lock = threading.Lock()

        self.tray_icon = None
        self.tray_thread = None
        self.tray_icon_created = False

        self.create_gui()
        self.ensure_files_exist()
        self.init_config()
        self.refresh_log()
        self.start_monitoring()

    def resource_path(self, filename):
        bundled_path = os.path.join(self.resource_dir, filename)
        if os.path.exists(bundled_path):
            return bundled_path
        return os.path.join(self.base_dir, filename)

    def set_window_icon(self):
        icon_path = self.resource_path("gxnu.ico")
        if not os.path.exists(icon_path):
            return

        try:
            self.root.iconbitmap(icon_path)
        except tk.TclError:
            pass

    def ensure_files_exist(self):
        if not os.path.exists(self.config_file):
            with open(self.config_file, "w", encoding="utf-8") as file:
                json.dump(self.default_config(), file, indent=4, ensure_ascii=False)

        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as file:
                file.write("")

    def default_config(self):
        return {
            "account": "",
            "password": "",
            "operator": 0,
            "v4ip": "",
            "login_url": "https://yc.gxnu.edu.cn/drcom/login",
        }

    def create_gui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        status_frame = ttk.Frame(notebook)
        config_frame = ttk.Frame(notebook)
        log_frame = ttk.Frame(notebook)

        notebook.add(status_frame, text="  状态  ")
        notebook.add(config_frame, text="  配置  ")
        notebook.add(log_frame, text="  日志  ")

        self.create_status_tab(status_frame)
        self.create_config_tab(config_frame)
        self.create_log_tab(log_frame)

    def create_status_tab(self, parent):
        status_info = ttk.LabelFrame(parent, text="当前状态", padding=10)
        status_info.pack(fill="x", padx=5, pady=5)

        ttk.Label(status_info, text="账号:").grid(row=0, column=0, sticky="w", pady=2)
        self.account_label = ttk.Label(status_info, text="未设置")
        self.account_label.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(status_info, text="运营商:").grid(row=1, column=0, sticky="w", pady=2)
        self.operator_label = ttk.Label(status_info, text="未设置")
        self.operator_label.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(status_info, text="IP 地址:").grid(row=2, column=0, sticky="w", pady=2)
        self.ip_label = ttk.Label(status_info, text="未设置")
        self.ip_label.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(status_info, text="联网状态:").grid(row=3, column=0, sticky="w", pady=2)
        self.status_label = ttk.Label(status_info, text=self.online_status)
        self.status_label.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(status_info, text="检测时间:").grid(row=4, column=0, sticky="w", pady=2)
        self.time_label = ttk.Label(status_info, text=self.last_check_time)
        self.time_label.grid(row=4, column=1, sticky="w", pady=2)

        control_frame = ttk.Frame(parent)
        control_frame.pack(fill="x", padx=5, pady=10)

        ttk.Button(control_frame, text="手动检测", command=self.manual_check).pack(side="left", padx=5)
        ttk.Button(control_frame, text="立即认证", command=self.manual_login).pack(side="left", padx=5)
        ttk.Button(control_frame, text="最小化到托盘", command=self.minimize_to_tray).pack(
            side="right", padx=5
        )

    def create_config_tab(self, parent):
        config_edit = ttk.LabelFrame(parent, text="认证配置", padding=10)
        config_edit.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Label(config_edit, text="账号:").grid(row=0, column=0, sticky="w", pady=5)
        self.account_entry = ttk.Entry(config_edit, width=30)
        self.account_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(config_edit, text="密码:").grid(row=1, column=0, sticky="w", pady=5)
        self.password_entry = ttk.Entry(config_edit, width=30, show="*")
        self.password_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(config_edit, text="运营商:").grid(row=2, column=0, sticky="w", pady=5)
        self.operator_var = tk.StringVar(value=OPERATORS[0])
        operator_combo = ttk.Combobox(
            config_edit,
            textvariable=self.operator_var,
            values=OPERATORS,
            state="readonly",
        )
        operator_combo.grid(row=2, column=1, sticky="w", pady=5, padx=5)

        ttk.Label(config_edit, text="IP 地址:").grid(row=3, column=0, sticky="w", pady=5)
        self.ip_entry = ttk.Entry(config_edit, width=30)
        self.ip_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        button_row = ttk.Frame(config_edit)
        button_row.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_row, text="保存配置", command=self.save_config).pack(side="left", padx=5)
        ttk.Button(button_row, text="打开配置文件", command=self.open_config_file).pack(side="left", padx=5)
        ttk.Button(button_row, text="重新加载", command=self.reload_config).pack(side="left", padx=5)

        config_edit.columnconfigure(1, weight=1)

    def create_log_tab(self, parent):
        log_display = ttk.LabelFrame(parent, text="运行日志", padding=10)
        log_display.pack(fill="both", expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_display, height=14, width=70)
        self.log_text.pack(fill="both", expand=True)

        button_row = ttk.Frame(log_display)
        button_row.pack(fill="x", pady=5)

        ttk.Button(button_row, text="打开日志文件", command=self.open_log_file).pack(side="left", padx=5)
        ttk.Button(button_row, text="清空日志", command=self.clear_log).pack(side="left", padx=5)
        ttk.Button(button_row, text="刷新日志", command=self.refresh_log).pack(side="left", padx=5)

    def init_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as file:
                self.config = json.load(file)
        except Exception:
            self.config = self.default_config()
            with open(self.config_file, "w", encoding="utf-8") as file:
                json.dump(self.config, file, indent=4, ensure_ascii=False)

        self.config.setdefault("login_url", "https://yc.gxnu.edu.cn/drcom/login")
        self.config.setdefault("operator", 0)
        self.update_display()

    def save_config(self):
        account = self.account_entry.get().strip()
        password = self.password_entry.get().strip()
        operator = self.operator_var.get().strip()
        v4ip = self.ip_entry.get().strip()

        if not account:
            messagebox.showerror("错误", "请输入账号")
            return
        if not password:
            messagebox.showerror("错误", "请输入密码")
            return
        if not v4ip:
            messagebox.showerror("错误", "请输入 IP 地址")
            return

        operator_index = OPERATORS.index(operator) if operator in OPERATORS else 0
        self.config.update(
            {
                "account": account,
                "password": password,
                "operator": operator_index,
                "v4ip": v4ip,
            }
        )

        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.config, file, indent=4, ensure_ascii=False)

        self.update_display()
        self.log_message("配置已保存")
        messagebox.showinfo("提示", "配置已保存")

    def update_display(self):
        self.account_entry.delete(0, tk.END)
        self.account_entry.insert(0, self.config.get("account", ""))

        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, self.config.get("password", ""))

        operator_index = self.config.get("operator", 0)
        if not isinstance(operator_index, int) or operator_index >= len(OPERATORS):
            operator_index = 0
        self.operator_var.set(OPERATORS[operator_index])

        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, self.config.get("v4ip", ""))

        self.account_label.config(text=self.config.get("account", "未设置"))
        self.operator_label.config(text=self.operator_var.get())
        self.ip_label.config(text=self.config.get("v4ip", "未设置"))

    def update_status_display(self, status_text, check_time):
        def _update():
            if self.closing:
                return
            try:
                if self.root.winfo_exists():
                    self.status_label.config(text=status_text)
                    self.time_label.config(text=check_time)
            except tk.TclError:
                pass

        self.schedule_ui(_update)

    def schedule_ui(self, callback):
        if self.closing:
            return False

        try:
            self.root.after(0, callback)
            return True
        except (tk.TclError, RuntimeError):
            return False

    def check_online(self):
        try:
            result = subprocess.run(
                ["ping", "-n", "2", "-w", "3000", "www.baidu.com"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            online = result.returncode == 0
            status_text = "已联网" if online else "未联网"
            check_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.online_status = status_text
            self.last_check_time = check_time
            self.update_status_display(status_text, check_time)
            self.log_message(f"网络检测结果: {status_text}")
            return online
        except Exception as exc:
            self.log_message(f"网络检测失败: {exc}")
            return False

    def build_login_url(self):
        params = {
            "callback": "dr1004",
            "DDDDD": self.config.get("account", ""),
            "upass": self.config.get("password", ""),
            "0MKKey": "123456",
            "R1": "0",
            "R2": "",
            "R3": str(self.config.get("operator", 0)),
            "R6": "0",
            "para": "00",
            "v4ip": self.config.get("v4ip", ""),
            "v6ip": "",
            "terminal_type": "1",
            "lang": "zh-cn",
            "jsVersion": "4.2.2",
            "v": "1171",
        }
        return f"{self.config['login_url']}?{urlencode(params)}"

    def parse_login_response(self, response_text):
        response_text = response_text.strip()
        if not response_text:
            return False, "接口返回空响应"

        payload_text = response_text
        jsonp_match = re.fullmatch(r"[\w$.]+\s*\((.*)\)\s*;?", response_text, re.DOTALL)
        if jsonp_match:
            payload_text = jsonp_match.group(1).strip()

        payload = None
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            pass

        failure_keywords = (
            "error",
            "fail",
            "denied",
            "refused",
            "失败",
            "错误",
            "拒绝",
            "无效",
            "欠费",
            "已达上限",
        )
        success_keywords = ("success", "认证成功", "登录成功", "登陆成功")
        response_lower = response_text.lower()

        if isinstance(payload, dict):
            result = payload.get("result")
            if result is not None:
                if result is True or str(result).strip().lower() in {"1", "success", "ok"}:
                    return True, str(payload.get("msg") or payload.get("message") or "认证成功")
                return False, str(payload.get("msg") or payload.get("message") or f"result={result}")

            success = payload.get("success")
            if success is not None:
                if success is True or str(success).strip().lower() in {"1", "true", "success", "ok"}:
                    return True, str(payload.get("msg") or payload.get("message") or "认证成功")
                return False, str(payload.get("msg") or payload.get("message") or "认证失败")

            if "ret_code" in payload:
                ret_code = str(payload["ret_code"]).strip()
                detail = str(payload.get("msg") or payload.get("message") or f"ret_code={ret_code}")
                return ret_code == "0", detail

        if any(keyword in response_lower for keyword in failure_keywords):
            return False, response_text[:120]
        if any(keyword in response_lower for keyword in success_keywords):
            return True, response_text[:120]

        return False, f"无法确认认证结果: {response_text[:120]}"

    def login(self):
        if not self.login_lock.acquire(blocking=False):
            self.log_message("认证任务已在执行，本次请求已跳过")
            return False

        try:
            if not all([self.config.get("account"), self.config.get("password"), self.config.get("v4ip")]):
                self.log_message("认证失败: 配置不完整，请先保存账号、密码和 IP")
                return False

            login_url = self.build_login_url()

            # 认证请求显式绕过系统代理，避免代理开启时把校园网认证流量错误转发出去。
            opener = build_opener(ProxyHandler({}))
            request = Request(
                login_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "*/*",
                    "Connection": "close",
                },
            )

            with opener.open(request, timeout=15) as response:
                response_text = response.read().decode("utf-8", errors="ignore").strip()

            success, detail = self.parse_login_response(response_text)
            if success:
                self.log_message(f"认证成功: {detail}")
                return True

            self.log_message(f"认证失败: {detail}")
            return False
        except Exception as exc:
            self.log_message(f"认证异常: {exc}")
            return False
        finally:
            self.login_lock.release()

    def start_monitoring(self):
        def monitoring_loop():
            while self.running:
                try:
                    if not self.check_online():
                        self.log_message("检测到未联网，开始尝试自动认证")
                        if self.login():
                            self.log_message("自动认证已完成")
                        else:
                            self.log_message("自动认证失败")

                    for _ in range(300):
                        if not self.running:
                            break
                        time.sleep(1)
                except Exception as exc:
                    self.log_message(f"监控线程异常: {exc}")
                    time.sleep(60)

        threading.Thread(target=monitoring_loop, daemon=True).start()

    def manual_check(self):
        threading.Thread(target=self.check_online, daemon=True).start()

    def manual_login(self):
        threading.Thread(target=self.login, daemon=True).start()

    def open_config_file(self):
        if os.path.exists(self.config_file):
            os.startfile(self.config_file)
        else:
            messagebox.showwarning("提示", "配置文件不存在")

    def open_log_file(self):
        if os.path.exists(self.log_file):
            os.startfile(self.log_file)
        else:
            messagebox.showwarning("提示", "日志文件不存在")

    def refresh_log(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as file:
                content = file.read()
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert("1.0", content)
        except Exception as exc:
            messagebox.showerror("错误", f"刷新日志失败: {exc}")

    def clear_log(self):
        if not messagebox.askyesno("确认", "确定要清空日志吗？"):
            return

        try:
            with open(self.log_file, "w", encoding="utf-8") as file:
                file.write("")
            self.log_text.delete("1.0", tk.END)
            self.log_message("日志已清空")
        except Exception as exc:
            messagebox.showerror("错误", f"清空日志失败: {exc}")

    def reload_config(self):
        self.init_config()
        messagebox.showinfo("提示", "配置已重新加载")

    def log_message(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        try:
            with open(self.log_file, "a", encoding="utf-8") as file:
                file.write(log_entry)
        except Exception:
            pass

        def _append():
            if self.closing:
                return
            try:
                if self.root.winfo_exists():
                    self.log_text.insert(tk.END, log_entry)
                    self.log_text.see(tk.END)
            except tk.TclError:
                pass

        self.schedule_ui(_append)

    def create_tray_image(self):
        icon_path = self.resource_path("gxnu.ico")
        if os.path.exists(icon_path):
            try:
                with Image.open(icon_path) as image:
                    return image.convert("RGBA")
            except Exception:
                pass

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=(0, 120, 215, 255))
        draw.ellipse((20, 20, 44, 44), fill=(255, 255, 255, 255))
        return image

    def create_tray_icon(self):
        def show_window(icon=None, item=None):
            self.schedule_ui(self.restore_from_tray)

        def exit_app(icon=None, item=None):
            self.schedule_ui(self.quit_application)

        tray_icon = pystray.Icon(
            "campus_network",
            self.create_tray_image(),
            "校园网自动认证工具",
            pystray.Menu(
                pystray.MenuItem("显示窗口", show_window, default=True),
                pystray.MenuItem("退出", exit_app),
            ),
        )

        return tray_icon

    def run_tray_icon(self, tray_icon):
        try:
            tray_icon.run()
        except Exception as exc:
            self.log_message(f"托盘图标运行失败: {exc}")
        finally:
            current_thread = threading.current_thread()
            with self.tray_lock:
                if self.tray_icon is tray_icon:
                    self.tray_icon = None
                    self.tray_icon_created = False
                if self.tray_thread is current_thread:
                    self.tray_thread = None

    def ensure_tray_icon_running(self):
        with self.tray_lock:
            if self.closing:
                return

            tray_icon = self.tray_icon
            tray_thread = self.tray_thread

            if tray_icon is None or tray_thread is None or not tray_thread.is_alive():
                tray_icon = self.create_tray_icon()
                tray_thread = threading.Thread(
                    target=self.run_tray_icon,
                    args=(tray_icon,),
                    daemon=True,
                )
                self.tray_icon = tray_icon
                self.tray_thread = tray_thread
                self.tray_icon_created = True
                tray_thread.start()
                return

        try:
            tray_icon.visible = True
        except Exception as exc:
            self.log_message(f"显示托盘图标失败: {exc}")

    def minimize_to_tray(self):
        self.ensure_tray_icon_running()
        self.root.withdraw()
        self.log_message("窗口已最小化到托盘")

    def restore_from_tray(self):
        if self.closing:
            return

        with self.tray_lock:
            tray_icon = self.tray_icon
            self.tray_icon = None
            self.tray_thread = None
            self.tray_icon_created = False

        if tray_icon is not None:
            try:
                tray_icon.stop()
            except Exception as exc:
                self.log_message(f"停止托盘图标失败: {exc}")

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.log_message("窗口已从托盘恢复")

    def quit_application(self):
        if not messagebox.askyesno("确认退出", "确定要退出校园网自动认证工具吗？"):
            return

        self.running = False
        self.closing = True

        with self.tray_lock:
            tray_icon = self.tray_icon
            self.tray_icon = None
            self.tray_thread = None
            self.tray_icon_created = False

        if tray_icon is not None:
            try:
                tray_icon.stop()
            except Exception:
                pass

        self.root.quit()
        self.root.destroy()

    def run(self):
        self.log_message("校园网自动认证工具已启动")
        self.root.mainloop()


def main():
        app = CampusNetworkGUI()
        app.run()


if __name__ == "__main__":
    main()
