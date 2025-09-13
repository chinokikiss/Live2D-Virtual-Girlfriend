<div align="center">

# 💕 Live2D Virtual Girlfriend

<img src="temp\avatar.png" alt="Virtual Girlfriend Avatar" width="200" height="200" style="border-radius: 50%; margin: 20px 0;"/>

*基于Live2D驱动的虚拟女友项目*

**提供实时对话、触摸交互、情绪系统等完整的虚拟伴侣体验**

[![GitHub Stars](https://img.shields.io/github/stars/chinokikiss/Live2D-Virtual-Girlfriend?style=flat-square)](https://github.com/chinokikiss/Live2D-Virtual-Girlfriend)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10--3.11-blue.svg?style=flat-square)](https://python.org)

---

</div>

## 功能特性

- **实时语音对话交互**
- **Live2D触摸交互**
- **实时字幕显示系统**
- **情绪识别与表达**
- **动态表情系统**
- **随机动画播放**
- **说话人身份确认**
- **唤醒与睡眠机制**
- **长期记忆存储**
- **屏幕内容识别**

## 性能表现

| 项目 | 规格 |
|------|------|
| **显存需求** | 3-4GB（包含GPTSoVits） |
| **测试环境** | i5 13代 + RTX 3050 笔记本 |
| **首次响应** | 1-2秒 |
| **API响应** | 0.5-0.7秒 |

## 环境要求

- **Python** < 3.12
- **Anaconda** 包管理器
- **Visual C++** 14 运行库
- **CUDA显卡** 支持（可选CPU运行）

## 安装步骤

### 1. 环境准备

安装Anaconda并创建Python虚拟环境。建议使用Python版本低于3.12。

### 2. 安装PyTorch

配置conda镜像源后执行：
```bash
conda install torch torchvision torchaudio
```
注意：以上命令安装CPU版本，如需GPU版本请上网查询教程。

### 3. 安装依赖
```bash
pip install -r requirements.txt
```
建议配置pip镜像源以提高下载速度。

### 4. 下载NLP模型
```bash
python -m spacy download zh_core_web_sm
```

### 5. 下载embedding模型
```bash
python download.py
```

### 6. 配置文件设置

修改`config.toml`文件中的以下配置：

#### API配置
在`["required"]`中填入OpenAI格式的API信息：
- `base_url`：API服务地址
- `api_key`：API密钥
- `chat_model`：使用的聊天模型

#### 语音配置
录制个人语音样本，将音频文件路径填入`your_voice`字段。

#### 设备配置
根据硬件情况修改`device`字段，按照配置文件中的注释说明进行设置。

### 7. 启动程序

运行`run.bat`或执行`python main.py`

首次启动将自动下载必要的模型文件，请耐心等待。

## 角色卡制作

### 目录结构

以`Character/llny`为例：
```
- mianfeimox/：Live2D模型文件夹
- exp.json：表情配置文件
- llny.json：角色配置文件
- 人设.txt：角色人设描述
- 日配.ogg：参考语音文件
- memory：记忆文件(不用一起复制，会自动生成)
```
### 表情配置文件

`exp.json`定义了Live2D模型的表情映射关系：
```json
{
    "- -": "面无表情",
    "阿尼亚": "双手比心的表情",
    "比心": "双手比心的表情",
    "荷包蛋": "两个圆圆的眼睛",
    "口罩": "戴着口罩的表情",
    "哭": "哭泣的表情",
    "脸黑": "脸色阴沉的表情",
    "脸红": "脸颊通红的表情",
    "生气": "愤怒的表情",
    "吐舌": "吐出舌头的表情",
    "外套": "穿着外套的表情",
    "星星": "眼睛发出星星的表情",
    "眼镜": "戴着眼镜的表情"
}
```
### 角色配置文件

`llny.json`包含角色的完整配置信息：
```json
{
    "live2d_model": "mianfeimox\\llny.model3.json",
    "ref_audio": "日配.ogg",
    "prompt_text": "ほら、今日も頑張って！私が手伝ってあげるから！",
    "prompt_lang": "ja",
    "system_prompt": "人设.txt",
    "exp": "exp.json",
    "max_rms_scale": 8000,
    "ttf_rgb": [255, 182, 193],
    "subtitle_speed": 0.13,
    "speed_factor": 1.0,
    "wake_word": ["在吗"],
    "end_word": ["再见"]
}
```
#### 配置参数说明

- `live2d_model`：Live2D模型文件相对路径
- `ref_audio`：参考音频文件相对路径
- `prompt_text`：参考音频对应文本
- `prompt_lang`：文本语言（zh中文/en英文/ja日文）
- `system_prompt`：人设文件相对路径
- `exp`：表情配置文件相对路径
- `max_rms_scale`：口型同步幅度（数值越大幅度越小）
- `ttf_rgb`：字幕颜色RGB值
- `subtitle_speed`：字幕生成速度（数值越小速度越快）
- `speed_factor`：语音生成语速
- `wake_word`：唤醒词列表
- `end_word`：休眠词列表

## 开发计划

- 开发UI界面
- 制作一键懒人包
- 扩展VTuber应用场景



