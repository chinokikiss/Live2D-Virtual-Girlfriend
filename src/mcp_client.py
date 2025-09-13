import asyncio
import threading
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        
        self.sessions = {}
        self.session_info = {}
        
        self._loop = None
        self._thread = None
        
    def _run_async_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()
    
    def _start_async_thread(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self._thread.start()
            
            while self._loop is None:
                threading.Event().wait(0.01)
    
    def _submit_coroutine(self, coro):
        self._start_async_thread()
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()
    
    async def connect_to_sse_server(self, server_name, server_url):
        print(f"尝试连接到 SSE 服务器 '{server_name}': {server_url}")
        
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url=server_url)
        )
        read, write = sse_transport
        print(f"SSE 传输已建立: {server_name}")

        session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        print(f"SSE 客户端会话已初始化: {server_name}")

        self.sessions[server_name] = session
        self.session_info[server_name] = {
            'type': 'sse',
            'url': server_url
        }

        response = await session.list_tools()
        tools = response.tools
        print(f"\n'{server_name}' SSE 服务器支持以下工具:", [tool.name for tool in tools])

    async def connect_to_stdio_server(self, server_name, server_script_path):
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        print(f"尝试连接到 Stdio 服务器 '{server_name}': {server_script_path}")
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        print(f"Stdio 传输已建立: {server_name}")
        
        session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        print(f"Stdio 客户端会话已初始化: {server_name}")

        self.sessions[server_name] = session
        self.session_info[server_name] = {
            'type': 'stdio',
            'path': server_script_path
        }

        response = await session.list_tools()
        tools = response.tools
        print(f"\n'{server_name}' Stdio 服务器支持以下工具:", [tool.name for tool in tools])

    async def connect_multiple_servers(self, server_configs):
        for config in server_configs:
            name = config['name']
            server_type = config['type']
            target = config['target']
            
            try:
                if server_type == 'stdio':
                    await self.connect_to_stdio_server(name, target)
                elif server_type == 'sse':
                    await self.connect_to_sse_server(name, target)
                else:
                    print(f"未知服务器类型: {server_type} for {name}")
            except Exception as e:
                print(f"连接服务器 '{name}' 失败: {e}")

    async def _get_all_tools_async(self):
        if not self.sessions:
            raise RuntimeError("MCP 客户端未连接到任何服务器。请先连接服务器。")

        all_tools = []
        tool_to_server = {}
        for server_name, session in self.sessions.items():
            try:
                response = await session.list_tools()
                tools = response.tools
                
                for tool in tools:
                    prefixed_tool_name = f"{server_name}_{tool.name}"
                    tool_dict = {
                        "type": "function",
                        "function": {
                            "name": prefixed_tool_name,
                            "description": f"[服务器: {server_name}] {tool.description}",
                            "input_schema": tool.inputSchema
                        }
                    }
                    all_tools.append(tool_dict)
                    tool_to_server[prefixed_tool_name] = {
                        'server_name': server_name,
                        'original_tool_name': tool.name,
                        'session': session
                    }
            except Exception as e:
                print(f"获取服务器 '{server_name}' 工具列表失败: {e}")
        
        return all_tools, tool_to_server

    async def _call_tool_async(self, tool_name, tool_args, tool_to_server):
        if tool_name in tool_to_server:
            server_info = tool_to_server[tool_name]
            server_name = server_info['server_name']
            original_tool_name = server_info['original_tool_name']
            session = server_info['session']

            print(f"\n[调用工具 '{original_tool_name}' 在服务器 '{server_name}' 上，参数: {tool_args}]")
            
            tool_result = await session.call_tool(original_tool_name, tool_args)
            tool_output_str = str(tool_result)
            print(f"服务器 '{server_name}' 工具 '{original_tool_name}' 返回结果: {tool_output_str}\n")
            
            return tool_output_str
        else:
            raise ValueError(f"找不到工具 '{tool_name}' 对应的服务器")

    def get_all_tools(self):
        return self._submit_coroutine(self._get_all_tools_async())
    
    def call_tool(self, tool_name, tool_args, tool_to_server):
        return self._submit_coroutine(self._call_tool_async(tool_name, tool_args, tool_to_server))
    
    def connect_servers_sync(self, server_configs):
        return self._submit_coroutine(self.connect_multiple_servers(server_configs))