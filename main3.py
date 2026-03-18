import json
import os
import subprocess
import time
import datetime
import threading
import sys
import pystray
from urllib.parse import quote
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

class CampusNetworkGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("校园网自动认证工具")
        self.root.geometry("600x350")
        self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)
        
        self.config_file = "config.json"
        self.log_file = "log.txt"
        self.config = {}
        self.running = True
        self.online_status = "检测中..."
        self.last_check_time = ""
        self.tray_icon = None
        self.tray_icon_created = False  # 新增：标记托盘图标是否已创建
        
        # 创建界面
        self.create_gui()
        
        # 初始化配置
        self.init_config()
        
        # 启动监控线程
        self.start_monitoring()
    
    def create_gui(self):
        """创建图形用户界面"""
        # 创建选项卡
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 状态标签
        status_frame = ttk.Frame(notebook)
        config_frame = ttk.Frame(notebook)
        log_frame = ttk.Frame(notebook)
        
        notebook.add(status_frame, text="状态监控")
        notebook.add(config_frame, text="配置管理")
        notebook.add(log_frame, text="运行日志")
        
        self.create_status_tab(status_frame)
        self.create_config_tab(config_frame)
        self.create_log_tab(log_frame)
    
    def create_status_tab(self, parent):
        """创建状态监控标签页"""
        # 状态信息框架
        status_info = ttk.LabelFrame(parent, text="当前状态", padding=10)
        status_info.pack(fill='x', padx=5, pady=5)
        
        # 状态信息显示
        ttk.Label(status_info, text="账号:").grid(row=0, column=0, sticky='w', pady=2)
        self.account_label = ttk.Label(status_info, text="未设置")
        self.account_label.grid(row=0, column=1, sticky='w', pady=2)
        
        # 运营商信息
        ttk.Label(status_info, text="运营商:").grid(row=1, column=0, sticky='w', pady=2)
        self.operator_label = ttk.Label(status_info, text="未设置")
        self.operator_label.grid(row=1, column=1, sticky='w', pady=2)
        
        # IP信息
        ttk.Label(status_info, text="IP地址:").grid(row=2, column=0, sticky='w', pady=2)
        self.ip_label = ttk.Label(status_info, text="未设置")
        self.ip_label.grid(row=2, column=1, sticky='w', pady=2)
        
        # 在线状态
        ttk.Label(status_info, text="在线状态:").grid(row=3, column=0, sticky='w', pady=2)
        self.status_label = ttk.Label(status_info, text="检测中...")
        self.status_label.grid(row=3, column=1, sticky='w', pady=2)
        
        # 最后检测时间
        ttk.Label(status_info, text="最后检测:").grid(row=4, column=0, sticky='w', pady=2)
        self.time_label = ttk.Label(status_info, text="")
        self.time_label.grid(row=4, column=1, sticky='w', pady=2)
        
        # 控制按钮
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(control_frame, text="立即检测网络",
                   command=self.manual_check).pack(side='left', padx=5)
        ttk.Button(control_frame, text="立即登录",
                   command=self.manual_login).pack(side='left', padx=5)
        ttk.Button(control_frame, text="退出程序",
                   command=self.quit_application).pack(side='right', padx=5)
        ttk.Button(control_frame, text="最小化到托盘",
                   command=self.minimize_to_tray).pack(side='right', padx=5)
    
    def create_config_tab(self, parent):
        """创建配置管理标签页"""
        config_edit = ttk.LabelFrame(parent, text="编辑配置", padding=10)
        config_edit.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 账号输入
        ttk.Label(config_edit, text="账号:").grid(row=0, column=0, sticky='w', pady=5)
        self.account_entry = ttk.Entry(config_edit, width=30)
        self.account_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=5)
        
        # 密码输入
        ttk.Label(config_edit, text="密码:").grid(row=1, column=0, sticky='w', pady=5)
        self.password_entry = ttk.Entry(config_edit, width=30, show="*")
        self.password_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=5)
        
        # 运营商选择
        ttk.Label(config_edit, text="运营商:").grid(row=2, column=0, sticky='w', pady=5)
        self.operator_var = tk.StringVar()
        operator_combo = ttk.Combobox(config_edit, textvariable=self.operator_var, 
                                    values=["校园网", "移动", "联通", "电信"], state="readonly")
        operator_combo.grid(row=2, column=1, sticky='w', pady=5, padx=5)
        
        # IP地址输入
        ttk.Label(config_edit, text="IP地址:").grid(row=3, column=0, sticky='w', pady=5)
        self.ip_entry = ttk.Entry(config_edit, width=30)
        self.ip_entry.grid(row=3, column=1, sticky='ew', pady=5, padx=5)
        
        # 配置操作按钮
        config_buttons = ttk.Frame(config_edit)
        config_buttons.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(config_buttons, text="保存配置", 
                  command=self.save_config).pack(side='left', padx=5)
        ttk.Button(config_buttons, text="打开配置文件", 
                  command=self.open_config_file).pack(side='left', padx=5)
        ttk.Button(config_buttons, text="重新加载配置", 
                  command=self.reload_config).pack(side='left', padx=5)
        
        config_edit.columnconfigure(1, weight=1)
    
    def create_log_tab(self, parent):
        """创建日志标签页"""
        log_display = ttk.LabelFrame(parent, text="运行日志", padding=10)
        log_display.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_display, height=15)
        self.log_text.pack(fill='both', expand=True)
        
        log_buttons = ttk.Frame(log_display)
        log_buttons.pack(fill='x', pady=5)
        
        ttk.Button(log_buttons, text="打开日志文件", 
                  command=self.open_log_file).pack(side='left', padx=5)
        ttk.Button(log_buttons, text="清空日志", 
                  command=self.clear_log).pack(side='left', padx=5)
        ttk.Button(log_buttons, text="刷新日志", 
                  command=self.refresh_log).pack(side='left', padx=5)
    
    def init_config(self):
        """初始化配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.update_display()
                self.log_message("配置文件加载成功")
            except Exception as e:
                self.log_message(f"配置文件加载失败: {e}")
                self.create_default_config()
        else:
            self.create_default_config()
            messagebox.showinfo("首次运行", "请先完善配置信息")
    
    def create_default_config(self):
        """创建默认配置"""
        self.config = {
            "account": "",
            "password": "",
            "operator": 0,
            "v4ip": "",
            "login_url": "https://yc.gxnu.edu.cn/drcom/login"
        }
        self.save_config()
    
    def save_config(self):
        """保存配置"""
        try:
            # 获取输入值
            account = self.account_entry.get().strip()
            password = self.password_entry.get().strip()
            operator_str = self.operator_var.get().strip()
            v4ip = self.ip_entry.get().strip()
            
            # 验证必填字段
            if not account:
                messagebox.showerror("错误", "账号不能为空！")
                return
            
            if not password:
                messagebox.showerror("错误", "密码不能为空！")
                return
            
            if not v4ip:
                messagebox.showerror("错误", "IP地址不能为空！")
                return
            
            # 处理运营商选择，如果为空则使用默认值
            operators = ["校园网", "移动", "联通", "电信"]
            if operator_str and operator_str in operators:
                operator_index = operators.index(operator_str)
            else:
                operator_index = 0  # 默认使用校园网
                self.operator_var.set("校园网")  # 更新界面显示
            
            # 更新配置
            self.config.update({
                "account": account,
                "password": password,
                "operator": operator_index,
                "v4ip": v4ip
            })
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            self.update_display()
            self.log_message("配置保存成功")
            messagebox.showinfo("成功", "配置保存成功！")
            
        except Exception as e:
            self.log_message(f"配置保存失败: {e}")
            messagebox.showerror("错误", f"配置保存失败: {e}")
    
    def update_display(self):
        """更新界面显示"""
        # 更新输入框
        self.account_entry.delete(0, tk.END)
        self.account_entry.insert(0, self.config.get('account', ''))
        
        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, self.config.get('password', ''))
        
        operator_index = self.config.get('operator', 0)
        operators = ["校园网", "移动", "联通", "电信"]
        self.operator_var.set(operators[operator_index] if operator_index < len(operators) else "校园网")
        
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, self.config.get('v4ip', ''))
        
        # 更新状态标签
        self.account_label.config(text=self.config.get('account', '未设置'))
        self.operator_label.config(text=self.operator_var.get())
        self.ip_label.config(text=self.config.get('v4ip', '未设置'))
    
    def check_online(self):
        """检查网络状态"""
        try:
            # 使用subprocess.run执行ping命令[1,2](@ref)
            result = subprocess.run(
                ['ping', '-n', '2', '-w', '3000', 'www.baidu.com'],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 修复：正确的属性名称是returncode[3,6](@ref)
            online = result.returncode == 0
            status_text = "在线" if online else "离线"
            self.online_status = status_text
            self.last_check_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新界面
            self.status_label.config(text=status_text)
            self.time_label.config(text=self.last_check_time)
            
            self.log_message(f"网络检测: {status_text}")
            return online
        except Exception as e:
            self.log_message(f"网络检测失败: {e}")
            return False
    
    def login(self):
        """执行登录"""
        try:
            if not all([self.config.get('account'), self.config.get('password'), self.config.get('v4ip')]):
                self.log_message("登录失败：配置不完整")
                return False
                
            encoded_password = quote(self.config['password'], safe='')
            login_url = (
                f"{self.config['login_url']}?"
                f"callback=dr1004&DDDDD={self.config['account']}&"
                f"upass={encoded_password}&0MKKey=123456&R1=0&R2=&"
                f"R3={self.config['operator']}&R6=0¶=00&"
                f"v4ip={self.config['v4ip']}&v6ip=&terminal_type=1&"
                f"lang=zh-cn&jsVersion=4.2.2&v=1171&lang=zh"
            )
            
            # 使用subprocess.run执行curl命令[4,7](@ref)
            cmd = ['curl', '-s', login_url]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 修复：使用正确的returncode属性[3](@ref)
            if result.returncode == 0:
                self.log_message("登录命令执行成功")
                return True
            else:
                self.log_message(f"登录命令执行失败: {result.stderr}")
                return False
        except Exception as e:
            self.log_message(f"登录过程出错: {e}")
            return False
    
    def start_monitoring(self):
        """启动监控线程"""
        def monitoring_loop():
            while self.running:
                try:
                    if not self.check_online():
                        self.log_message("网络连接断开，尝试重新登录...")
                        if self.login():
                            self.log_message("重新登录成功")
                        else:
                            self.log_message("重新登录失败")
                    
                    # 等待5分钟
                    for _ in range(300):
                        if not self.running:
                            break
                        time.sleep(1)
                except Exception as e:
                    self.log_message(f"监控循环出错: {e}")
                    time.sleep(60)
        
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
    
    def manual_check(self):
        """手动检测网络"""
        threading.Thread(target=self.check_online, daemon=True).start()
    
    def manual_login(self):
        """手动登录"""
        threading.Thread(target=self.login, daemon=True).start()
    
    def open_config_file(self):
        """打开配置文件"""
        try:
            if os.path.exists(self.config_file):
                os.startfile(self.config_file)
            else:
                messagebox.showwarning("警告", "配置文件不存在")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开配置文件: {e}")
    
    def open_log_file(self):
        """打开日志文件"""
        try:
            if os.path.exists(self.log_file):
                os.startfile(self.log_file)
            else:
                messagebox.showwarning("警告", "日志文件不存在")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开日志文件: {e}")
    
    def refresh_log(self):
        """刷新日志显示"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.log_text.delete('1.0', tk.END)
                self.log_text.insert('1.0', content)
        except Exception as e:
            messagebox.showerror("错误", f"无法刷新日志: {e}")
    
    def clear_log(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空日志吗？"):
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write('')
                self.log_text.delete('1.0', tk.END)
                self.log_message("日志已清空")
            except Exception as e:
                messagebox.showerror("错误", f"无法清空日志: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        self.init_config()
        messagebox.showinfo("成功", "配置重新加载完成")
    
    def log_message(self, message):
        """记录日志消息"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # 更新界面日志
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # 写入文件
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"日志写入失败: {e}")
    
    def create_tray_icon(self):
        """创建系统托盘图标"""
        def create_image():
            # 创建更清晰的托盘图标
            image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            # 绘制网络图标
            dc.ellipse([16, 16, 48, 48], fill=(0, 120, 215))  # 蓝色背景
            dc.ellipse([20, 20, 44, 44], fill=(255, 255, 255))  # 白色内圆
            dc.ellipse([24, 24, 40, 40], fill=(0, 120, 215))  # 蓝色中心
            return image
        
        def on_click(icon, item):
            """单击托盘图标恢复窗口"""
            self.restore_from_tray()
        
        def show_window(icon, item):
            """显示窗口（菜单项）"""
            self.restore_from_tray()
        
        def quit_application(icon=None, item=None):
            """退出应用程序"""
            self.running = False
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.quit()
            self.root.destroy()
        
        # 创建托盘菜单
        menu = pystray.Menu(
            pystray.MenuItem('显示窗口', show_window),
            pystray.MenuItem('退出', quit_application)
        )
        
        image = create_image()
        self.tray_icon = pystray.Icon(
            "campus_network", 
            image, 
            "校园网认证工具", 
            menu
        )
        
        # 设置单击事件（pystray 0.19.0+ 版本支持）
        try:
            self.tray_icon.on_click = on_click
        except AttributeError:
            # 如果版本不支持on_click，使用默认行为
            pass
        
        self.tray_icon_created = True
    
    def minimize_to_tray(self):
        """最小化到系统托盘"""
        self.root.withdraw()
        if not self.tray_icon_created:
            self.create_tray_icon()
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def restore_from_tray(self):
        """从系统托盘恢复窗口"""
        if self.tray_icon:
            self.tray_icon.visible = False  # 隐藏托盘图标
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.log_message("窗口已从托盘恢复")
    
    def quit_application(self):
        """退出应用程序"""
        if messagebox.askyesno("确认退出", "确定要退出校园网认证工具吗？"):
            self.log_message("用户退出程序")
            self.running = False
            
            # 停止托盘图标
            if self.tray_icon:
                self.tray_icon.stop()
            
            # 退出应用程序
            self.root.quit()
            self.root.destroy()
    
    def run(self):
        """运行应用程序"""
        self.log_message("校园网自动认证工具启动")
        self.root.mainloop()

def main():
    # 检查必要的库
    try:
        import pystray
        from PIL import Image
    except ImportError as e:
        print(f"缺少必要的库: {e}")
        print("请安装: pip install pystray pillow")
        return
    
    app = CampusNetworkGUI()
    app.run()

if __name__ == "__main__":
    main()