import requests
import socket
import time
import random
import os
import sys
import configparser
import ctypes
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

# ==========================================
# 1. 基础路径与环境配置
# ==========================================
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe 环境
    CURRENT_DIR = os.path.dirname(sys.executable)
    SCRIPT_PATH = sys.executable
    IS_EXE = True
else:
    # 如果是纯 py 脚本环境
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    SCRIPT_PATH = os.path.abspath(__file__)
    IS_EXE = False

CONFIG_PATH = os.path.join(CURRENT_DIR, 'config.ini')

# ==========================================
# 2. 防多开互斥锁 (Mutex)
# ==========================================
def check_single_instance():
    """检查程序是否已经在运行，防止多开占用资源"""
    mutex_name = "Global\\CZU_AutoLogin_Mutex_Lock_Final" 
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    
    if last_error == 183: # ERROR_ALREADY_EXISTS
        root = tk.Tk()
        root.withdraw() 
        messagebox.showinfo("提示", "校园网自动守护程序已经在后台运行啦！\n无需重复打开。")
        root.destroy()
        sys.exit(0)
        
    return mutex # 必须返回该锁，防止被内存回收

# ==========================================
# 3. 图形化界面与配置管理
# ==========================================
def show_first_run_gui():
    """首次运行的图形化配置界面"""
    result = {}
    suffix_map = {
        "中国电信 (@telecom)": "@telecom",
        "中国移动 (@cmcc)": "@cmcc",
        "中国联通 (@unicom)": "@unicom",
        "纯校园网 (无后缀)": ""
    }

    def on_submit():
        raw_id = entry_user.get().strip()
        p = entry_pwd.get().strip()
        
        if not raw_id or not p:
            messagebox.showwarning("提示", "学号和密码不能为空哦！")
            return
            
        clean_id = raw_id.split('@')[0] 
        selected_isp = combo_isp.get()
        final_account = clean_id + suffix_map.get(selected_isp, "")
        
        result['user'] = final_account
        result['pwd'] = p
        result['autostart'] = 'yes' if var_autostart.get() else 'no'
        root.destroy()

    root = tk.Tk()
    root.title("常州工学院 - 校园网自动连接")
    
    window_width = 380
    window_height = 280
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    root.resizable(False, False)

    tk.Label(root, text="首次运行配置\n请填写您的认证信息", font=("微软雅黑", 12, "bold"), pady=10).pack()

    frame_inputs = tk.Frame(root)
    frame_inputs.pack(pady=5)

    tk.Label(frame_inputs, text="纯学号:", font=("微软雅黑", 10)).grid(row=0, column=0, pady=8, sticky='e')
    entry_user = tk.Entry(frame_inputs, width=22, font=("微软雅黑", 10))
    entry_user.grid(row=0, column=1, pady=8, padx=5)

    tk.Label(frame_inputs, text="运营商:", font=("微软雅黑", 10)).grid(row=1, column=0, pady=8, sticky='e')
    combo_isp = ttk.Combobox(frame_inputs, values=list(suffix_map.keys()), state="readonly", width=20, font=("微软雅黑", 9))
    combo_isp.current(0) 
    combo_isp.grid(row=1, column=1, pady=8, padx=5)

    tk.Label(frame_inputs, text="密码:", font=("微软雅黑", 10)).grid(row=2, column=0, pady=8, sticky='e')
    entry_pwd = tk.Entry(frame_inputs, width=22, font=("微软雅黑", 10), show="*")
    entry_pwd.grid(row=2, column=1, pady=8, padx=5)

    var_autostart = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="开启开机自动静默重连 (强烈推荐)", variable=var_autostart, font=("微软雅黑", 9)).pack(pady=5)

    tk.Button(root, text="保存并自动连接网络", command=on_submit, bg="#4CAF50", fg="white", font=("微软雅黑", 10, "bold"), width=20, pady=5).pack(pady=5)

    def on_closing():
        result['cancel'] = True
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

    if result.get('cancel') or not result.get('user'):
        return None, None, None
    return result['user'], result['pwd'], result['autostart']

def init_config_and_startup():
    """初始化配置：读取或唤起界面，并设置自启"""
    config = configparser.ConfigParser()
    need_gui = False
    
    if not os.path.exists(CONFIG_PATH):
        need_gui = True
    else:
        try:
            config.read(CONFIG_PATH, encoding='utf-8')
            user = config.get('Account', 'username')
            if not user or '你的学号' in user:
                need_gui = True
        except:
            need_gui = True

    if need_gui:
        user, pwd, auto_start = show_first_run_gui()
        if not user:
            sys.exit(0)
            
        config['Account'] = {'username': user, 'password': pwd}
        config['Settings'] = {'auto_start': auto_start}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            config.write(f)
            
        manage_startup(auto_start == 'yes')
        return user, pwd
    else:
        config.read(CONFIG_PATH, encoding='utf-8')
        user = config.get('Account', 'username')
        pwd = config.get('Account', 'password')
        auto_start = config.get('Settings', 'auto_start', fallback='yes').strip().lower()
        manage_startup(auto_start == 'yes')
        return user, pwd

def manage_startup(enable):
    """管理开机启动项"""
    startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
    vbs_path = os.path.join(startup_dir, 'czu_net_keeper.vbs')
    
    if enable:
        if IS_EXE:
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{SCRIPT_PATH}""", 0, False'''
        else:
            pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = "pythonw"
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{pythonw_exe}"" ""{SCRIPT_PATH}""", 0, False'''
        try:
            with open(vbs_path, 'w', encoding='utf-8') as f:
                f.write(vbs_content)
        except Exception:
            pass
    else:
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
            except Exception:
                pass

# ==========================================
# 4. 核心网络通信与守护逻辑
# ==========================================
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""

def check_network():
    try:
        res = requests.get("http://1.1.1.1", timeout=3)
        if "172.19.0.1" in res.url:
            return False
        return True
    except requests.RequestException:
        return False

def daemon_login():
    user_account, user_password = init_config_and_startup()
    if not user_account:
        return

    while True:
        try:
            if not check_network():
                ip = get_local_ip()
                if ip:
                    BASE_URL = "http://172.19.0.1:801/eportal/portal/login"
                    params = {
                        "callback": "dr1003",
                        "login_method": "1",
                        "user_account": user_account,
                        "user_password": user_password,
                        "wlan_user_ip": ip,   
                        "wlan_user_ipv6": "",
                        "wlan_user_mac": "000000000000",
                        "wlan_ac_ip": "",
                        "wlan_ac_name": "",
                        "jsVersion": "4.2.1",
                        "terminal_type": "1",
                        "lang": "zh-cn",
                        "v": str(random.randint(1000, 9999)),
                        "lang": "zh"
                    }
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    requests.get(BASE_URL, params=params, headers=headers, timeout=5)
                time.sleep(30) 
            else:
                time.sleep(600) 
        except Exception:
            time.sleep(5)

# ==========================================
# 5. 程序入口
# ==========================================
if __name__ == "__main__":
    # 1. 获取全局锁，如果获取失败说明已经有程序在运行，会自动退出
    _instance_lock = check_single_instance()
    
    # 2. 进入守护循环
    daemon_login()