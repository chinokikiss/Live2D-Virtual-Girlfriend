import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import re
import time
import json
import tempfile
from datetime import datetime
import src.loader
from queue import Queue
from openai import OpenAI
from threading import Thread
from PyQt5.QtWidgets import QApplication
from config import Global
import live2d.v3 as live2d
from gui.gui import Live2DCanvas
from utils.other import wait_send_over, capture_screen
from utils.func_queue import FuncQueue
from src.asr import speech_recognition
from src.tts import AudioQueue, gptsovits_audio, text_process
from src.tools import identify_role
from src.rvc import get_music163
from src import api

class Agent:
    def __init__(self, win):
        with open(Global.character["system_prompt"], 'r', encoding='utf-8') as f:
            prompt = f.read()
            prompt = prompt.replace('{{user}}', Global.user_name)
            prompt = prompt.replace('{{char}}', Global.user_name)
        
        self.win = win
        Global.exp_queue = Queue()
        if Global.character["exp"]:
            with open(Global.character["exp"], 'r', encoding='utf-8') as f:
                self.exp = json.load(f)
        else:
            self.exp = {}
        
        if "watermark" in Global.character:
            self.win.model.SetParameterValue(Global.character["watermark"], 1, 1)
    
        live2d_model = Global.character["live2d_model"]
        dirname = os.path.dirname(live2d_model)
        basename = os.path.basename(live2d_model)
        cdi3_path = os.path.join(dirname, basename.split('.')[0]+'.cdi3.json')
        with open(cdi3_path, 'r', encoding='utf-8') as f:
            cdi3_json = json.load(f)
        Global.parts = {}
        for i in cdi3_json["Parts"]:
            Global.parts[i["Id"]] = i["Name"]
        
        Global.exp_params = {}
        expressions_path = os.path.join(dirname, 'expressions')
        if os.path.exists(expressions_path):
            for filename in os.listdir(expressions_path):
                if filename.endswith('.json'):
                    exp_path = os.path.join(expressions_path, filename)
                    with open(exp_path, 'r', encoding='utf-8') as f:
                        exp_json = json.load(f)
                    Global.exp_params[filename.split('.')[0]] = [exp_json["Parameters"][0]["Id"], exp_json["Parameters"][0]["Value"]]
        
        self.exp['正常'] = '正常表情'
        self.speed_factor = Global.character["speed_factor"]
        self.prompt_lang = Global.character["prompt_lang"] if "prompt_lang" in Global.character else None
        self.text_lang = Global.character["text_lang"]

        tool_prompt = f"""
        工具能力:
        你不仅能调用工具，还拥有强大的AI助手工具：
        - CLI_Agent: 执行命令行操作，处理系统任务
        - GUI_Agent: 自动化界面操作，控制应用程序  
        - Web_Agent: 进行深度网络搜索，获取详细信息
        """ if Global.modelscope['api_key'] else ''

        system_prompt = f"""
        今天是 {datetime.today().strftime('%Y年%m月%d日')}
        你扮演 {Global.character["name"]}，我扮演 {Global.user_name}。
        {prompt}

        表情设置: {self.exp}
        {tool_prompt}

        当你调用工具后，工具正在执行期间，你应该：
        1. 正常回应用户的任何新对话或问题
        2. 不要重复调用相同的工具
        3. 可以简单提及"刚才的任务还在进行中"但继续正常聊天

        对话规范:
        1. 这是实时语音对话场景，请使用自然流畅的口语化表达
        2. 避免过于正式或书面化的表达方式
        3. 可以适当使用语气词、感叹词让对话更生动
        4. 每次回复都要简洁明了，避免重复或冗长的表达
        5. 保持轻松愉快的对话氛围
        6. 严禁使用任何形式的括号描述，包括但不限于：
           - 动作描写：(笑了笑)、(点头)、(思考)
           - 心理描写：(内心想着)、(感到疑惑)
           - 状态描写：(紧张地)、(开心地)
           - 任何用()、[]包裹的描述性文字

        工具调用规范:
        1. 当在调用工具时，记得告知用户需要稍等片刻，等到调用工具结果返回后，再回答用户答案
        2. 仅在用户有相关需求时才调用工具，不要无缘无故调用工具

        输出要求:
        1. 每次回复末尾必须添加情绪数据: {{"happy":int, "exp":str}}
        2. happy值范围: [0-10]，表示当前开心程度 
        3. exp值从表情设置中选择,表示当前表情状态
        4. 使用口语化、自然的表达方式
        5. 保持对话的连贯性和互动性
        """
        system_prompt = '\n'.join(line[8:] for line in system_prompt.splitlines())

        self.messages = [{'role': 'system', 'content': system_prompt}]
        self.client = OpenAI(
            base_url=Global.required['base_url'],
            api_key=Global.required['api_key']
        )
        self.auxiliary_client = OpenAI(
            base_url=Global.auxiliary['base_url'],
            api_key=Global.auxiliary['api_key']
        )

        self.memory_save = []

        Global.kokoro_client = OpenAI(
            base_url=Global.kokoro_api, 
            api_key="not-needed"
        )

        if "voice" in Global.character:
            Global.audio_queue = AudioQueue(self.win.model, sample_rate=24000)
        else:
            Global.audio_queue = AudioQueue(self.win.model, sample_rate=32000)

        # mcp
        self.mcp_client = Global.mcp_client
        with open('mcp_configs.json', 'r', encoding='utf-8') as f:
            mcp_configs = json.load(f)
        if self.mcp_client and mcp_configs:
            self.mcp_client.connect_servers_sync(mcp_configs)
            self.mcp_tools, self.tool_to_server = self.mcp_client.get_all_tools()
        else:
            self.mcp_tools, self.tool_to_server = [], None

        self.tools = []

        # agent
        if Global.modelscope['api_key']:
            with open('assets\\agents.json', 'r', encoding='utf-8') as f:
                agents = json.load(f)
            self.tools += agents
        
        # tools
        with open('assets\\tools.json', 'r', encoding='utf-8') as f:
            tools = json.load(f)
        for i in mcp_configs:
            tools[2]["function"]["description"] += i["feature"] + '\n'
        self.tools += tools

        # 初始化
        Global.func_queue3 = FuncQueue()
    
    def call_tool(self, tool_name, tool_args):
        print('tool', tool_name, tool_args)
        
        py = ''
        temp_data = {}
        if tool_name == "CLI_Agent":
            py = 'agents\CLIAgent.py'
            temp_data["WORKDIR"] = 'temp'

        elif tool_name == "GUI_Agent":
            py = 'agents\GUIAgent.py'

        elif tool_name == "Web_Agent":
            py = 'agents\WebAgent.py'

        elif tool_name == "identify_role":
            img = capture_screen()
            tool_result = identify_role(img)

        elif tool_name == "sing_song":
            if Global.rvc.ok:
                try:
                    song, lyric = get_music163(tool_args['keyword'])
                    print('歌曲下载完毕', song, lyric)
                    if song and lyric:
                        Global.rvc.cover_song(os.path.abspath("temp\music"))
                        tool_result = f"【RVC】准备翻唱歌曲。歌曲信息：{song}。歌词内容：{lyric}。请你说出简短的演唱开场白。"
                    else:
                        tool_result = "搜索不到相关歌曲"
                except Exception as e:
                    print('RVC:', e)
                    tool_result = "RVC服务端未响应"
            else:
                tool_result = "RVC服务端未启动"

        else:
            response = self.auxiliary_client.chat.completions.create(
                model=Global.auxiliary['chat_model'],
                messages=[{'role': 'user', 'content': f'{self.messages[1:]}\n请根据以上对话记录，调用合适的工具'}],
                tools=self.mcp_tools,
                tool_choice="required"
            )
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                if self.tool_to_server:
                    tool_result = self.mcp_client.call_tool(function_name, function_args, self.tool_to_server)
                else:
                    return
            else:
                tool_result = message.content
        
        if py:
            agent_id = int(time.time()*1000)
            temp_data["task_content"] = tool_args["task_content"]
            temp_data["agent_id"] = agent_id

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(temp_data, f, ensure_ascii=False)
                temp_file = f.name

            os.system(f'start /min cmd /c python {py} "{temp_file}"')

            while True:
                if agent_id in Global.Agent_return:
                    tool_result = Global.Agent_return[agent_id]
                    del Global.Agent_return[agent_id]
                    break
                time.sleep(1)

        wait_send_over()

        tool_call_id = f"call_{int(time.time()*1000)}"
        self.messages.append({
            'role': 'assistant', 
            'content': '', 
            'tool_calls': [
                {
                    'id': tool_call_id,
                    'type': 'function',
                    'function': {
                        'name': tool_name,
                        'arguments': ''
                    }
                }
            ]
        })
        self.messages.append({
            'role': 'tool',
            'content': str(tool_result),
            'tool_call_id': tool_call_id
        })
        self.messages.append({'role':'user', 'content':'查看工具返回结果'})
        self.send_audio_text(tool=False)

        if tool_name == "sing_song" and "【RVC】准备翻唱歌曲" in tool_result:
            wait_send_over()
            Global.rvc.play(lyric)
            self.messages.append({'role':'user', 'content':'你已唱完歌曲'})
            self.send_audio_text(tool=False)
    
    def send_audio_text(self, text=None, img=None, tool=True):
        self.t = time.time()

        # 重置主动对话
        Global.win.initiative_reset()

        self._messages = self.messages.copy()

        # 眼球归位
        Global.eyeball_animator.move_to_center()

        memory_results = None
        if not text is None:
            memory_results = Global.memory.semantic_search(text, top_k=Global.memory_top_k, similarity_threshold=Global.memory_similarity_threshold)
            print(f"\n记忆检索(耗时: {time.time()-self.t:.2f}s) {len(memory_results)}")

            content = []
            if not img is None:
                content.append({'type': 'image_url', 'image_url': {'url': f"data:image/png;base64,{img}"}, 'max_pixels': Global.required['max_pixels']})
            if memory_results:
                memory_context = Global.memory.build_context(memory_results)
                print(f'```\n{memory_context}\n```')
                self._messages.append({'role':'user', 'content':f"以下是当前对话的相关记忆片段，这些是你过往的经历和记忆，无关记忆请忽略：\n{memory_context}"})

            content.append({"type": "text", "text": text})
            self._messages.append({'role':'user', 'content':content})
            self.messages.append({'role':'user', 'content':text})
            
            try:
                json.loads(text)
                is_json = True
            except (json.JSONDecodeError, ValueError):
                is_json = False
            if not is_json:
                self.memory_save.append({'role':'user', 'content':text})
        
        self.flag = True
        self.t = time.time()

        chat_params = {
            "model": Global.required['chat_model'],
            "messages": self._messages,
            "stream": True,
            "temperature": Global.required['temperature'],
            "top_p": Global.required['top_p'],
            "max_tokens": Global.required['max_tokens'],
            "extra_body": {
                "thinking": {"type": "disabled"}
            }
        }
        if tool and self.tools:
            chat_params["tools"] = self.tools
        response = self.client.chat.completions.create(**chat_params)

        temp = ''
        message_content = ''
        tool_calls = []
        flag1 = ''

        for chunk in response:
            if chunk.choices:
                choice = chunk.choices[0]
                if choice.delta.tool_calls:
                    for tool_call in choice.delta.tool_calls:
                        if tool_call.index is not None:
                            while len(tool_calls) <= tool_call.index:
                                tool_calls.append({
                                    'id': '',
                                    'type': 'function',
                                    'function': {'name': '', 'arguments': ''}
                                })
                            
                            if tool_call.id:
                                tool_calls[tool_call.index]['id'] = tool_call.id
                            if tool_call.function:
                                if tool_call.function.name:
                                    tool_calls[tool_call.index]['function']['name'] = tool_call.function.name
                                if tool_call.function.arguments:
                                    tool_calls[tool_call.index]['function']['arguments'] += tool_call.function.arguments

                if choice.delta.content:
                    content = chunk.choices[0].delta.content
                    for content_chr in content:
                        temp += content_chr

                        flag = content_chr in ['。', '，', '！', '？', '、', '~', '…', '!', '?', '\n'] or temp[-3:] == '...'
                        if flag1:
                            flag = False
                            if content_chr in [')', '}', ']', '）', '】', '》']:
                                flag1 = ''
                                flag = True
                        else:
                            if content_chr in ['(', '{', '[', '（', '【', '《']:
                                flag1 = content_chr

                        if flag:
                            if self.flag:
                                self.flag = False
                                print(f"\nLLM(耗时: {time.time()-self.t:.2f}s) {temp}")
                            self.t = time.time()

                            text, tran_text = text_process(temp, Global.subtitle_lang, self.text_lang, length=Global.cut_length)
                            if len(tran_text) > 1:
                                print(f"\nLLM {temp}")
                                print(f"\n翻译(耗时: {time.time()-self.t:.2f}s) {tran_text}")
                                Global.func_queue1.add(
                                    gptsovits_audio,
                                    (text, tran_text, self.text_lang, self.prompt_lang, self.speed_factor)
                                )

                                temp = ''

                    message_content += content
                    
                    match = re.findall(r'\{[^)]*\}', message_content)
                    for i in match:
                        try:
                            json_data = json.loads(i)
                        except:
                            json_data = {}
                        print(json_data)
                        if 'happy' in json_data:
                            Global.happy = json_data['happy']
                            Global.emotion_animator.start(json_data['happy'])
                        if 'exp' in json_data:
                            if json_data['exp'] in self.exp.keys() and json_data['exp'] != '正常':
                                Global.exp_queue.put(json_data['exp'])

        if not temp and self.flag and tool_calls:
            temp = "稍等片刻~"

        if temp:
            if self.flag:
                self.flag = False
                print(f"\nLLM(耗时: {time.time()-self.t:.2f}s) {temp}")
            self.t = time.time()

            text, tran_text = text_process(temp, Global.subtitle_lang, self.text_lang, length=1)
            if len(tran_text) > 1:
                print(f"\nLLM {temp}")
                print(f"\n翻译(耗时: {time.time()-self.t:.2f}s) {tran_text}")
                Global.func_queue1.add(
                    gptsovits_audio,
                    (text, tran_text, self.text_lang, self.prompt_lang, self.speed_factor)
                )

        assistant_message = {'role': 'assistant', 'content': message_content}
        if tool_calls:
            assistant_message['tool_calls'] = tool_calls[:1]

        self.messages.append(assistant_message)
        if tool_calls:
            tool_call = tool_calls[0]
            self.messages.append({
                'role': 'tool',
                'content': f"执行成功: {tool_call['function']['name']} - 工具已经正在执行中，结果过一会返回，不用再重复调用",
                'tool_call_id': tool_call['id']
            })
        if len(self.messages) >= Global.context_length:
            self.messages.pop(1)
            self.messages.pop(1)
            if self.messages[1]['role'] == "tool":
                self.messages.pop(1)

        self.memory_save.append({'role':'assistant', 'content':message_content})
        if len(self.memory_save) >= Global.save_memory_steps:
            Global.func_queue3.add(Global.memory.add_conversation, (self.memory_save.copy(),))
            self.memory_save = []
        
        if tool and tool_calls:
            tool_call = tool_calls[0]
            tool_name = tool_call['function']['name']
            try:
                tool_args = json.loads(tool_call['function']['arguments'])
            except json.JSONDecodeError:
                tool_args = {}

            Thread(target=self.call_tool, args=(tool_name, tool_args), daemon=True).start()

if __name__ == '__main__':

    live2d.init()
    app = QApplication(sys.argv)
    win = Live2DCanvas()
    win.show()
    Global.win = win

    my_agent = Agent(win)
    Global.send_audio_text = my_agent.send_audio_text
    
    Thread(target=speech_recognition, daemon=True).start()
    Thread(target=api.run, daemon=True).start()


    sys.exit(app.exec())
