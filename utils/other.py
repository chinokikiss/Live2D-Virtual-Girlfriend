import io
import time
import ctypes
import base64
import pyautogui
from PIL import Image
from config import Global

def terminate_thread(thread):
    if not thread.is_alive():
        return
    
    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), exc)
    if res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)

def wait_send_over():
    while True:
        flag = check_send_over()
        if flag:
            break
        time.sleep(1)

def check_send_over():
    flag = True
    for i in Global.func_queue1.t:
        if i.is_alive():
            flag = False
    
    if Global.audio_queue.q:
        flag = False
    elif Global.send_text_thread and Global.send_text_thread.is_alive():
        flag = False
    elif Global.rvc.playing:
        flag = False
    
    return flag

def capture_screen(max_pixels=None):
    screenshot = pyautogui.screenshot()
    
    width, height = screenshot.size
    current_pixels = width * height

    if max_pixels:
        if current_pixels > max_pixels:
            scale_factor = (max_pixels / current_pixels) ** 0.5
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str