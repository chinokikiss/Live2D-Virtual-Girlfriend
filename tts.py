import live2d.v3 as live2d
import sounddevice as sd
import numpy as np
import requests
import hashlib
import time
import re
import threading
from init import Global
from queue import Queue
import string
import random

class LipSyncHandler:
    def __init__(self, model, sample_rate=32000):
        self.model = model
        self.sample_rate = sample_rate
        self.smoothing_factor = 0.3
        self.last_mouth_value = 0.0
        self.silence_threshold = 0 # 静音阈值
        self.max_rms_scale = Global.character["max_rms_scale"]
        self.mouth_scale = 1.0 # 整体嘴巴开合缩放
        
    def update_mouth_sync(self, audio_chunk):
        """更新口型同步"""
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        
        if rms < self.silence_threshold:
            mouth_value = 0.0
        else:
            normalized_rms = (rms - self.silence_threshold) / self.max_rms_scale
            mouth_value = min(normalized_rms ** 2.0, 1.0) * self.mouth_scale
        
        smoothed_value = (self.smoothing_factor * mouth_value + 
                        (1 - self.smoothing_factor) * self.last_mouth_value)
        
        self.model.SetParameterValue("ParamMouthOpenY", smoothed_value)
        self.last_mouth_value = smoothed_value

class AudioQueue:
    def __init__(self, model):
        self.q = {}
        self.t = None
        self.model = model
        threading.Thread(target=self.process).start()

    def process(self):
        while True:
            while not self.q:
                time.sleep(0.01)
            idx = list(self.q.keys())[0]

            lip_sync = LipSyncHandler(self.model)
            stream = sd.OutputStream(samplerate=32000, channels=1, dtype=np.int16)
            stream.start()

            while self.q:
                audio_chunk, subtitle = self.q[idx].get()
                if audio_chunk is None:
                    del self.q[idx]
                    break

                if not Global.exp_queue.empty():
                    Global.expression_animator.add(Global.exp_params[Global.exp_queue.get()], 2)
                
                if subtitle:
                    Global.func_queue2.add(Global.animator1.animate_subtitle, subtitle)
                stream.write(audio_chunk)

                live2d.clearBuffer()
                self.model.Update()
                lip_sync.update_mouth_sync(audio_chunk)
                self.model.Draw()
            
            stream.stop()
            stream.close()
            self.model.SetParameterValue("ParamMouthOpenY", 0.0)
            self.model.Draw()
    
    def add(self, idx, audio_chunk, subtitle):
        if idx not in self.q:
            self.q[idx] = Queue()
        self.q[idx].put((audio_chunk, subtitle)) 
        return None

def generate_auth_str(params):
    sorted_params = sorted(list(params.items()) + [('apikey', Global.niutrans_api_key)], key=lambda x: x[0])
    param_str = '&'.join([f'{key}={value}' for key, value in sorted_params])
    md5 = hashlib.md5()
    md5.update(param_str.encode('utf-8'))
    auth_str = md5.hexdigest()
    return auth_str

def translate(from_l, to_l, src_t, pre_text):
    if Global.niutrans_app_id and Global.niutrans_api_key:
        data = {
            'from': from_l,
            'to': to_l,
            'appId': Global.niutrans_app_id,
            'timestamp': int(time.time()),
            'srcText': src_t
        }

        auth_str = generate_auth_str(data)
        data['authStr'] = auth_str
        response = requests.post("https://api.niutrans.com/v2/text/translate", data=data)
        try:
            pre_text[0] = response.json()['tgtText']
        except:
            print(from_l, to_l, [src_t], response.json())
    else:
        l = {'zh':'ZH_CN', 'en':'EN', 'ja':'JA'}
        from_l = l[from_l]
        to_l = l[to_l]
        response = requests.get(f'https://api.pearktrue.cn/api/translate?text={src_t}&type={from_l}2{to_l}')
        pre_text[0] = response.json()['data']['translate']

def text_process(text, text_lang, prompt_lang):
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'（.*?）', '', text)
    text = re.sub(r'{.*?}', '', text)
    text = text.lstrip(string.punctuation + '……。，；：！？""''（）【】')
    text = text.replace('\n', '')
    pre_text = ['']

    if text_lang != prompt_lang and text and not text.isspace():
        threading.Thread(target=translate, args=(prompt_lang, text_lang, text, pre_text)).start()
        text_lang = prompt_lang
    
    return text, text_lang, pre_text

def gptsovits_audio(pre_text, text, text_lang, ref_audio_path, prompt_text, prompt_lang, speed_factor):
    flag = True
    t = time.time()
    idx = random.randint(1, 10000)
    
    url = Global.tts_api2

    data = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": ref_audio_path,
        "aux_ref_audio_paths": [],
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "top_k": 5,
        "top_p": 1,
        "temperature": 1,
        "text_split_method": "cut5",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": speed_factor,
        "streaming_mode": True,
        "seed": -1,
        "parallel_infer": False,
        "repetition_penalty": 1.35,
        "sample_steps": 32,
        "super_sampling": False,
    }

    response = requests.post(url, json=data, stream=True)
    if response.status_code != 200:
        raise Exception(f"API请求失败: {response.status_code}")
    
    pre_i = 0
    subtitle_text = ''
    audio_length = 0
    subtitle_speed = Global.character["subtitle_speed"]
    buffer_size = 4096
    fade_in_samples = 1600
    samplerate = 32000
    current_sample = 0
    
    for chunk in response.iter_content(chunk_size=buffer_size):
        if not chunk:
            continue
            
        audio_chunk = np.frombuffer(chunk, dtype=np.int16).copy()

        # 淡入效果
        chunk_length = len(audio_chunk)
        for i in range(chunk_length):
            if current_sample < fade_in_samples:
                fade_factor = current_sample / fade_in_samples
                audio_chunk[i] = int(audio_chunk[i] * fade_factor)
            else:
                break
            current_sample += 1
        
        audio_length += chunk_length / samplerate
        if pre_text[0]:
            i = int((int(audio_length / subtitle_speed) + 1) / len(text) * len(pre_text[0])) - 1
            i = max(i, 0)
        else:
            i = 0

        subtitle = None
        add_text = pre_text[0][pre_i:i]
        if add_text:
            subtitle = (subtitle_text, add_text)
            subtitle_text += add_text
        
        pre_i = i
        
        if flag:
            print(f"\nTTS(耗时: {time.time()-t:.2f}s) {pre_text[0]}")
            if Global.sign1:
                Global.sign1 = False
                Global.appearance_animator.reset(-1)
            flag = False
            t = time.time()

        Global.audio_queue.add(idx, audio_chunk, subtitle)
    
    Global.audio_queue.add(idx, None, None)