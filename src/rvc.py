import pyaudio
import soundfile as sf
import numpy as np
import os
import re
import shutil
import librosa
import requests
import subprocess
from config import Global
from animator.animator import LipSyncHandler

class RVC:
    def __init__(self):
        self.singer = ''
        self.ok = True
        self.playing = False
        self.rvc_url = Global.rvc_url
    
    def change_voice(self, rvc_model):
        try:
            response = requests.post(f"{self.rvc_url}/run/infer_change_voice", json={
            "data": [
                rvc_model,
                0.33,
                0.33,
            ]})

            if response.status_code == 200:
                print("change_voice", response.json())
                return True
        except:
            pass
        
        return False

    def cover_song(self, music_path):
        temp = os.path.realpath('temp')
        voice_dir = os.path.join(temp, "voice")
        background_dir = os.path.join(temp, "background")

        def clear_folder(folder_path):
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            os.makedirs(folder_path)
        
        clear_folder(voice_dir)
        clear_folder(background_dir)

        while True:
            response = requests.post(f"{self.rvc_url}/run/uvr_convert", json={
            "data": [
                "HP2_all_vocals",
                music_path,
                voice_dir,
                None,
                background_dir,
                10,
                "wav",
            ]}).json()

            print('uvr', response)
            if os.listdir(voice_dir):
                break

        voice = os.path.join(voice_dir, os.listdir(voice_dir)[0])
        background = os.path.join(background_dir, os.listdir(background_dir)[0])

        response = requests.post(f"{self.rvc_url}/run/infer_convert", json={
        "data": [
            0,
            voice,
            get_optimal_pitch_shift(voice), # 变调(整数, 半音数量, 升八度12降八度-12)
            None,
            "rmvpe",
            "",
            "logs/guanguanV1.index",
            0.66, # 检索特征占比
            3, # >=3则使用对harvest音高识别的结果使用中值滤波，数值为滤波半径，使用可以削弱哑音
            0, # 后处理重采样至最终采样率，0为不进行重采样
            0.25, # 输入源音量包络替换输出音量包络融合比例，越靠近1越使用输出包络
            0.33, # 保护清辅音和呼吸声，防止电音撕裂等artifact，拉满0.5不开启，调低加大保护力度但可能降低索引效果
        ]}).json()

        print('infer', response)

        voice_path = response["data"][1]["name"]
        shutil.move(voice_path, 'temp/voice.wav')
        shutil.move(background, 'temp/background.wav')
        os.remove(voice)

        # 处理音频
        voice_data, voice_rate = sf.read('temp/voice.wav', dtype='float32')
        background_data, background_rate = sf.read('temp/music/song.mp3', dtype='float32')
        
        # 重采样
        if background_rate != voice_rate:
            if background_data.ndim == 1:
                background_data = librosa.resample(background_data, orig_sr=background_rate, target_sr=voice_rate)
            else:
                # 多声道处理
                background_data = librosa.resample(background_data.T, orig_sr=background_rate, target_sr=voice_rate).T
        
        # 处理声道匹配
        if voice_data.ndim == 1 and background_data.ndim == 2:
            voice_data = np.column_stack([voice_data, voice_data])
        elif voice_data.ndim == 2 and background_data.ndim == 1:
            background_data = np.column_stack([background_data, background_data])
        
        min_len = min(len(voice_data), len(background_data))
        voice_data = voice_data[:min_len]
        background_data = background_data[:min_len] * 0.1
        
        mixed_audio = voice_data + background_data
        
        sf.write('temp/mixed.wav', mixed_audio, voice_rate)

    def play(self, lyrics):
        def parse_lyrics(text):
            lines = text.strip().split('\n')
            result = []
            
            for line in lines:
                timestamps = re.findall(r'\[(\d{2}:\d{2}\.\d{1,3})\]', line)
                
                if timestamps:
                    content = re.sub(r'\[\d{2}:\d{2}\.\d{1,3}\]', '', line).strip()
                    
                    for timestamp in timestamps:
                        minutes, seconds = timestamp.split(':')
                        total_seconds = int(minutes) * 60 + float(seconds)
                        
                        result.append({
                            'seconds': total_seconds,
                            'content': content
                        })
            
            return result
        lyrics = parse_lyrics(lyrics)

        self.playing = True
        voice_data, voice_rate = sf.read('temp/voice.wav', dtype='float32')
        mixed_data, mixed_rate = sf.read('temp/mixed.wav', dtype='float32')
        
        # 转换为播放格式
        audio_int16 = (mixed_data * 32767).clip(-32768, 32767).astype(np.int16)
        
        p = pyaudio.PyAudio()
        channels = audio_int16.shape[1] if audio_int16.ndim > 1 else 1
        
        chunk_size = 1024
        model = Global.model
        lip_sync = LipSyncHandler(sample_rate=voice_rate, max_rms_scale=0.18)

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=int(voice_rate),
            output=True,
            frames_per_buffer=chunk_size
        )
        
        try:
            total_chunks = len(audio_int16) // chunk_size

            lyric_index = 0
            _subtitle_i = 0
            subtitle_text = ''
            Global.animator2.cancel_fade_out()
            
            for i in range(total_chunks):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size
                chunk = audio_int16[start_idx:end_idx]

                if lyric_index != -1:
                    current_time = start_idx / voice_rate
                    
                    q_seconds = lyrics[lyric_index]['seconds']
                    p_seconds = lyrics[lyric_index+1]['seconds']

                    if current_time > p_seconds:
                        if lyric_index == len(lyrics)-2:
                            lyric_index = -1
                            Global.animator2.schedule_fade_out()
                        else:
                            lyric_index += 1
                            _subtitle_i = 0
                            subtitle_text = ''
                            q_seconds = lyrics[lyric_index]['seconds']
                            p_seconds = lyrics[lyric_index+1]['seconds']

                if lyric_index != -1:
                    lyric_content = lyrics[lyric_index]['content']
                    subtitle_i = int(len(lyric_content) * ((current_time - q_seconds) / (p_seconds - q_seconds))) + 1

                    subtitle = None
                    add_text = lyric_content[_subtitle_i:subtitle_i]
                    if add_text:
                        subtitle = (subtitle_text, add_text)
                        subtitle_text += add_text
                    
                    _subtitle_i = subtitle_i
                    
                    if subtitle:
                        Global.func_queue2.add(Global.animator1.animate_subtitle, subtitle)

                stream.write(chunk.tobytes())
                
                voice_chunk = voice_data[start_idx:end_idx]
                if voice_chunk.ndim > 1:
                    voice_chunk = voice_chunk[:, 0]
                
                lip_sync.update_mouth_sync(voice_chunk)
            
            # 播放剩余部分
            remaining = audio_int16[total_chunks * chunk_size:]
            if len(remaining) > 0:
                stream.write(remaining.tobytes())
                
        finally:
            self.playing = False
            stream.stop_stream()
            stream.close()
            p.terminate()
            model.SetParameterValue("ParamMouthOpenY", 0.0)

def get_music163(keyword):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(f'https://apis.netstart.cn/music/cloudsearch?keywords={keyword}', headers=headers)
    json_data = response.json()
    
    songs = json_data["result"]["songs"]
    for song in songs:
        song_id = song['id']
        mv_id = song.get('mvid', None)

        response = requests.get(f'https://apis.netstart.cn/music/song/download/url?id={song_id}', headers=headers)
        json_data = response.json()
        
        if json_data['data']["url"]:
            song_url = json_data['data']["url"]

            response = requests.get(f'https://apis.netstart.cn/music/lyric?id={song_id}', headers=headers)
            json_data = response.json()
            lyric = json_data["lrc"]["lyric"]

            response = requests.get(song_url, headers=headers, stream=True)
            response.raise_for_status()
            with open('temp\music\song.mp3', 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return song, lyric

        elif mv_id:
            response = requests.get(f'https://apis.netstart.cn/music/mv/url?id={mv_id}', headers=headers)
            json_data = response.json()
            
            if json_data['data']["url"]:
                mv_url = json_data['data']["url"]

                response = requests.get(f'https://apis.netstart.cn/music/lyric?id={song_id}', headers=headers)
                json_data = response.json()
                lyric = json_data["lrc"]["lyric"]

                response = requests.get(mv_url, headers=headers, stream=True)
                response.raise_for_status()
                with open('temp\mv.mp4', 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                subprocess.run([
                    'ffmpeg', '-i', 'temp\mv.mp4', 
                    '-vn', '-acodec', 'mp3', '-ab', '192k', 
                    '-ar', '44100', '-y', 'temp\music\song.mp3'
                ], check=True, capture_output=True)

                return song, lyric
    
    return None, None

def get_optimal_pitch_shift(audio_path):
    voice_data, voice_rate = librosa.load(audio_path, sr=None)

    f0 = librosa.yin(voice_data, fmin=80, fmax=400, sr=voice_rate)
    
    valid_f0 = f0[~np.isnan(f0)]
    
    if len(valid_f0) > 0:
        average_pitch = np.mean(valid_f0)
        print(f"源音频平均基频: {average_pitch:.2f} Hz")

        pitch_shift = 0 if average_pitch > 260 else 8
        
        print(f"变调: {pitch_shift} 半音")
        return int(pitch_shift)
    else:
        return 0