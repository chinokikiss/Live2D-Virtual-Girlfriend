import re
import os
import numpy as np
from config import Global
from src.rvc import RVC
from src.mcp_client import MCPClient
from src.graph_rag import RAGMemory
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from concurrent.futures import ThreadPoolExecutor

device = Global.device

class SpeakerVerification:
    def __init__(self):
        if Global.your_voice:
            self.verification = pipeline(
                task='speaker-verification',
                model='iic/speech_campplus_sv_zh-cn_16k-common',
                model_revision='v1.0.0',
                device=device
            )
            
            self._warmup()
    
    def _warmup(self):
        self.my_voice_emb = self.verification([Global.your_voice], output_emb=True)['embs'][0]
    
    def verify_speaker(self, audio_file):
        voice_emb = self.verification([audio_file], output_emb=True)['embs'][0]

        similarity = np.dot(self.my_voice_emb, voice_emb) / (
            np.linalg.norm(self.my_voice_emb) * np.linalg.norm(voice_emb)
        )
        
        return similarity

class SenseVoice:
    def __init__(self):
        self.model = pipeline(
            task=Tasks.auto_speech_recognition,
            model='iic/SenseVoiceSmall',
            model_revision="master",
            device=device
        )

        self._warmup()
    
    def _warmup(self):
        if os.path.exists('temp\\temp.wav'):
            self.infer()

    def infer(self, voice_path='temp\\temp.wav'):
        result = self.model(voice_path)
        pattern = r"<\|(.+?)\|><\|(.+?)\|><\|(.+?)\|><\|(.+?)\|>(.+)"
        match = re.match(pattern, result[0]['text'])
        if match:
            language, emotion, audio_type, itn, text = match.groups()
            text = f"<{emotion}>{text}"
        else:
            text = ''
        return text

Global.rvc = RVC()
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(lambda: setattr(Global, 'sense_voice', SenseVoice())),
        executor.submit(lambda: setattr(Global, 'speaker_verifier', SpeakerVerification())),
        executor.submit(lambda: setattr(Global, 'memory', RAGMemory())),
        executor.submit(lambda: setattr(Global, 'mcp_client', MCPClient()))
    ]

    if "rvc_model" in Global.character:
        futures.append(executor.submit(Global.rvc.change_voice, Global.character["rvc_model"]))
    
    results = []
    for future in futures:
        results.append(future.result())
    
    if not ("rvc_model" in Global.character and results[4]):
        Global.rvc.ok = False
        print('[!]RVC未启动')