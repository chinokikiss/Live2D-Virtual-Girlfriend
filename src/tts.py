import sounddevice as sd
import numpy as np
import requests
import hashlib
import time
import re
import os
import threading
from config import Global
from queue import Queue
from pydub import AudioSegment
from animator.animator import LipSyncHandler
import string
import random

class AudioQueue:
    def __init__(self, model, sample_rate):
        self.q = {}
        self.t = None
        self.model = model
        self.sample_rate = sample_rate
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        while True:
            while not self.q:
                time.sleep(0.01)
            idx = list(self.q.keys())[0]

            lip_sync = LipSyncHandler(sample_rate=self.sample_rate)
            stream = sd.OutputStream(samplerate=self.sample_rate, channels=1, dtype=np.int16)
            stream.start()
            Global.animator2.cancel_fade_out()

            while self.q:
                audio_chunk, subtitle = self.q[idx].get()
                if audio_chunk is None:
                    del self.q[idx]
                    break

                if not Global.exp_queue.empty():
                    Global.expression_animator.add(Global.exp_params[Global.exp_queue.get()], Global.exp_fadeout)
                
                if subtitle:
                    Global.func_queue2.add(Global.animator1.animate_subtitle, subtitle)
                stream.write(audio_chunk)

                lip_sync.update_mouth_sync(audio_chunk)

            Global.animator2.schedule_fade_out()
            stream.stop()
            stream.close()
            self.model.SetParameterValue("ParamMouthOpenY", 0.0)
    
    def add(self, idx, audio_chunk, subtitle):
        if idx not in self.q:
            self.q[idx] = Queue()
        self.q[idx].put((audio_chunk, subtitle)) 
        return None

def process_chunk_pitch(chunk_data, samplerate, pitch):
    if len(chunk_data) == 0:
        return chunk_data
    
    segment = AudioSegment(
        data=chunk_data,
        sample_width=2,
        frame_rate=samplerate,
        channels=1
    )
    
    segment = segment._spawn(segment.raw_data, overrides={
        "frame_rate": int(segment.frame_rate * pitch)
    }).set_frame_rate(samplerate)
    
    audio_array = np.frombuffer(segment.raw_data, dtype=np.int16)
    return audio_array

def generate_auth_str(params):
    sorted_params = sorted(list(params.items()) + [('apikey', Global.niutrans_api_key)], key=lambda x: x[0])
    param_str = '&'.join([f'{key}={value}' for key, value in sorted_params])
    md5 = hashlib.md5()
    md5.update(param_str.encode('utf-8'))
    auth_str = md5.hexdigest()
    return auth_str

def translate(from_l, to_l, src_t):
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
            return response.json()['tgtText']
        except:
            print(from_l, to_l, [src_t], response.json())
            return ''
    else:
        l = {'zh':'ZH_CN', 'en':'EN', 'ja':'JA'}
        from_l = l[from_l]
        to_l = l[to_l]
        response = requests.get(f'https://api.pearktrue.cn/api/translate?text={src_t}&type={from_l}2{to_l}')
        return response.json()['data']['translate']

def text_process(text, subtitle_lang, text_lang, length):
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'（.*?）', '', text)
    text = re.sub(r'{.*?}', '', text)
    text = text.lstrip(string.punctuation + '\n……。，；：！？""''（）【】')
    text = text.replace('\n', '')
    
    tran_text = ''
    if len(text) > length and not text.isspace():
        if subtitle_lang != text_lang:
            tran_text = translate(subtitle_lang, text_lang, text)
        else:
            tran_text = text
    
    return text, tran_text

def gptsovits_audio(text, tran_text, text_lang, prompt_lang, speed_factor):
    flag = True
    t = time.time()
    idx = random.randint(1, 10000)
    pre_i = 0
    subtitle_text = ''
    audio_length = 0
    subtitle_speed = Global.character["subtitle_speed"]
    buffer_size = 1024
    
    if "voice" in Global.character:
        samplerate = 24000

        tran_text = tran_text.replace('Hmph', 'Humph')

        with Global.kokoro_client.audio.speech.with_streaming_response.create(
            model="kokoro",
            voice=Global.character["voice"],
            speed=speed_factor,
            response_format="pcm",
            input=tran_text
        ) as response:
            for chunk in response.iter_bytes(chunk_size=buffer_size):
                audio_chunk = process_chunk_pitch(chunk, samplerate, Global.character["pitch"])
                
                audio_length += len(audio_chunk) / samplerate
                if text:
                    i = int((int(audio_length / subtitle_speed) + 1) / len(tran_text) * len(text)) - 1
                    i = max(i, 0)
                else:
                    i = 0

                subtitle = None
                add_text = text[pre_i:i]
                if add_text:
                    subtitle = (subtitle_text, add_text)
                    subtitle_text += add_text
                
                pre_i = i

                if flag:
                    print(f"\nTTS(耗时: {time.time()-t:.2f}s)")
                    flag = False
                    t = time.time()

                Global.audio_queue.add(idx, audio_chunk, subtitle)

    else:
        ref_audio = os.path.realpath(Global.character["ref_audio"])
        prompt_text = Global.character["prompt_text"]

        url = Global.gsv_api2

        data = {
            "text": tran_text,
            "text_lang": text_lang,
            "ref_audio_path": ref_audio,
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
            if text:
                i = int((int(audio_length / subtitle_speed) + 1) / len(tran_text) * len(text)) - 1
                i = max(i, 0)
            else:
                i = 0

            subtitle = None
            add_text = text[pre_i:i]
            if add_text:
                subtitle = (subtitle_text, add_text)
                subtitle_text += add_text
            
            pre_i = i
            
            if flag:
                print(f"\nTTS(耗时: {time.time()-t:.2f}s)")
                flag = False
                t = time.time()

            Global.audio_queue.add(idx, audio_chunk, subtitle)
    
    Global.audio_queue.add(idx, None, None)