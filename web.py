import os
import ssl
import time
import logging
import socket
import queue
import base64
from threading import Thread
from config import Global
from utils.other import terminate_thread
from src.asr import speech_recognition
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

port = Global.weblive2d["port"]
cert_file = 'assets\cert.pem'
key_file = 'assets\key.pem'
app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = 'live2dchat'
socketio = SocketIO(app, cors_allowed_origins="*")
logging.getLogger('werkzeug').setLevel(logging.ERROR)

class AudioStream:
    def __init__(self):
        self.buffer = queue.Queue(10)
        
    def write(self, data):
        self.buffer.put(data)
        
    def read(self, chunk_size=None):
        chunk_size *= 2
        data = b''
        while len(data) != chunk_size:
            data += self.buffer.get()
            if len(data) > chunk_size:
                remaining = data[chunk_size:]
                self.buffer.put(remaining)
                data = data[:chunk_size]
        return data

def generate_html():
    """动态生成HTML内容"""
    
    # 嘴型同步参数配置
    mouth_sync_config = {
        'smoothing_factor': 0.3, # 平滑系数 (0-1)
        'silence_threshold': 0, # 静音阈值
        'max_rms_scale': Global.character["max_rms_scale"]*Global.weblive2d["max_rms_scale"], # 最大RMS缩放
        'mouth_scale': 1.0, # 整体嘴巴开合缩放
        'power_exponent': 2.0, # 非线性变换指数
        'update_interval': 16, # 更新间隔(ms)，16约等于60fps
        'close_speed': 0.85 # 嘴巴关闭速度
    }
    
    return f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/x-icon" href="assets/icons/icon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      body {{
        background-image: url('{Global.weblive2d["background"]}');
        background-size: {Global.weblive2d["background_width"]}px {Global.weblive2d["background_height"]}px;
        background-repeat: no-repeat;
        background-position: center center;
        background-attachment: fixed;
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100vh;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        overflow: hidden;
      }}
      #canvas2 {{
        width: auto;
        height: 100vh;
        margin: 0 auto;
        display: block;
        background-color: transparent;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
      }}
      
      .status-message {{
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 8px 12px;
        border-radius: 15px;
        font-size: 12px;
        backdrop-filter: blur(10px);
        opacity: 0;
        transition: opacity 0.3s ease;
      }}
      
      .status-message.show {{
        opacity: 1;
      }}
      
      .subtitle-container {{
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 2000;
        max-width: 90%;
        width: auto;
        pointer-events: none;
      }}
      
      .subtitle {{
        background: linear-gradient(135deg, rgba(0, 0, 0, 0.85) 0%, rgba(30, 30, 30, 0.9) 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 25px;
        font-size: 16px;
        font-weight: 500;
        text-align: center;
        line-height: 1.4;
        margin: 0 auto;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        opacity: 0;
        transform: translateY(20px) scale(0.95);
        transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        word-wrap: break-word;
        max-width: 600px;
        min-width: 100px;
      }}
      
      .subtitle.show {{
        opacity: 1;
        transform: translateY(0) scale(1);
      }}
      
      .subtitle.fadeout {{
        opacity: 0;
        transform: translateY(-10px) scale(0.98);
        transition: all 0.3s ease-in;
      }}
      
      .subtitle.instant-replace {{
        transition: all 0.2s ease;
      }}
      
      @media (max-width: 768px) {{
        .subtitle {{
          font-size: 14px;
          padding: 10px 16px;
          max-width: calc(100vw - 40px);
          margin: 0 20px;
        }}
        
        .subtitle-container {{
          bottom: 80px;
          max-width: 100%;
        }}
      }}
      
      @media (max-width: 480px) {{
        .subtitle {{
          font-size: 13px;
          padding: 8px 14px;
          border-radius: 20px;
        }}
        
        .subtitle-container {{
          bottom: 60px;
        }}
      }}
      
      .permission-modal {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        backdrop-filter: blur(5px);
      }}
      
      .modal-content {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        text-align: center;
        color: white;
        max-width: 400px;
        margin: 20px;
        transform: scale(0.9);
        animation: modalAppear 0.3s ease-out forwards;
      }}
      
      @keyframes modalAppear {{
        to {{
          transform: scale(1);
        }}
      }}
      
      .modal-title {{
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 15px;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
      }}
      
      .modal-text {{
        font-size: 16px;
        line-height: 1.5;
        margin-bottom: 25px;
        opacity: 0.9;
      }}
      
      .modal-buttons {{
        display: flex;
        gap: 15px;
        justify-content: center;
      }}
      
      .modal-btn {{
        padding: 12px 25px;
        border: none;
        border-radius: 25px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        min-width: 100px;
      }}
      
      .btn-primary {{
        background: white;
        color: #667eea;
      }}
      
      .btn-primary:hover {{
        background: #f0f0f0;
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
      }}
      
      .btn-secondary {{
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border: 2px solid rgba(255, 255, 255, 0.3);
      }}
      
      .btn-secondary:hover {{
        background: rgba(255, 255, 255, 0.3);
        transform: translateY(-2px);
      }}
      
      .hidden {{ display: none !important; }}
      
      #hiddenCanvas {{
        display: none;
      }}
      
      #hiddenVideo {{
        display: none;
      }}
    </style>
    <script src="assets/live2d_core/live2dcubismcore.min.js"></script>
    <script src="assets/live2d_core/live2d.min.js"></script>
    <script src="assets/live2d_core/pixi.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <title>Ciallo～(∠・ω< )⌒★</title>
    
    <script>
      // 基于RMS的嘴型同步配置参数
      const MOUTH_SYNC_CONFIG = {{
        smoothingFactor: {mouth_sync_config['smoothing_factor']},
        silenceThreshold: {mouth_sync_config['silence_threshold']},
        maxRmsScale: {mouth_sync_config['max_rms_scale']},
        mouthScale: {mouth_sync_config['mouth_scale']},
        powerExponent: {mouth_sync_config['power_exponent']},
        updateInterval: {mouth_sync_config['update_interval']},
        closeSpeed: {mouth_sync_config['close_speed']}
      }};
      
      let audioContext;
      let mediaRecorder;
      let isRecording = false;
      let socket;
      let currentAudioPlayer = null;
      let currentAudioPlayerTimeout = null;
      let isPlaying = false;
      let audioPermissionGranted = false;
      let audioQueue = [];
      let isProcessingAudio = false;
      let source;
      let processor;
      
      // RMS嘴型同步相关变量
      let mouthSyncAnimation;
      let sharedAudioContext;
      let lastMouthValue = 0.0;
      let mouthSyncEnabled = true;
      let currentAudioSource = null;
      let analyser = null;
      let detectedMouthParam = null;
      let mouthCloseInterval = null; // 新增：用于管理嘴型关闭动画的定时器
      
      // 摄像头相关变量
      let cameraStream = null;
      let cameraVideo = null;
      let currentFacingMode = 'environment'; // 默认后置摄像头
      let cameraPermissionGranted = false;
      let isCapturingPhoto = false;
      
      // 字幕相关变量
      let currentSubtitleTimeout = null;
      let subtitleQueue = [];
      let isDisplayingSubtitle = false;
      
      // JavaScript版本的LipSyncHandler
      class LipSyncHandler {{
        constructor() {{
          this.smoothingFactor = MOUTH_SYNC_CONFIG.smoothingFactor;
          this.lastMouthValue = 0.0;
          this.silenceThreshold = MOUTH_SYNC_CONFIG.silenceThreshold;
          this.maxRmsScale = MOUTH_SYNC_CONFIG.maxRmsScale;
          this.mouthScale = MOUTH_SYNC_CONFIG.mouthScale;
          this.powerExponent = MOUTH_SYNC_CONFIG.powerExponent;
        }}
        
        updateMouthSync(audioData) {{
          let sum = 0;
          for (let i = 0; i < audioData.length; i++) {{
            sum += audioData[i] * audioData[i];
          }}
          const rms = Math.sqrt(sum / audioData.length);
          
          let mouthValue;
          if (rms < this.silenceThreshold) {{
            mouthValue = 0.0;
          }} else {{
            const normalizedRms = (rms - this.silenceThreshold) / this.maxRmsScale;
            mouthValue = Math.min(Math.pow(normalizedRms, this.powerExponent), 1.0) * this.mouthScale;
          }}
          
          const smoothedValue = (this.smoothingFactor * mouthValue + 
                               (1 - this.smoothingFactor) * this.lastMouthValue);
          
          window.updateMouthSync(smoothedValue);
          this.lastMouthValue = smoothedValue;
          
          return smoothedValue;
        }}
      }}
      
      const lipSyncHandler = new LipSyncHandler();
      
      function detectMouthParameter() {{
        if (!window._i || !window._i.internalModel || !window._i.internalModel.coreModel) {{
          return null;
        }}
        
        const possibleParams = [
          "ParamMouthOpenY",
          "PARAM_MOUTH_OPEN_Y", 
          "ParamMouthOpen",
          "PARAM_MOUTH_OPEN",
          "ParamMouthForm",
          "PARAM_MOUTH_FORM",
          "MouthOpenY",
          "MouthOpen",
          "Mouth_Open_Y",
          "mouth_open_y",
          "mouth_open"
        ];
        
        const coreModel = window._i.internalModel.coreModel;
        
        for (const param of possibleParams) {{
          try {{
            const originalValue = coreModel.getParameterValueById ? 
                                 coreModel.getParameterValueById(param) : 0;
            coreModel.setParameterValueById(param, 0.5);
            coreModel.setParameterValueById(param, originalValue);
            return param;
          }} catch (error) {{
            // 参数不存在，继续尝试下一个
          }}
        }}
        
        try {{
          if (coreModel.getParameterCount && coreModel.getParameterId) {{
            const paramCount = coreModel.getParameterCount();
            for (let i = 0; i < paramCount; i++) {{
              const paramId = coreModel.getParameterId(i);
              if (paramId && (
                paramId.toLowerCase().includes('mouth') ||
                paramId.toLowerCase().includes('口') ||
                paramId.toLowerCase().includes('嘴')
              )) {{
                return paramId;
              }}
            }}
          }}
        }} catch (error) {{
          // 忽略错误
        }}
        
        return null;
      }}
      
      window.updateMouthSync = function(value) {{
        if (!window._i || !window._i.internalModel || !window._i.internalModel.coreModel) {{
          return;
        }}
        
        if (detectedMouthParam === null) {{
          detectedMouthParam = detectMouthParameter();
          if (!detectedMouthParam) {{
            return;
          }}
        }}
        
        const clampedValue = Math.max(0, Math.min(1, value));
        
        try {{
          window._i.internalModel.coreModel.setParameterValueById(detectedMouthParam, clampedValue);
        }} catch (error) {{
          detectedMouthParam = null;
        }}
      }};
      
      // 字幕显示相关函数 - 修改版本，支持立即替换
      function showSubtitle(text, duration = 3000, forceReplace = false) {{
        if (!text || text.trim() === '') {{
          return;
        }}
        
        const newSubtitle = {{ text: text.trim(), duration: duration }};
        
        // 如果强制替换或者当前正在显示字幕，立即替换
        if (forceReplace || isDisplayingSubtitle) {{
          // 清除当前字幕队列和超时
          subtitleQueue = [];
          if (currentSubtitleTimeout) {{
            clearTimeout(currentSubtitleTimeout);
            currentSubtitleTimeout = null;
          }}
          
          // 立即显示新字幕
          isDisplayingSubtitle = true;
          displaySubtitleInstant(newSubtitle.text, newSubtitle.duration);
        }} else {{
          // 添加到字幕队列
          subtitleQueue.push(newSubtitle);
          
          // 如果没有正在显示字幕，立即处理队列
          if (!isDisplayingSubtitle) {{
            processSubtitleQueue();
          }}
        }}
      }}
      
      function displaySubtitleInstant(text, duration) {{
        const subtitleEl = document.getElementById('subtitle');
        
        // 添加快速替换样式
        subtitleEl.classList.add('instant-replace');
        
        // 如果当前有字幕显示，快速淡出
        if (subtitleEl.classList.contains('show')) {{
          subtitleEl.classList.remove('show');
          
          // 很短的延迟后显示新字幕
          setTimeout(() => {{
            subtitleEl.textContent = text;
            subtitleEl.classList.add('show');
            
            // 移除快速替换样式
            setTimeout(() => {{
              subtitleEl.classList.remove('instant-replace');
            }}, 200);
          }}, 100);
        }} else {{
          // 没有当前字幕，直接显示
          subtitleEl.textContent = text;
          subtitleEl.classList.add('show');
          
          // 移除快速替换样式
          setTimeout(() => {{
            subtitleEl.classList.remove('instant-replace');
          }}, 200);
        }}
        
        // 设置隐藏字幕的定时器
        currentSubtitleTimeout = setTimeout(() => {{
          hideSubtitle();
        }}, duration);
      }}
      
      function processSubtitleQueue() {{
        if (subtitleQueue.length === 0) {{
          isDisplayingSubtitle = false;
          return;
        }}
        
        isDisplayingSubtitle = true;
        const subtitleData = subtitleQueue.shift();
        displaySubtitle(subtitleData.text, subtitleData.duration);
      }}
      
      function displaySubtitle(text, duration) {{
        const subtitleEl = document.getElementById('subtitle');
        
        // 清除之前的字幕超时
        if (currentSubtitleTimeout) {{
          clearTimeout(currentSubtitleTimeout);
          currentSubtitleTimeout = null;
        }}
        
        // 设置字幕文本
        subtitleEl.textContent = text;
        
        // 重置类名并强制重绘
        subtitleEl.className = 'subtitle';
        subtitleEl.offsetHeight; // 触发重绘
        
        // 显示字幕
        setTimeout(() => {{
          subtitleEl.classList.add('show');
        }}, 50);
        
        // 设置隐藏字幕的定时器
        currentSubtitleTimeout = setTimeout(() => {{
          hideSubtitle();
        }}, duration);
      }}
      
      function hideSubtitle() {{
        const subtitleEl = document.getElementById('subtitle');
        
        // 添加淡出效果
        subtitleEl.classList.add('fadeout');
        
        // 等待动画完成后隐藏并处理下一个字幕
        setTimeout(() => {{
          subtitleEl.classList.remove('show', 'fadeout', 'instant-replace');
          subtitleEl.textContent = '';
          
          // 处理队列中的下一个字幕
          setTimeout(() => {{
            processSubtitleQueue();
          }}, 100);
        }}, 300);
      }}
      
      function clearSubtitle() {{
        // 清除当前字幕
        if (currentSubtitleTimeout) {{
          clearTimeout(currentSubtitleTimeout);
          currentSubtitleTimeout = null;
        }}
        
        // 清空字幕队列
        subtitleQueue = [];
        isDisplayingSubtitle = false;
        
        // 隐藏当前显示的字幕
        const subtitleEl = document.getElementById('subtitle');
        subtitleEl.classList.remove('show');
        subtitleEl.classList.add('fadeout');
        
        setTimeout(() => {{
          subtitleEl.classList.remove('fadeout', 'instant-replace');
          subtitleEl.textContent = '';
        }}, 300);
      }}
      
      function showStatus(message) {{
        const statusEl = document.getElementById('statusMessage');
        statusEl.textContent = message;
        statusEl.classList.add('show');
        setTimeout(() => {{
          statusEl.classList.remove('show');
        }}, 3000);
      }}
      
      function showPermissionModal() {{
        return new Promise((resolve) => {{
          const modal = document.getElementById('permissionModal');
          modal.classList.remove('hidden');
          
          document.getElementById('allowBtn').onclick = () => {{
            modal.classList.add('hidden');
            resolve(true);
          }};
          
          document.getElementById('denyBtn').onclick = () => {{
            modal.classList.add('hidden');
            resolve(false);
          }};
        }});
      }}
      
      async function initializeAudioPermission() {{
        try {{
          const granted = await showPermissionModal();
          
          if (granted) {{
            const silentAudio = new Audio();
            silentAudio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IAAAAAEAAQAARAAAIlAAAQACABAAZGF0YQAAAAA=';
            silentAudio.volume = 0;
            
            try {{
              await silentAudio.play();
              audioPermissionGranted = true;
              showStatus('音频权限已获得');
              processAudioQueue();
            }} catch (error) {{
              audioPermissionGranted = true;
              processAudioQueue();
            }}
          }} else {{
            showStatus('用户拒绝了音频播放权限');
            audioPermissionGranted = false;
          }}
          
        }} catch (error) {{
          audioPermissionGranted = false;
        }}
      }}
      
      async function processAudioQueue() {{
        if (isProcessingAudio || audioQueue.length === 0) {{
          return;
        }}
        
        isProcessingAudio = true;
        
        while (audioQueue.length > 0) {{
          const audioInfo = audioQueue.shift();
          try {{
            // 如果有字幕，显示字幕（强制替换）
            if (audioInfo.subtitle) {{
              showSubtitle(audioInfo.subtitle, audioInfo.subtitleDuration || 3000, true);
            }}
            
            // 播放音频并等待其结束，实现无缝衔接
            await playAudioBlockingWithSync(audioInfo.data, audioInfo.format, audioInfo.volume, audioInfo.enableSync);
            // 移除固定延迟
          }} catch (error) {{
            showStatus('播放音频失败: ' + error.message);
          }}
        }}
        
        isProcessingAudio = false;
      }}
      
      function getSharedAudioContext() {{
        if (!sharedAudioContext) {{
          try {{
            sharedAudioContext = new (window.AudioContext || window.webkitAudioContext)();
          }} catch (error) {{
            return null;
          }}
        }}
        
        if (sharedAudioContext.state === 'suspended') {{
          sharedAudioContext.resume();
        }}
        
        return sharedAudioContext;
      }}
      
      function startMouthSync(audioElement) {{
        try {{
          const audioCtx = getSharedAudioContext();
          if (!audioCtx) {{
            startSimpleMouthSync();
            return;
          }}
          
          // 清除任何正在进行的嘴型关闭动画
          if (mouthCloseInterval) {{
            clearInterval(mouthCloseInterval);
            mouthCloseInterval = null;
          }}

          if (currentAudioSource) {{
            try {{
              currentAudioSource.disconnect();
            }} catch (e) {{}}
          }}
          if (analyser) {{
            try {{
              analyser.disconnect();
            }} catch (e) {{}}
          }}
          
          try {{
            currentAudioSource = audioCtx.createMediaElementSource(audioElement);
            analyser = audioCtx.createAnalyser();
            
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8;
            
            currentAudioSource.connect(analyser);
            analyser.connect(audioCtx.destination);
            
          }} catch (error) {{
            startSimpleMouthSync();
            return;
          }}
          
          const bufferLength = analyser.fftSize;
          const dataArray = new Float32Array(bufferLength);
          
          function analyzeRMS() {{
            if (!isPlaying) {{
              // 播放结束，由 onended 中的 stopMouthSync 处理关闭动画
              return;
            }}
            
            analyser.getFloatTimeDomainData(dataArray);
            lipSyncHandler.updateMouthSync(dataArray);
            mouthSyncAnimation = setTimeout(analyzeRMS, MOUTH_SYNC_CONFIG.updateInterval);
          }}
          
          analyzeRMS();
          
        }} catch (error) {{
          startSimpleMouthSync();
        }}
      }}
      
      function startSimpleMouthSync() {{
        let intensity = 0.8;
        let currentValue = 0;
        
        function simpleMouth() {{
          if (!isPlaying) {{
            currentValue *= MOUTH_SYNC_CONFIG.closeSpeed;
            window.updateMouthSync(currentValue);
            if (currentValue > 0.01) {{
              setTimeout(simpleMouth, MOUTH_SYNC_CONFIG.updateInterval);
            }} else {{
              window.updateMouthSync(0);
            }}
            return;
          }}
          
          const baseValue = Math.random() * intensity;
          const smoothFactor = MOUTH_SYNC_CONFIG.smoothingFactor;
          currentValue = currentValue * (1 - smoothFactor) + baseValue * smoothFactor;
          
          window.updateMouthSync(currentValue);
          intensity *= 0.998;
          
          setTimeout(simpleMouth, 60 + Math.random() * 40);
        }}
        
        simpleMouth();
      }}
      
      function stopMouthSync() {{
        if (mouthSyncAnimation) {{
          clearTimeout(mouthSyncAnimation);
          mouthSyncAnimation = null;
        }}
        
        if (mouthCloseInterval) {{ // 确保清除任何正在进行的嘴型关闭动画
          clearInterval(mouthCloseInterval);
          mouthCloseInterval = null;
        }}
        
        if (currentAudioSource) {{
          try {{
            currentAudioSource.disconnect();
          }} catch (e) {{}}
          currentAudioSource = null;
        }}
        if (analyser) {{
          try {{
            analyser.disconnect();
          }} catch (e) {{}}
          analyser = null;
        }}
        
        // 启动嘴型平滑关闭动画
        mouthCloseInterval = setInterval(() => {{
          lipSyncHandler.lastMouthValue *= MOUTH_SYNC_CONFIG.closeSpeed;
          window.updateMouthSync(lipSyncHandler.lastMouthValue);
          if (lipSyncHandler.lastMouthValue < 0.02) {{
            clearInterval(mouthCloseInterval);
            mouthCloseInterval = null; // 清除定时器引用
            window.updateMouthSync(0);
            lipSyncHandler.lastMouthValue = 0;
          }}
        }}, MOUTH_SYNC_CONFIG.updateInterval);
      }}
      
      function playAudioBlockingWithSync(audioData, format = 'wav', volume = 0.7, enableMouthSync = true) {{
        return new Promise((resolve, reject) => {{
          try {{
            stopAudio();
            
            const audioPlayer = new Audio();
            currentAudioPlayer = audioPlayer;
            
            const blob = new Blob([audioData], {{ type: `audio/${{format}}` }});
            const url = URL.createObjectURL(blob);
            
            audioPlayer.src = url;
            audioPlayer.volume = volume;
            audioPlayer.crossOrigin = 'anonymous';
            
            audioPlayer.onended = () => {{
              isPlaying = false;
              if (enableMouthSync && mouthSyncEnabled) {{
                stopMouthSync();
              }}
              URL.revokeObjectURL(url);
              
              if (currentAudioPlayer === audioPlayer) {{
                currentAudioPlayer = null;
              }}
              
              resolve();
            }};
            
            audioPlayer.onerror = (error) => {{
              isPlaying = false;
              if (enableMouthSync && mouthSyncEnabled) {{
                stopMouthSync();
              }}
              URL.revokeObjectURL(url);
              
              if (currentAudioPlayer === audioPlayer) {{
                currentAudioPlayer = null;
              }}
              
              reject(error);
            }};
            
            audioPlayer.play().then(() => {{
              isPlaying = true;
              if (enableMouthSync && mouthSyncEnabled) {{
                setTimeout(() => {{
                  if (isPlaying && currentAudioPlayer === audioPlayer) {{
                    startMouthSync(audioPlayer);
                  }}
                }}, 100);
              }}
            }}).catch(error => {{
              URL.revokeObjectURL(url);
              
              if (currentAudioPlayer === audioPlayer) {{
                currentAudioPlayer = null;
              }}
              
              reject(error);
            }});
            
          }} catch (error) {{
            reject(error);
          }}
        }});
      }}
      
      function playAudio(audioData, format = 'wav', volume = 0.7, enableMouthSync = true, subtitle = null, subtitleDuration = 3000) {{
        if (audioPermissionGranted) {{
          audioQueue.push({{ 
            data: audioData, 
            format: format, 
            volume: volume, 
            enableSync: enableMouthSync,
            subtitle: subtitle,
            subtitleDuration: subtitleDuration
          }});
          processAudioQueue();
        }} else {{
          audioQueue.push({{ 
            data: audioData, 
            format: format, 
            volume: volume, 
            enableSync: enableMouthSync,
            subtitle: subtitle,
            subtitleDuration: subtitleDuration
          }});
          initializeAudioPermission();
        }}
      }}
      
      function stopAudio() {{
        if (isPlaying && currentAudioPlayer) {{
          currentAudioPlayer.pause();
          currentAudioPlayer.currentTime = 0;
          isPlaying = false;
          stopMouthSync();
        }}
        
        if (currentAudioPlayerTimeout) {{
          clearTimeout(currentAudioPlayerTimeout);
          currentAudioPlayerTimeout = null;
        }}
      }}
      
      function clearAudioQueue() {{
        audioQueue = [];
        stopAudio();
        isProcessingAudio = false;
        clearSubtitle(); // 清除字幕
        
        if (currentAudioPlayer) {{
          currentAudioPlayer.pause();
          currentAudioPlayer = null;
        }}
      }}
      
      // 摄像头相关函数
      async function requestCameraPermission() {{
        try {{
          const stream = await navigator.mediaDevices.getUserMedia({{
            video: {{ facingMode: currentFacingMode }}
          }});
          
          // 立即停止流，我们只是在测试权限
          stream.getTracks().forEach(track => track.stop());
          cameraPermissionGranted = true;
          return true;
        }} catch (error) {{
          console.error('摄像头权限被拒绝:', error);
          cameraPermissionGranted = false;
          return false;
        }}
      }}
      
      async function initCamera() {{
        try {{
          if (cameraStream) {{
            cameraStream.getTracks().forEach(track => track.stop());
          }}
          
          const constraints = {{
            video: {{
              facingMode: currentFacingMode,
              width: {{ ideal: 1280 }},
              height: {{ ideal: 720 }}
            }}
          }};
          
          cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
          cameraVideo.srcObject = cameraStream;
          
          return true;
        }} catch (error) {{
          console.error('初始化摄像头失败:', error);
          return false;
        }}
      }}
      
      function stopCamera() {{
        if (cameraStream) {{
          cameraStream.getTracks().forEach(track => track.stop());
          cameraStream = null;
        }}
        if (cameraVideo) {{
          cameraVideo.srcObject = null;
        }}
      }}
      
      async function capturePhoto() {{
        if (isCapturingPhoto) {{
          return;
        }}
        
        isCapturingPhoto = true;
        
        try {{
          if (!cameraPermissionGranted) {{
            const granted = await requestCameraPermission();
            if (!granted) {{
              showStatus('需要摄像头权限才能拍照');
              isCapturingPhoto = false;
              return;
            }}
          }}
          
          // 初始化摄像头
          const success = await initCamera();
          if (!success) {{
            showStatus('摄像头初始化失败');
            isCapturingPhoto = false;
            return;
          }}
          
          // 等待一小段时间确保摄像头准备就绪
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          if (!cameraVideo || !cameraStream) {{
            showStatus('摄像头未就绪');
            isCapturingPhoto = false;
            return;
          }}
          
          const canvas = document.getElementById('hiddenCanvas');
          const context = canvas.getContext('2d');
          
          // 设置canvas尺寸与视频相同
          canvas.width = cameraVideo.videoWidth || 640;
          canvas.height = cameraVideo.videoHeight || 480;
          
          // 绘制当前视频帧到canvas
          context.drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);
          
          // 转换为base64
          canvas.toBlob((blob) => {{
            const reader = new FileReader();
            reader.onload = () => {{
              const base64Data = reader.result.split(',')[1]; // 移除data:image/jpeg;base64,前缀
              
              // 发送到服务器
              if (socket) {{
                socket.emit('photo_captured', {{
                  image_data: base64Data,
                  format: 'jpeg',
                  width: canvas.width,
                  height: canvas.height,
                  facing_mode: currentFacingMode,
                  timestamp: Date.now()
                }});
                
                showStatus('照片已自动拍摄并发送');
              }}
              
              // 停止摄像头
              stopCamera();
              isCapturingPhoto = false;
            }};
            reader.readAsDataURL(blob);
          }}, 'image/jpeg', 0.8);
          
        }} catch (error) {{
          console.error('自动拍照失败:', error);
          showStatus('自动拍照失败: ' + error.message);
          stopCamera();
          isCapturingPhoto = false;
        }}
      }}
      
      async function startRecording() {{
        try {{
          socket = io();
          
          socket.on('connect', () => {{
            showStatus('音频流连接成功');
          }});
          
          socket.on('disconnect', () => {{
            showStatus('音频流连接断开');
          }});
          
          socket.on('play_audio', (data) => {{
            try {{
              const audioData = base64ToArrayBuffer(data.audio_data);
              playAudio(
                audioData, 
                data.format || 'wav', 
                data.volume || 0.7, 
                true,
                data.subtitle || null,
                data.subtitle_duration || 3000
              );
            }} catch (error) {{
              showStatus('处理音频失败: ' + error.message);
            }}
          }});
          
          socket.on('play_audio_with_sync', (data) => {{
            try {{
              const audioData = base64ToArrayBuffer(data.audio_data);
              playAudio(
                audioData, 
                data.format || 'wav', 
                data.volume || 0.7, 
                data.enable_mouth_sync !== false,
                data.subtitle || null,
                data.subtitle_duration || 3000
              );
            }} catch (error) {{
              showStatus('处理音频失败: ' + error.message);
            }}
          }});
          
          socket.on('clear_audio', () => {{
            clearAudioQueue();
            showStatus('音频队列已清空');
          }});
          
          socket.on('show_subtitle', (data) => {{
            showSubtitle(data.text, data.duration || 3000, data.force_replace !== false);
          }});
          
          socket.on('clear_subtitle', () => {{
            clearSubtitle();
          }});
          
          // 监听服务器请求拍照 - 自动执行
          socket.on('request_photo', (data) => {{
            showStatus('服务器请求拍照，正在自动拍摄...');
            capturePhoto();
          }});
          
          const stream = await navigator.mediaDevices.getUserMedia({{ 
            audio: {{
              sampleRate: 16000,
              channelCount: 1,
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true
            }}
          }});
          
          audioContext = new (window.AudioContext || window.webkitAudioContext)({{
            sampleRate: 16000
          }});
          
          source = audioContext.createMediaStreamSource(stream);
          
          function useScriptProcessor() {{
            processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            processor.onaudioprocess = (event) => {{
              const inputBuffer = event.inputBuffer;
              const inputData = inputBuffer.getChannelData(0);
              
              const pcmData = new Int16Array(inputData.length);
              for (let i = 0; i < inputData.length; i++) {{
                pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32767));
              }}
              
              if (socket && pcmData.length > 0) {{
                socket.emit('audio_chunk', pcmData.buffer);
              }}
            }};
            
            source.connect(processor);
            processor.connect(audioContext.destination);
          }}
          
          useScriptProcessor();
          
          isRecording = true;
          showStatus('开始录音...');
          
        }} catch (error) {{
          showStatus('无法访问麦克风: ' + error.message);
        }}
      }}
      
      function stopRecording() {{
        if (processor) {{
          processor.disconnect();
          processor = null;
        }}
        if (source) {{
          source.disconnect();
          source = null;
        }}
        if (audioContext) {{
          audioContext.close();
          audioContext = null;
        }}
        isRecording = false;
        showStatus('录音已停止');
      }}
      
      function base64ToArrayBuffer(base64) {{
        const binaryString = atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {{
          bytes[i] = binaryString.charCodeAt(i);
        }}
        return bytes.buffer;
      }}
      
      function waitForModelAndDetectParams() {{
        const checkModel = () => {{
          if (window._i && window._i.internalModel && window._i.internalModel.coreModel) {{
            detectedMouthParam = detectMouthParameter();
          }} else {{
            setTimeout(checkModel, 500);
          }}
        }};
        
        checkModel();
      }}
      
      window.addEventListener('load', () => {{
        // 创建隐藏的视频元素用于拍照
        cameraVideo = document.getElementById('hiddenVideo');
        if (!cameraVideo) {{
          cameraVideo = document.createElement('video');
          cameraVideo.id = 'hiddenVideo';
          cameraVideo.autoplay = true;
          cameraVideo.muted = true;
          cameraVideo.playsInline = true;
          cameraVideo.style.display = 'none';
          document.body.appendChild(cameraVideo);
        }}
        
        setTimeout(() => {{
          waitForModelAndDetectParams();
          startRecording();
        }}, 2000);
      }});
      
      window.addEventListener('beforeunload', () => {{
        stopRecording();
        clearAudioQueue();
        stopCamera();
        if (sharedAudioContext) {{
          sharedAudioContext.close();
        }}
        if (socket) {{
          socket.disconnect();
        }}
      }});
      
      // 去掉所有按键控制
      
      window.toggleMouthSync = function() {{
        mouthSyncEnabled = !mouthSyncEnabled;
        return mouthSyncEnabled;
      }};
      
      // 暴露字幕函数到全局作用域
      window.showSubtitle = showSubtitle;
      window.clearSubtitle = clearSubtitle;
    </script>
    <script type="module" crossorigin src="assets/live2d.js"></script>
  </head>
  <body>
    <div id="permissionModal" class="permission-modal hidden">
      <div class="modal-content">
        <div class="modal-title">音频播放权限</div>
        <div class="modal-text">
          为了给您带来更好的体验，需要您的允许来播放音频内容。<br>
          这将用于语音回复和背景音效。
        </div>
        <div class="modal-buttons">
          <button id="allowBtn" class="modal-btn btn-primary">允许播放</button>
          <button id="denyBtn" class="modal-btn btn-secondary">暂不允许</button>
        </div>
      </div>
    </div>
    
    <div id="statusMessage" class="status-message"></div>
    
    <div class="subtitle-container">
      <div id="subtitle" class="subtitle"></div>
    </div>
    
    <canvas id="hiddenCanvas"></canvas>
    
    <div id="app"></div>
    <canvas id="canvas2"></canvas>
  </body>
</html>
"""

@app.route('/')
def index():
    return generate_html()

@app.route('/Character/<path:path>')
def serve_models(path):
    return send_from_directory('Character', path)

@app.route('/assets/<path:path>')
def serve_static(path):
    return send_from_directory('assets', path)

@socketio.on('connect')
def handle_connect():
    print('web客户端连接成功')
    emit('status', {'message': '服务器连接成功'})
    if Global.web_asr_thread:
        terminate_thread(Global.web_asr_thread)
    if Global.asr_thread:
        terminate_thread(Global.asr_thread)
        
    Global.web_asr_thread = Thread(target=speech_recognition, args=(True,), daemon=True)
    Global.web_asr_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    print('web客户端断开连接')
    if Global.web_asr_thread:
        terminate_thread(Global.web_asr_thread)
    if Global.asr_thread:
        terminate_thread(Global.asr_thread)

    Global.asr_thread = Thread(target=speech_recognition, daemon=True)
    Global.asr_thread.start()

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        Global.web_audio_stream.write(data)
    except Exception as e:
        print(f"处理音频块失败: {e}")
        emit('error', {'message': f'音频处理错误: {str(e)}'})

@socketio.on('photo_captured')
def handle_photo_captured(data):
    """处理照片数据"""
    try:
        image_data = data.get('image_data')
        format_type = data.get('format', 'jpeg')
        width = data.get('width', 0)
        height = data.get('height', 0)
        facing_mode = data.get('facing_mode', 'environment')
        
        print(f"收到照片: {width}x{height}, 格式: {format_type}, 摄像头: {facing_mode}")
        
        image_bytes = base64.b64decode(image_data)
        
        filepath = f'temp/img.{format_type}'

        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        Global.received_photo.put(filepath)
        
        emit('status', {'message': '照片接收成功'})
        
    except Exception as e:
        print(f"处理照片失败: {e}")
        emit('error', {'message': f'照片处理错误: {str(e)}'})

def play_audio(audio_data, format='wav', subtitle=None, subtitle_duration=3000):
    """播放音频"""
    try:
        if isinstance(audio_data, (bytes, bytearray)):
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        else:
            audio_base64 = base64.b64encode(bytes(audio_data)).decode('utf-8')
        
        emit_data = {
            'audio_data': audio_base64,
            'format': format,
            'enable_mouth_sync': True
        }
        
        if subtitle:
            emit_data['subtitle'] = subtitle
            emit_data['subtitle_duration'] = subtitle_duration
        
        socketio.emit('play_audio', emit_data)

        return True
        
    except Exception as e:
        print(f"发送音频数据失败: {e}")
        return False

def play_audio_file(file_path, format=None, subtitle=None, subtitle_duration=3000):
    """播放音频文件"""
    try:
        if not os.path.exists(file_path):
            print(f"音频文件不存在: {file_path}")
            return False
        
        if format is None:
            ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            format = ext if ext in ['wav', 'mp3', 'ogg', 'm4a'] else 'wav'
        
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        return play_audio(audio_data, format, subtitle, subtitle_duration)
        
    except Exception as e:
        print(f"播放音频文件失败: {e}")
        return False

def clear_audio_queue():
    """清空音频播放队列"""
    try:
        socketio.emit('clear_audio')
        print("已发送清空音频队列指令")
        return True
    except Exception as e:
        print(f"发送清空音频队列指令失败: {e}")
        return False

def request_photo():
    """请求客户端拍照"""
    try:
        socketio.emit('request_photo', {
            'timestamp': int(time.time() * 1000),
            'message': '服务器请求拍照'
        })
        print("已发送拍照请求到客户端")
        return True
    except Exception as e:
        print(f"发送拍照请求失败: {e}")
        return False

def create_signed_cert():
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("正在生成自签名证书...")
        try:
            import subprocess
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-nodes',
                '-out', cert_file, '-keyout', key_file, '-days', '365',
                '-subj', '/C=CN/ST=State/L=City/O=Organization/CN=localhost'
            ], check=True)
            print("证书生成成功！")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("无法自动生成证书，请手动运行:")
            print("openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365")
            return False
    
    return True

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def run_web():
    with open('assets\live2d.js', 'r', encoding='utf-8') as f:
      js = f.readlines()

    path = Global.character["live2d_model"]
    path = path.replace('\\', '/')
    js[1581] = f'xb = "{path}",\n'
    js[1588] = f'_i.x = {Global.character["web_x"]};\n'
    js[1589] = f'_i.y = {Global.character["web_y"]};\n'
    js[1592] = f'_i.scale.set({Global.character["web_scale"]});\n'

    if 'watermark' in Global.character:
        js[1595] = f'_i.internalModel.coreModel.setParameterValueById("{Global.character["watermark"]}", 1);\n'
    else:
        js[1595] = '\n'

    with open('assets\live2d.js', 'w', encoding='utf-8') as f:
      f.writelines(js)

    local_ip = get_local_ip()
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert_file, key_file)
            print(f"Web对话接口: https://{local_ip}:{port}")
            socketio.run(app, port=port, host="0.0.0.0", ssl_context=context, debug=False, use_reloader=False)
        except Exception as e:
            print(f"HTTPS启动失败: {e}")
            print("回退到HTTP模式...")
            socketio.run(app, port=port, host="0.0.0.0", debug=False, use_reloader=False)
    else:
        print("未找到SSL证书文件")
        if create_signed_cert():
            run_web()
        else:
            print(f"Web对话接口: http://{local_ip}:{port}")
            print("注意: 手机浏览器可能需要HTTPS才能使用麦克风功能")
            socketio.run(app, port=port, host="0.0.0.0", debug=False)

Global.web_clear_audio = clear_audio_queue
Global.web_audio_stream = AudioStream()
Global.web_request_photo = request_photo