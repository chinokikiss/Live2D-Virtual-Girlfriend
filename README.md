<div align="center">

# 💕 Live2D Virtual Girlfriend

<img src="assets\avatar.gif" alt="Virtual Girlfriend Avatar" width="360" height="487" style="border-radius: 50%; margin: 20px 0;"/>

*基于Live2D驱动的虚拟女友项目*

**提供实时对话、触摸交互、情绪系统等完整的虚拟伴侣体验**

[![GitHub Stars](https://img.shields.io/github/stars/chinokikiss/Live2D-Virtual-Girlfriend?style=flat-square)](https://github.com/chinokikiss/Live2D-Virtual-Girlfriend)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg?style=flat-square)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10--3.11-blue.svg?style=flat-square)](https://python.org)
![QQ群](https://img.shields.io/badge/QQ群-768397399-brightgreen?logo=tencent-qq&logoColor=white)

---

</div>

</div>

## 演示视频

📺 [观看演示视频](https://www.bilibili.com/video/BV169HPzEEGX)

## 功能特性
- ✅ **实时语音对话**
- ✅ **触摸交互**
- ✅ **实时字幕**
- ✅ **情绪表达**
- ✅ **表情播放**
- ✅ **语音打断**
- ✅ **随机动画播放**
- ✅ **声纹识别**
- ✅ **长期记忆** - *支持动态添加、修改知识图谱、时间点记忆查询，暂不支持遗忘机制*
- ✅ **屏幕内容识别**
- ✅ **MCP调用** - *更便捷的工具调用*
- ✅ **深度联网搜索** - *自动爬虫，支持游览器操作，网络资源下载*
- ✅ **屏幕控制** - *模拟鼠标、键盘输入，支持实时解说*
- ✅ **代码执行** - *代码能做到什么，它就能做到什么*
- ✅ **主动对话** - *计时器触发，暂时不能感知环境*
- ✅ **点歌功能** - *网易云，UVR5分离人声，RVC翻唱*
- ✅ **网页对话** - *支持手机游览器直接对话、字幕显示、语音打断、拍照识别*
- 🔄 **VTuber直播**
- 🔄 **UI界面开发**
- 🔄 **ONNX加速** - *目前实现了SenseVoiceSmall、speech_campplus_sv_zh-cn_16k-common 转onnx，准备将GPT_SoVITS v2proplus 转onnx*
- 🔄 **AutoAgent** - *更加智能的智能体团队*
- ❌ **纯API版本**
- ❌ **EasyVtuber**
- ❌ **角色卡社区**
- ❌ **动作播放**
- ❌ **游戏解说**
- ❌ **自主玩游戏**
- ✅ **整合包**
- ❌ **记忆可视化管理**

</div>


## 性能表现

| 项目 | 规格 |
|------|------|
| **显存需求** | 3-4GB（包含GPTSoVits） |
| **测试环境** | i5 13代 + RTX 3050 笔记本 |
| **首次响应** | 1-2秒 (豆包1.6 flash 0.5-0.7秒) |


## 环境要求

- **Python** < 3.12
- **Anaconda** 包管理器
- **CUDA Toolkit**
- **Microsoft Visual C++**

## 🚀 部署导航

### 📦 整合包
**高速下载** - [🔗Live2D-Virtual-Girlfriend-main.zip](https://modelscope.cn/models/chinokiki/chinokikisss/resolve/master/Live2D-Virtual-Girlfriend-main.zip)

### 🎵 语音合成
**GPT-SoVITS** - [🔗整合包](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4#KTvnO)

**Kokoro** - [🔗GitHub仓库](https://github.com/remsky/Kokoro-FastAPI)

### 🎤 歌曲翻唱
**RVC** - [🔗整合包](https://www.yuque.com/flowercry/hxf0ds)

## 部署步骤

### 1. 环境准备

**创建虚拟环境**
```bash
conda create -n live2d_chat python=3.11
conda activate live2d_chat
```

**安装依赖**
```bash
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia # 建议配置conda镜像源
pip install -r requirements.txt # 建议配置pip镜像源
pip install modelscope[audio] -f https://modelscope.oss-cn-beijing.aliyuncs.com/releases/repo.html
python download.py
playwright install

# 以下建议开VPN下载
python -m spacy download zh_core_web_sm
python download_vpn.py
```

### 2. 配置文件设置

修改`config.toml`文件中的以下配置：

#### 用户角色配置
在`user_name`字段填入自己要扮演的角色名，这将影响对话中的身份设定。

#### 声纹识别配置
录制个人语音样本，将音频文件路径填入`your_voice`字段。

#### 对话模型配置
在`["required"]`中填入OpenAI格式的API信息：
- `base_url`：API服务地址
- `api_key`：API密钥
- `chat_model`：聊天模型

#### 辅助模型配置
在`["auxiliary"]`中填入支持调用工具、价格低、能力强的大模型API信息，用于辅助生成内容：
- `base_url`：API服务地址
- `api_key`：API密钥
- `chat_model`：聊天模型

### 3. 启动程序
```bash
python main.py
```

## 语音合成优化
在 *GPT-SoVITS-main\api_v2.py*、*Kokoro-FastAPI-master\api\src\main.py* 中插入以下代码：
```python
import psutil
import os

def set_high_priority():
    p = psutil.Process(os.getpid())
    try:
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        print("已将进程优先级设为 High")
    except psutil.AccessDenied:
        print("权限不足，无法修改优先级（请用管理员运行）")
set_high_priority()
```

## mcp_configs.json 配置指南

### 概述

`mcp_configs.json` 是用于配置 MCP (Model Context Protocol) 服务的配置文件。该文件包含一个 JSON 数组，用于定义多个 MCP 服务的连接配置。

### 文件结构

配置文件采用 JSON 格式，根级别是一个数组，包含多个服务配置对象。
```json
[
  {
    "name": "服务名称",
    "type": "通信模式",
    "target": "目标路径或地址"
  }
]
```

### 配置参数说明

#### name
- **类型**: 字符串
- **描述**: MCP 服务的自定义名称

#### type
- **类型**: 字符串
- **可选值**: 
  - `"stdio"` - 标准输入输出通信模式
  - `"sse"` - 服务器发送事件通信模式
- **描述**: 指定与 MCP 服务通信的协议类型

#### target
- **类型**: 字符串
- **描述**: 根据通信类型指定不同的目标
  - 当 `type` 为 `"stdio"` 时：指定服务器脚本文件路径（.py 或 .js 文件）
  - 当 `type` 为 `"sse"` 时：指定 SSE 服务的网址

## 我的感想
*暂时没感想...*


## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=chinokikiss/Live2D-Virtual-Girlfriend&type=Date)](https://star-history.com/#chinokikiss/Live2D-Virtual-Girlfriend&Date)













