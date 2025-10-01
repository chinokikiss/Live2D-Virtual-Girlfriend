import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import re
import json
import requests
import platform
import subprocess
from openai import OpenAI
from config import Global
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.status import Status

sys.stdout.reconfigure(encoding='utf-8')
console = Console()

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
你是一个智能命令行Agent，叫CLIAgent，专门通过执行代码和多轮对话来帮助用户完成各种编程和系统任务。

## 系统环境信息
- **操作系统**：%s
- **Python版本**：%s
- **工作目录**：{WORKDIR}

## 可用工具
- **VLM工具**：无需导入的内置函数，用于处理图像识别相关任务
  - 函数签名：`print(VLM(text, imgs))` 
  - **重要提醒**：必须使用print()打印VLM结果，不能直接调用VLM函数
  - 调用要求：不要一张一张图片识别，尽量批量识别图片，最多可以识别10张图片，减少调用次数
  - 参数说明：text为文本提示，imgs为图像文件路径列表
  - 支持格式：.png, .jpg, .jpeg, .bmp, .webp
  - 返回结果：图像分析的文本描述

## 核心工作原则
- **主动信息收集**：基于已知系统环境，直接执行相关代码来获取任务所需信息
- **代码优先策略**：优先通过执行代码来分析问题和收集数据
- **分步式执行**：每次只执行一个步骤，等待执行结果后再进行下一步
- **信息可视化**：使用print()函数清晰打印收集到的信息

## 代码执行机制
- **代码格式要求**：必须使用标准Markdown代码块格式，即```python开头，```结尾
- **代码输出方式**：直接输出Python代码块，由系统自动识别并执行
- **独立执行原则**：**每个代码块都是完全独立运行的，不存在变量继承关系**
- **变量重新定义**：每次代码执行都需要重新定义所需的变量和导入模块
- **状态无继承**：前一个代码块的变量、函数定义等状态不会传递到下一个代码块
- **结果反馈机制**：Python解释器执行代码后自动返回结果，触发AI进行下一轮回答
- **自动执行流程**：AI输出代码 → 系统自动执行 → 返回真实结果 → AI基于结果继续
- **跨平台命令支持**：基于已知操作系统类型选择合适的命令执行方式
- **环境信息利用**：基于预设的系统环境信息优化代码执行策略

## VLM工具使用规范
- **强制打印输出**：调用VLM时必须使用print(VLM(text, imgs))格式
- **禁止直接调用**：不允许直接使用VLM(text, imgs)而不打印结果
- **结果可见性**：所有VLM分析结果必须通过print输出到控制台

## 执行策略
- **分对话执行**：每次回复只输出一段代码，等待系统执行并返回结果
- **真实结果依赖**：绝不预测或假设执行结果，完全依赖系统返回的真实结果
- **信息打印**：代码中使用print()函数详细打印，便于查看和分析
- **独立性保证**：每段代码都包含完整的变量定义和模块导入
- 主动输出信息收集代码，不等待用户确认
- 对于可能修改系统的操作，先解释再征求同意后输出代码
- 每次收到执行结果后分析并决定下一步动作
- 遇到错误时自动输出替代方案代码
- 基于已知系统类型智能选择执行方式

## 工作流程
1. **需求分析阶段**
   - 基于预设的系统环境信息分析用户需求
   - 输出独立的代码块分步收集任务相关的具体信息
   - 等待执行结果后分步验证可行性和约束条件
   - 识别潜在风险和技术要求

2. **方案实施阶段**
   - 分步输出独立的代码块来解决问题
   - 每输出一段代码等待系统执行结果再继续
   - 根据执行反馈动态调整方案并输出新的独立代码块

3. **任务完成阶段**
   - **当任务已完成时，要输出 [任务完成] 标记**

## 重要约束
- **代码独立性**：每个代码块必须完全独立，重新定义所需变量和导入模块
- **禁止变量继承**：不能假设前一个代码块的变量在当前代码块中可用
- **VLM强制打印**：调用VLM工具时必须使用print()输出结果
- **禁止一步到位**：不要试图在一段代码中完成复杂任务，必须分层进行
- **信息收集优先**：永远先收集和打印信息，再基于信息进行分析和决策
- **严禁输出特殊字符**：禁止输出可能导致编码错误的 Unicode 字符
- **依赖系统执行**：所有代码执行由Python解释器完成，结果自动返回给AI
- **分步代码输出**：每次回复只包含一段待执行的独立代码
- **结果等待机制**：必须等待系统返回真实执行结果才能继续下一步
- **信息透明**：代码中使用print()清晰展示收集到的所有信息
"""

system_info = f"{platform.system()} {platform.release()} {platform.machine()}"
python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
SYSTEM_PROMPT = SYSTEM_PROMPT % (system_info, python_version)

class Agent:
    def __init__(self):
        self.client = OpenAI(
            api_key=Global.modelscope['api_key'],
            base_url=Global.modelscope['base_url']
        )
        self.prompt = SYSTEM_PROMPT
        self.messages = [{'role':'system', 'content':self.prompt}]

    def request(self, task_content):
        self.messages.append({'role':'user', 'content':task_content})

        while True:
            self.messages[0] = {'role':'system', 'content':SYSTEM_PROMPT.replace('{WORKDIR}', WORKDIR)}

            response = self.client.chat.completions.create(
                model = 'Qwen/Qwen3-235B-A22B-Instruct-2507',
                messages=self.messages,
                stream=True,
                temperature=0.7,
                top_p=0.8
            )

            content = ''
            reasoning = True
            
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        if reasoning:
                            reasoning = False
                            console.print("\n[bold blue]Agent Response:[/bold blue]")
                        console.print(delta.content, end='')
                        content += delta.content
                    elif delta.reasoning_content:
                        console.print(delta.reasoning_content, end='', style="dim")
            
            console.print()
            self.messages.append({'role':'assistant', 'content':content})

            code_result = self.run_code(content)

            if '[任务完成]' in content:
                console.print("\n[bold green]Task Completed[/bold green]")
                break

            if code_result:
                for key, value in code_result.items():
                    if 'print' in value and value['print']:
                        console.print(f"\n[bold cyan]{key.upper()} Output:[/bold cyan]")
                        console.print(Panel(value['print'].strip(), border_style="cyan"))
                    if 'error' in value and value['error']:
                        console.print(f"\n[bold red]{key.upper()} Error:[/bold red]")
                        console.print(Panel(value['error'].strip(), border_style="red"))
                self.messages.append({'role':'user', 'content':str(code_result)})
            else:
                user_input = console.input("\n[bold yellow]Reply:[/bold yellow] ")
                self.messages.append({'role':'user', 'content':user_input})
        
        try:
            port = Global.modelscope['port']
            response = requests.post(f'http://127.0.0.1:{port}/return', json={"function_name":"CLI_Agent", "function_id":agent_id, "result":content})
            if response.status_code != 200:
                raise response.content
        except:
            raise "无法与server通信"
    
    def run_code(self, text):
        pattern = r'```(\w+)?\s*(.*?)```'
        matches = re.finditer(pattern, text, re.DOTALL)

        code_dict = {}
        for match in matches:
            language = match.group(1) or 'unknown'
            code = match.group(2).strip()

            gbk_text = ''
            for char in code:
                try:
                    char.encode('gbk')
                    gbk_text += char
                except UnicodeEncodeError:
                    continue
            code = gbk_text

            if language in code_dict:
                code_dict[language] += code
            else:
                code_dict[language] = code
        
        result_dict = {}
        if 'python' in code_dict:
            console.print(f"\n[bold magenta]Executing Python Code:[/bold magenta]")
            console.print(Syntax(code_dict['python'], "python", theme="monokai", word_wrap=True))
            
            with open('agents\extra_tool.py', 'r', encoding='utf-8') as f:
                extra_tool_py = f.read()
            api_key, base_url = Global.modelscope['api_key'], Global.modelscope['base_url']
            extra_tool_py = extra_tool_py.replace("from config import Global\nclient = OpenAI(api_key=Global.modelscope['api_key'], base_url=Global.modelscope['base_url'])", f'client = OpenAI(api_key="{api_key}", base_url="{base_url}")')

            code_dict['python'] = extra_tool_py+'\n'+code_dict['python']
            
            with Status("[bold green]Executing...", console=console):
                process = subprocess.Popen(
                    [sys.executable, "-c", code_dict['python']],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=WORKDIR
                )
                
                stdout, errors = process.communicate()
                result_dict['python'] = {'print':stdout, 'error':errors}
        
        return result_dict

import sys
if sys.argv:
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
    task_content = data["task_content"]
    WORKDIR = data["WORKDIR"]
    agent_id = data["agent_id"]
    os.unlink(sys.argv[1])

    console.print(f"[bold blue]CLIAgent Starting[/bold blue]")
    console.print(f"Task: {task_content}")
    console.print(f"Working Directory: {WORKDIR}")
    console.print(f"System: {system_info} | Python: {python_version}")
    console.print("-" * 50)
    
    agent = Agent()
    agent.request(task_content)