import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import re
import asyncio
import requests
from openai import OpenAI
from config import Global
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

console = Console()
# if Global.modelscope['has_proxy']:
#     with open('assets\www_bing_cookie.json', 'r', encoding='utf-8') as f:
#         bing_cookie = json.load(f)
# else:
#     with open('assets\cn_bing_cookie.json', 'r', encoding='utf-8') as f:
#         bing_cookie = json.load(f)
# bing_cookie = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in bing_cookie])
if Global.modelscope['has_proxy']:
    bing_cookie = Global.modelscope['www_bing_cookie']
else:
    bing_cookie = Global.modelscope['cn_bing_cookie']

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "基于bing搜索，可以搜索网页或学术内容，返回搜索结果列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["网页", "学术"],
                        "description": "搜索类型，默认为网页搜索",
                        "default": "网页"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_webpage_text",
            "description": "获取指定URL列表的网页详细文本内容，专门用于提取网页中的文字信息。如果需要获取视频、图片、链接等其他元素，请使用get_website_elements",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "uri"
                        },
                        "description": "要获取文本内容的URL列表(可以多输入几个URL，这样获取的信息更全面)"
                    }
                },
                "required": ["urls"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_website_elements",
            "description": "获取指定URL的网站内容,包括标题、图片、视频、链接、导航和meta信息。专门用于提取网页中的媒体资源和跳转链接，方便在特定网站中跳转网页。如果只需要获取网页文本内容，请使用get_webpage_text",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",
                        "description": "要获取内容的网址"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_media",
            "description": "下载给定 URL 列表中的媒体文件(视频和图片)到指定目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "uri"
                        },
                        "description": "要下载的媒体文件 URL 列表"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "下载文件的输出目录，默认为 './downloads'",
                        "default": "./downloads"
                    }
                },
                "required": ["urls"]
            }
        }
    }
]

SYSTEM_PROMPT = """
今天是%s
你是WebAgent，一个专业的信息搜索和分析助手。你的核心使命是帮助用户完成各种搜索任务，通过多轮对话和工具调用来收集全面、准确、最新的信息。

1. **get_website_elements**（媒体资源和链接发现工具）
- 专门用于获取网页上的图片、视频、跳转链接、导航元素等
- 适用于需要获取媒体资源或在特定网站内部进行深度导航
- 帮助发现网站内的相关页面、子页面和媒体资源
- 注意：这个工具主要获取页面元素和资源，无法获取详细文本内容

2. **组合使用模式**
- 使用get_website_elements发现新的有价值链接和媒体资源
- 对新发现的重要链接继续使用get_webpage_text获取文本内容

3. **信息整合**：
- 持续收集和验证信息
- 交叉对比不同来源的内容
- 确保信息的准确性和时效性

4. **任务完成**：
- 当收集到足够全面的信息后
- 输出 [任务完成] 标记

## 搜索原则

- **权威性优先**：优先选择官方网站、知名媒体、学术机构等权威来源
- **时效性关注**：重点关注最新发布的信息和数据
- **全面性保证**：确保从多个角度和维度收集信息
- **准确性验证**：通过多个来源验证关键信息的准确性
- **精选策略**：从大量搜索结果中挑选最有价值的网站进行深度分析

## 工具功能说明

1. **search_web**：网络搜索工具
- 功能：通过关键词发现相关网页
- 策略：获得搜索结果后，要从中挑选最有价值的网站进行后续分析

2. **get_webpage_text**：文本内容获取工具
- 功能：专门获取网页的详细文本内容
- 用途：深入分析网页文字内容，提取有价值的文本信息
- 使用策略：对从search_web中挑选出的优质网站使用
- 局限：只能获取文本信息，无法获取HTML、图片、视频、链接等其他元素

3. **get_website_elements**：媒体资源和链接发现工具
- 功能：获取网页上的图片、视频、跳转链接、导航元素、meta信息等页面结构
- 用途：获取媒体资源、在特定网站内部进行导航、发现更多相关页面
- 使用场景：需要获取图片、视频、链接等非文本内容时使用
- 局限：主要获取页面元素和资源，无法获取详细文本内容

4. **download_media**：媒体下载工具，用于下载相关媒体文件

记住：search_web用于"发现网站"，get_webpage_text用于"获取文本"，get_website_elements用于"获取媒体和链接"
""" % (f"{datetime.today().strftime('%Y年%m月%d日')}，{datetime.today().strftime('%A')}")

class Agent:
    def __init__(self):
        self.client = OpenAI(
            api_key=Global.modelscope['api_key'],
            base_url=Global.modelscope['base_url']
        )
        self.messages = [{'role':'system', 'content':SYSTEM_PROMPT}]

    def request(self, task_content):
        self.messages.append({'role':'user', 'content':task_content})

        while True:
            response = self.client.chat.completions.create(
                model = 'Qwen/Qwen3-235B-A22B-Thinking-2507',
                messages=self.messages,
                stream=True,
                tools=tools,
                temperature=0.6,
                top_p=0.95
            )

            content = ''
            reasoning = True
            assistant_message = {'role': 'assistant', 'content': ''}
            
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
            
            for message in self.messages:
                if message['role'] == 'tool':
                    if "get_website_elements" in message['content'][:100]:
                        if len(message['content']) > 1000:
                            message['content'] = message['content'][:1000]+'...'

            self.messages.append(assistant_message)

            if assistant_message.get('tool_calls'):
                for tool_call in assistant_message['tool_calls']:
                    try:
                        function_name = tool_call['function']['name']
                        
                        if tool_call['function']['arguments']:
                            args = json.loads(tool_call['function']['arguments'])
                        else:
                            args = {}
                        
                        console.print(f"\n[bold magenta]Executing Tool: {function_name}[/bold magenta]")
                        
                        with Status(f"[bold green]Running {function_name}...", console=console):
                            if function_name == "search_web":
                                result = get_search(**args)
                            elif function_name == "get_webpage_text":
                                result = get_webpage_content(args['urls'])
                            elif function_name == "get_website_elements":
                                async def extract_content():
                                    async with WebContentExtractor() as extractor:
                                        return await extractor.extract_page_content(args['url'])
                                
                                result = asyncio.run(extract_content())
                            elif function_name == "download_media":
                                result = download_media(**args)
                            else:
                                raise Exception("错误的函数名")

                        console.print(f"\n[bold cyan]{function_name.upper()} Output:[/bold cyan]")
                        console.print(Panel(str(result)[:2000] + "..." if len(str(result)) > 2000 else str(result), border_style="cyan"))

                        self.messages.append({
                            'role': 'tool',
                            'content': f"执行成功: {function_name} - {str(result)[:30000]}",
                            'tool_call_id': tool_call['id']
                        })
                        
                    except Exception as e:
                        error_message = f"执行失败: {str(e)}"
                        console.print(f"\n[bold red]{function_name.upper()} Error:[/bold red]")
                        console.print(Panel(error_message, border_style="red"))

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
            response = requests.post(f'http://127.0.0.1:{port}/return', json={"function_name":"Web_Agent", "function_id":agent_id, "result":content})
            if response.status_code != 200:
                raise response.content
        except:
            raise "无法与server通信"

class WebContentExtractor:
    def __init__(self):
        self.playwright = None
        self.browser = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=Global.modelscope['headless'], args=['--start-minimized'])
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def extract_page_content(self, url, wait_time=3000):
        """提取网页核心内容"""
        self.context = await self.browser.new_context()
        page = await self.context.new_page()
        
        try:
            try:
                await page.goto(url, wait_until='networkidle')
                await page.wait_for_timeout(wait_time)
            except:
                pass
            
            html_content = await page.content()
            extracted_data = self._preprocess_html(html_content, url)
            
            return extracted_data
            
        finally:
            await page.close()
    
    def _preprocess_html(self, html_content, base_url):
        """预处理HTML，提取核心信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        self._remove_unwanted_elements(soup)
        
        extracted_data = {
            'url': base_url,
            'title': self._extract_title(soup),
            'content': self._extract_main_content(soup)[:10000],
            'meta_info': self._extract_meta_info(soup),
            'navigation': self._extract_navigation(soup),
            'links': self._extract_links(soup, base_url),
            'images': self._extract_images(soup, base_url)
        }
        
        return extracted_data
    
    def _remove_unwanted_elements(self, soup):
        """移除不必要的元素以减少token消耗"""
        unwanted_tags = [
            'script', 'style', 'noscript', 'iframe', 'embed', 'object',
            'form', 'input', 'button', 'select', 'textarea',
            'svg', 'canvas', 'video', 'audio'
        ]
        
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
        
        ad_classes = ['ad', 'ads', 'advertisement', 'banner', 'popup', 'modal', 'overlay']
        for class_name in ad_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        important_attrs = ['href', 'src', 'alt', 'title', 'id', 'class']
        for tag in soup.find_all():
            attrs_to_remove = [attr for attr in tag.attrs if attr not in important_attrs]
            for attr in attrs_to_remove:
                del tag[attr]
    
    def _extract_title(self, soup):
        """提取页面标题"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
        
        return "无标题"
    
    def _extract_meta_info(self, soup):
        """提取meta信息"""
        meta_info = {}
        
        description = soup.find('meta', attrs={'name': 'description'})
        if description and description.get('content'):
            meta_info['description'] = description['content']
        
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        if keywords and keywords.get('content'):
            meta_info['keywords'] = keywords['content']
        
        author = soup.find('meta', attrs={'name': 'author'})
        if author and author.get('content'):
            meta_info['author'] = author['content']
        
        return meta_info
    
    def _extract_main_content(self, soup):
        """提取主要内容"""
        main_selectors = [
            'main', 'article', '[role="main"]', 
            '.content', '.main-content', '.post-content',
            '#content', '#main-content', '#post-content'
        ]
        
        for selector in main_selectors:
            main_element = soup.select_one(selector)
            if main_element:
                return self._clean_text(main_element.get_text())
        
        body = soup.find('body')
        if body:
            for unwanted in body.find_all(['nav', 'aside', 'footer', 'header']):
                unwanted.decompose()
            return self._clean_text(body.get_text())
        
        return self._clean_text(soup.get_text())
    
    def _extract_navigation(self, soup):
        """提取导航信息"""
        nav_links = []
        nav_elements = soup.find_all(['nav', '[role="navigation"]'])
        
        for nav in nav_elements:
            links = nav.find_all('a', href=True)
            for link in links:
                nav_links.append({
                    'text': self._clean_text(link.get_text()),
                    'href': link['href']
                })
        
        return nav_links
    
    def _extract_links(self, soup, base_url):
        """提取所有链接"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = self._clean_text(link.get_text())
            if text and href:
                absolute_url = urljoin(base_url, href)
                links.append({
                    'text': text,
                    'href': href,
                    'absolute_url': absolute_url
                })
        
        return links
    
    def _extract_images(self, soup, base_url):
        """提取图片信息"""
        images = []
        for img in soup.find_all('img', src=True):
            src = img['src']
            alt = img.get('alt', '')
            absolute_url = urljoin(base_url, src)
            
            images.append({
                'src': src,
                'alt': alt,
                'absolute_url': absolute_url
            })
        
        return images
    
    def _extract_headings(self, soup):
        """提取标题结构"""
        headings = []
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                headings.append({
                    'level': i,
                    'text': self._clean_text(heading.get_text())
                })
        
        return headings
    
    def _clean_text(self, text):
        """清理文本"""
        if not text:
            return ""
        
        text = re.sub(r'\s+', ' ', text.strip())
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\-]', '', text)
        
        return text

def is_html_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(1024)
            content_lower = content.lower().strip()
            return (content_lower.startswith('<!doctype html') or 
                   '<html' in content_lower or 
                   '<head>' in content_lower or
                   '<body>' in content_lower)
    except:
        return False

def download_with_requests(url, output_path):
    """使用requests下载文件"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return True
    except Exception:
        return False

def download_with_browser(page, url, output_path, filename):
    """使用浏览器下载文件"""
    try:
        page.goto(url)
        page.evaluate(f"""
            fetch('{url}')
                .then(response => response.blob())
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = '{filename}';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                }});
        """)
        
        with page.expect_download(timeout=10000) as download_info:
            pass
        
        download = download_info.value
        download.save_as(output_path)
        
        return True
    except Exception:
        return False

def download_media(urls, output_dir='./downloads'):
    output_dir = os.path.join(WORKDIR, output_dir)
    os.makedirs(output_dir, exist_ok=True)
    results = []
    
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False, args=['--start-minimized'])
    context = browser.new_context()
    page = context.new_page()
    
    try:
        for url in urls:
            try:
                filename = os.path.basename(url)
                output_path = os.path.join(output_dir, filename)
                
                if download_with_requests(url, output_path):
                    results.append(f'成功下载，已保存到 {output_path}')
                else:
                    if download_with_browser(page, url, output_path, filename):
                        if is_html_content(output_path):
                            results.append(f'警告: {url} 下载的是HTML文件，可能不是预期的媒体文件')
                        else:
                            results.append(f'成功下载，已保存到 {output_path}')
                    else:
                        results.append(f'下载 {url} 时出现错误: requests和浏览器都失败')
                
            except Exception as e:
                results.append(f'下载 {url} 时出现错误: {e}')
    
    finally:
        browser.close()
        p.stop()

    return results

def get_search(query, search_type='网页'):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(bing_search, query, i, search_type) for i in range(Global.modelscope['search_pages'])]
        results = []
        for future in as_completed(futures):
            results.append(future.result())

    search_results = []
    for result in results:
        search_results += result
    
    return search_results

def get_webpage_content(urls):
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for x,url in enumerate(urls):
            futures.append(executor.submit(get_url_content, url))
        
        for future in as_completed(futures):
            results.append(future.result())

    response_data = []
    for url, content in results:
        response_data.append({
            'url': url,
            'content': content if content and len(content) > 200 else None
        })

    for x in range(len(response_data)-1, -1, -1):
        if not response_data[x]['content']:
            response_data.pop(x)
            
    if response_data:
        text = ''
        lenth = int(Global.modelscope['search_max_context']/len(response_data))
        for i,x in enumerate(response_data):
            text += f"[webpage {i} URL]: {x['url']}\n"
            content = x['content']
            if len(content) > lenth:
                content = content[:lenth]+'...'
            text += f"[webpage {i} begin]{content}[webpage {i} end]\n"

        return text
    else:
        return None

def bing_search(query, page, search_type):
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate',
        'Cookie': bing_cookie
    }

    if search_type == '网页':
        url_insert = ''
        select = 'li.b_algo'
    elif search_type == '学术':
        url_insert = '/academic'
        select = 'li.aca_algo'
    
    if Global.modelscope['has_proxy']:
        url = f'https://www.bing.com{url_insert}/search?q={query}&first={page*10+1}&ensearch=1'
    else:
        url = f'https://cn.bing.com{url_insert}/search?q={query}&first={page*10}'

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    for item in soup.select(select):
        title_elem = item.select_one('h2')
        link_elem = item.select_one('a')
        desc_elem = item.select_one('.b_caption p')
        
        if title_elem and link_elem:
            result = {
                'title': title_elem.text.strip(),
                'url': link_elem.get('href'),
                'introduction': desc_elem.text.strip() if desc_elem else ""
            }
            results.append(result)
            
    return results

def get_url_content(url, proxy_dict=None):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(
            url,
            headers=headers,
            proxies=proxy_dict,
            timeout=2
        )

        if response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(["script", "style"]):
            element.decompose()

        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return url, ' '.join(chunk for chunk in chunks if chunk)
        
    except Exception as e:
        return url, '网络错误'

def get_proxies(protocol, count):
    response = requests.get(f'https://proxy.scdn.io/api/get_proxy.php?protocol={protocol}&count={count}')
    results = response.json()["data"]["proxies"]
    return results

import sys
if sys.argv:
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
    task_content = data["task_content"]
    WORKDIR = 'temp'
    agent_id = data["agent_id"]
    os.unlink(sys.argv[1])

    console.print(f"[bold blue]WebAgent Starting[/bold blue]")
    console.print(f"Task: {task_content}")
    console.print(f"Working Directory: {WORKDIR}")
    console.print("-" * 50)
    
    agent = Agent()
    agent.request(task_content)