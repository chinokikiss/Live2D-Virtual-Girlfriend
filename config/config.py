import os
import ast
import toml
from queue import Queue

with open('config.toml', 'r', encoding='utf-8-sig') as f:
    config = toml.loads(f.read())

with open(config['character_toml'], 'r', encoding='utf-8-sig') as f:
    character = toml.loads(f.read())
dir = os.path.dirname(config['character_toml'])
character["live2d_model"] = os.path.join(dir, character["live2d_model"])
if "ref_audio" in character:
    character["ref_audio"] = os.path.join(dir, character["ref_audio"])
character["system_prompt"] = os.path.join(dir, character["system_prompt"])
character["exp"] = os.path.join(dir, character["exp"])

class Global:
    # 全局变量
    subtitle_lang = 'zh'
    happy = 5
    sign1 = False
    exist = True
    send_text_thread = None
    mcp_client = None
    Agent_return = {}

    user_name: str
    character: dict
    auxiliary: dict
    required: dict
    exp_queue: Queue

setattr(Global, 'character', character)
for key, value in config.items():
    if key == 'hot_word':
        value = ast.literal_eval(value)
    setattr(Global, key, value)