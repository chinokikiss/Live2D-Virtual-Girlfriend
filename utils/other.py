import io
import wave
import time
import ctypes
import base64
import pyaudio
import pyautogui
import numpy as np
from PIL import Image
from config import Global
from threading import Thread

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

def capture_screen(max_pixels=None, web=False):
    if web:
        Global.web_request_photo()
        image_path = Global.received_photo.get()
        screenshot = Image.open(image_path)
    else:
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

class sounds_player:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.cache = {}
    
    def load(self, id, path, volume):
        with wave.open(path, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            
        audio_data = np.frombuffer(frames, dtype=np.int16)
        audio_data = (audio_data * volume).astype(audio_data.dtype)
        
        with wave.open(path, 'rb') as wf:
            audio_info = {
                'data': audio_data.tobytes(),
                'channels': wf.getnchannels(),
                'sample_width': wf.getsampwidth(),
                'framerate': wf.getframerate()
            }
        
        stream = self.p.open(
            format=self.p.get_format_from_width(audio_info['sample_width']),
            channels=audio_info['channels'],
            rate=audio_info['framerate'],
            output=True
        )

        self.cache[id] = (audio_info['data'], stream)
    
    def play(self, id):
        Thread(target=self._play, args=(id,)).start()
    
    def _play(self, id):
        audio_data, stream = self.cache[id]
        stream.write(audio_data)