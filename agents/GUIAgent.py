import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import base64
import io
import time
import requests
import pyperclip
import pyautogui
from openai import OpenAI
from config import Global
from agents.extra_tool import VLM
from rich.console import Console
from rich.panel import Panel

console = Console()
scale = pyautogui.size().width/1261
pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True

tools = [
    {
        "type": "function",
        "function": {
            "name": "click_position",
            "description": "点击屏幕上的指定位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "屏幕X坐标"
                    },
                    "y": {
                        "type": "number",
                        "description": "屏幕Y坐标"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "double_click_position",
            "description": "双击屏幕上的指定位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "屏幕X坐标"
                    },
                    "y": {
                        "type": "number",
                        "description": "屏幕Y坐标"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "right_click_position",
            "description": "右键点击屏幕上的指定位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "屏幕X坐标"
                    },
                    "y": {
                        "type": "number",
                        "description": "屏幕Y坐标"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "移动鼠标到指定位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "屏幕X坐标"
                    },
                    "y": {
                        "type": "number",
                        "description": "屏幕Y坐标"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "drag_mouse",
            "description": "从一个位置拖动到另一个位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {
                        "type": "number",
                        "description": "起始X坐标"
                    },
                    "start_y": {
                        "type": "number",
                        "description": "起始Y坐标"
                    },
                    "end_x": {
                        "type": "number",
                        "description": "结束X坐标"
                    },
                    "end_y": {
                        "type": "number",
                        "description": "结束Y坐标"
                    },
                    "duration": {
                        "type": "number",
                        "description": "拖动持续时间（秒）",
                        "default": 0.5
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["start_x", "start_y", "end_x", "end_y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "滚动鼠标",
            "parameters": {
                "type": "object",
                "properties": {
                    "clicks": {
                        "type": "number",
                        "description": "滚动的点击数（正数向上，负数向下）"
                    },
                    "x": {
                        "type": "number",
                        "description": "滚动前移动鼠标到的X坐标"
                    },
                    "y": {
                        "type": "number",
                        "description": "滚动前移动鼠标到的Y坐标"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["clicks"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "输入文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要输入的文本"
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "是否在输入后按回车键，默认为false",
                        "default": False
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "按下单个按键（如enter, tab, esc等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "要按下的按键名称"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "按下组合键（如ctrl+c, alt+tab等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "要按下的按键列表"
                    },
                    "wait": {
                        "type": "number",
                        "description": "操作后等待时间（秒），默认为0.5",
                        "default": 0.5
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
                "name": "VLM",
                "description": "使用视觉语言模型识别和分析屏幕截图的详细内容，能够理解图像中的文字、内容等信息",
                "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "对图像分析的具体要求或问题，例如：'识别屏幕上的所有文字内容'、'找出错误信息'等"
                    }
                },
                "required": ["text"]
            }
        }
    }
]

event_check_prompt = '''
你需要分析Agent当前的操作状态，并生成适合AI女友解说的事件信息。

输出格式为JSON，不用输出代码块：
{
    "当前操作": "正在进行的具体操作描述",
    "操作状态": "准备中|进行中|已完成|失败",
    "可见结果": "用户当前能看到的具体内容或输出结果，如果没有则为null",
    "下一步预期": "下一步将要做什么",
    "解说提示": "给AI女友的解说建议，告诉她应该如何向用户解释当前情况"
}
'''

SYSTEM_PROMPT = """
你现在是一个屏幕自动化操作Agent，叫GUIAgent，你可以通过查看屏幕并执行各种鼠标和键盘操作来帮助用户完成任务。

你的主要能力包括：
1. 捕获和分析屏幕图像
2. 控制鼠标移动、点击和拖拽
3. 输入文本和按键
4. 执行组合键操作

工作流程：
1. 先分析屏幕内容，仔细思考你接下来要进行什么操作
2. 执行鼠标和键盘操作

当你根据屏幕内容判断出用户的任务已经完成时，请输出 [任务完成] 标记。

行为规范：
- 如果屏幕没有返回什么有效信息，也不要放弃，可以尝试一些快捷键（如win键）
- 不要失败了就一直重复尝试
- 游览器优先使用edge

重要提示：每个操作函数都有一个可选的wait参数（单位：秒），用于指定操作后需要等待的时间。根据屏幕内容动态调整等待时间：
- 对于需要页面加载或渲染的操作（如打开应用、切换页面），使用较长的等待时间（3-5秒）
- 对于常规操作（如点击按钮、输入文本），使用中等等待时间（0.5-2秒）
- 对于即时响应操作（如移动鼠标、简单按键），使用较短等待时间（0.1-0.5秒）
- 当不确定时，默认使用0.5秒
"""

class Agent:
    def __init__(self):
        self.client = OpenAI(
            api_key=Global.modelscope['api_key'],
            base_url=Global.modelscope['base_url']
        )
        self.messages = [{'role':'system', 'content':SYSTEM_PROMPT}]
    
    def identify(self):
        screen_result = capture_screen()
        if len(self.messages) > 2:
            text = f"任务:'{self.task_content}'，上下文:'{self.messages[-2:]}'，"+"先根据图像判断你是否成功完成上一个的操作，最后检测图像中所有可能对任务有帮助的对象并返回它们的坐标位置。输出格式应为：{“bbox_2d”: [x1, y1, x2, y2], “label”: 该对象的详细名称}。注意不要返回虚假坐标和虚假对象"
        else:
            text = f"任务:'{self.task_content}'，"+"检测图像中所有可能对任务有帮助的对象并返回它们的坐标位置。输出格式应为：{“bbox_2d”: [x1, y1, x2, y2], “label”: 该对象的详细名称}。注意不要返回虚假坐标和虚假对象"
        messages2 = [{
            'role': 'user',
            'content': [
                {
                    "type": "text", 
                    "text": text
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screen_result['image']}"}
                }
            ]
        }]

        response = self.client.chat.completions.create(
            model='Qwen/Qwen2.5-VL-72B-Instruct',
            messages=messages2,
            stream=True
        )

        console.print("\n[bold magenta]Qwen2.5-VL Response:[/bold magenta]")
        res = ''
        for chunk in response:
            if chunk.choices[0].delta.content:
                res += chunk.choices[0].delta.content
                console.print(chunk.choices[0].delta.content, end='')
        console.print()

        return res
    
    def request(self, task_content):
        self.task_content = task_content
        self.messages.append({'role':'user', 'content':task_content})

        while True:
            self.messages.append({'role': 'user', 'content': f'当前屏幕:\n{self.identify()}'})

            response = self.client.chat.completions.create(
                model='Qwen/Qwen3-235B-A22B-Thinking-2507',
                messages=self.messages,
                stream=True,
                tools=tools,
                temperature=0.6,
                top_p=0.95
            )

            console.print("\n[bold blue]Agent Response:[/bold blue]")
            content = ''
            assistant_message = {'role': 'assistant', 'content': ''}
            reasoning = True
            
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.reasoning_content:
                    if reasoning:
                        console.print(delta.reasoning_content, end='', style="dim")
                    else:
                        console.print(delta.reasoning_content, end='')
                    assistant_message['content'] += delta.reasoning_content
                if delta.content:
                    if reasoning:
                        reasoning = False
                    console.print(delta.content, end='')
                    content += delta.content
                if delta.tool_calls:
                    if 'tool_calls' not in assistant_message:
                        assistant_message['tool_calls'] = []
                    for tool_call in delta.tool_calls:
                        if len(assistant_message['tool_calls']) <= tool_call.index:
                            assistant_message['tool_calls'].append({
                                'id': tool_call.id,
                                'type': 'function',
                                'function': {
                                    'name': tool_call.function.name,
                                    'arguments': tool_call.function.arguments or ''
                                }
                            })
                        else:
                            assistant_message['tool_calls'][tool_call.index]['function']['arguments'] += tool_call.function.arguments or ''
            
            console.print()
            self.messages.append(assistant_message)

            # 事件检测
            if Global.modelscope['agent_event'] and '[任务完成]' not in content:
                event_check_messages = [
                    {'role': 'system', 'content': event_check_prompt},
                    {'role': 'user', 'content': f'任务内容：{task_content}\n\n最近的对话：{json.dumps(self.messages[-3:], ensure_ascii=False)}'}
                ]
                event_response = self.client.chat.completions.create(
                    model='Qwen/Qwen3-235B-A22B-Instruct-2507',
                    messages=event_check_messages,
                    temperature=0.7,
                    top_p=0.8
                )
                
                event_result = event_response.choices[0].message.content.strip()
                try:
                    event_data = json.loads(event_result)
                    console.print(f"\n[bold red]事件检测:[/bold red] {event_data}")
                    port = Global.modelscope['port']
                    response = requests.post(f'http://127.0.0.1:{port}/return', json={"function_name":"send_audio_text", "function_id":agent_id, "result":str({'GUI_Agent最新回复：':event_data})})
                except:
                    pass

            if assistant_message.get('tool_calls'):
                for tool_call in assistant_message['tool_calls']:
                    try:
                        function_name = tool_call['function']['name']
                        
                        if tool_call['function']['arguments']:
                            args = json.loads(tool_call['function']['arguments'])
                        else:
                            args = {}
                        
                        console.print(f"\n[bold cyan]Executing Tool:[/bold cyan] {function_name}")
                        console.print(Panel(json.dumps(args, indent=2, ensure_ascii=False), border_style="cyan"))
                        
                        if function_name == 'hotkey':
                            keys = args.pop('keys', [])
                            result = globals()[function_name](*keys, **args)
                        elif function_name == 'VLM':
                            result = VLM(args['text'], [capture_screen()['image']], False)
                        else:
                            result = globals()[function_name](**args)
                        
                        console.print(f"[bold green]Tool Result:[/bold green] {result}")

                        self.messages.append({
                            'role': 'tool',
                            'content': f"已执行: {function_name} - {str(result)}",
                            'tool_call_id': tool_call['id']
                        })
                        
                    except Exception as e:
                        error_message = f"执行失败: {str(e)}"
                        console.print(f"[bold red]Tool Error:[/bold red] {function_name} - {str(e)}")

                        self.messages.append({
                            'role': 'tool',
                            'content': error_message,
                            'tool_call_id': tool_call['id']
                        })
            
            if '[任务完成]' in content:
                console.print("\n[bold green]Task Completed[/bold green]")
                break
            
            if not assistant_message.get('tool_calls'):
                user_input = console.input('\n[bold yellow]Reply:[/bold yellow] ')
                self.messages.append({'role':'user', 'content':user_input})

        try:
            port = Global.modelscope['port']
            response = requests.post(f'http://127.0.0.1:{port}/return', json={"function_name":"GUI_Agent", "function_id":agent_id, "result":content})
            if response.status_code != 200:
                raise response.content
        except:
            raise "无法与server通信"

def capture_screen():
    """捕获当前屏幕并转为base64编码"""
    screenshot = pyautogui.screenshot()
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return {"image": img_str, "width": screenshot.width, "height": screenshot.height}

def click_position(x, y, wait=0.5):
    """点击屏幕上的指定位置"""
    try:
        current_x, current_y = pyautogui.position()
        distance = ((x*scale - current_x)**2 + (y*scale - current_y)**2)**0.5
        move_duration = max(0.3, min(0.8, distance / 1000))
        
        pyautogui.moveTo(x*scale, y*scale, duration=move_duration, tween=pyautogui.easeOutQuad)
        time.sleep(0.05)
        pyautogui.click()
        time.sleep(wait)
        return f"已平滑点击位置: ({x}, {y})，移动耗时 {move_duration:.2f} 秒，等待 {wait} 秒"
    except Exception as e:
        return f"点击位置失败: {str(e)}"

def double_click_position(x, y, wait=0.5):
    """双击屏幕上的指定位置"""
    try:
        current_x, current_y = pyautogui.position()
        distance = ((x*scale - current_x)**2 + (y*scale - current_y)**2)**0.5
        move_duration = max(0.3, min(0.8, distance / 1000))
        
        pyautogui.moveTo(x*scale, y*scale, duration=move_duration, tween=pyautogui.easeOutQuad)
        time.sleep(0.05)
        pyautogui.doubleClick()
        time.sleep(wait)
        return f"已平滑双击位置: ({x}, {y})，移动耗时 {move_duration:.2f} 秒，等待 {wait} 秒"
    except Exception as e:
        return f"双击位置失败: {str(e)}"

def right_click_position(x, y, wait=0.5):
    """右键点击屏幕上的指定位置"""
    try:
        current_x, current_y = pyautogui.position()
        distance = ((x*scale - current_x)**2 + (y*scale - current_y)**2)**0.5
        move_duration = max(0.3, min(0.8, distance / 1000))
        
        pyautogui.moveTo(x*scale, y*scale, duration=move_duration, tween=pyautogui.easeOutQuad)
        time.sleep(0.05)
        pyautogui.rightClick()
        time.sleep(wait)
        return f"已平滑右键点击位置: ({x}, {y})，移动耗时 {move_duration:.2f} 秒，等待 {wait} 秒"
    except Exception as e:
        return f"右键点击位置失败: {str(e)}"

def move_mouse(x, y, wait=0.5):
    """移动鼠标到指定位置"""
    try:
        current_x, current_y = pyautogui.position()
        distance = ((x*scale - current_x)**2 + (y*scale - current_y)**2)**0.5
        move_duration = max(0.2, min(1.0, distance / 800))
        
        pyautogui.moveTo(x*scale, y*scale, duration=move_duration, tween=pyautogui.easeInOutQuad)
        time.sleep(wait)
        return f"已平滑移动鼠标到: ({x}, {y})，移动耗时 {move_duration:.2f} 秒，等待 {wait} 秒"
    except Exception as e:
        return f"移动鼠标失败: {str(e)}"

def drag_mouse(start_x, start_y, end_x, end_y, duration=0.5, wait=0.5):
    """从一个位置拖动到另一个位置"""
    try:
        current_x, current_y = pyautogui.position()
        start_distance = ((start_x*scale - current_x)**2 + (start_y*scale - current_y)**2)**0.5
        move_duration = max(0.2, min(0.7, start_distance / 1000))
        
        pyautogui.moveTo(start_x*scale, start_y*scale, duration=move_duration, tween=pyautogui.easeOutQuad)
        time.sleep(0.05)
        
        pyautogui.dragTo(end_x*scale, end_y*scale, duration=duration, tween=pyautogui.easeInOutSine)
        time.sleep(wait)
        return f"已平滑拖动: ({start_x}, {start_y}) → ({end_x}, {end_y})，移动耗时 {move_duration:.2f} 秒，拖拽耗时 {duration} 秒，等待 {wait} 秒"
    except Exception as e:
        return f"拖动操作失败: {str(e)}"

def scroll(clicks, x=None, y=None, wait=0.5):
    """在指定位置滚动鼠标"""
    try:
        if x is not None and y is not None:
            current_x, current_y = pyautogui.position()
            distance = ((x*scale - current_x)**2 + (y*scale - current_y)**2)**0.5
            move_duration = max(0.2, min(0.6, distance / 1200))
            
            pyautogui.moveTo(x*scale, y*scale, duration=move_duration, tween=pyautogui.easeOutQuad)
            time.sleep(0.05)
        
        scroll_steps = abs(clicks) // 2
        if scroll_steps < 1:
            scroll_steps = 1
            
        step_size = 1 if clicks > 0 else -1
        for _ in range(scroll_steps):
            pyautogui.scroll(step_size * 2)
            time.sleep(0.05)
        
        time.sleep(wait)
        return f"已滚动鼠标 {clicks} 次（分 {scroll_steps} 步），等待 {wait} 秒"
    except Exception as e:
        return f"滚动操作失败: {str(e)}"

def type_text(text, press_enter=False, wait=0.5):
    try:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        if press_enter:
            pyautogui.press('enter')
            
        time.sleep(wait)
        action_desc = f"已输入文本: {text}"
        if press_enter:
            action_desc += " 并按回车"
        return action_desc + f"，等待 {wait} 秒"
    except Exception as e:
        return f"输入文本失败: {str(e)}"

def press_key(key, wait=0.5):
    """按下指定按键"""
    try:
        pyautogui.press(key)
        time.sleep(wait)
        return f"已按下按键: {key}，等待 {wait} 秒"
    except Exception as e:
        return f"按键操作失败: {str(e)}"

def hotkey(*keys, wait=0.5):
    """按下组合键"""
    try:
        pyautogui.hotkey(*keys)
        time.sleep(wait)
        return f"已按下组合键: {' + '.join(keys)}, 等待 {wait} 秒"
    except Exception as e:
        return f"组合键操作失败: {str(e)}"

import sys
if sys.argv:
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
    task_content = data["task_content"]
    agent_id = data["agent_id"]
    os.unlink(sys.argv[1])

    console.print(f"[bold blue]GUIAgent Starting[/bold blue]")
    console.print(f"Task: {task_content}")
    console.print("-" * 50)
    
    agent = Agent()
    agent.request(task_content)