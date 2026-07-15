"""
?? TARS MCP Browser Client
????
- 启动 / 停止 TARS MCP Browser Server
- tools_list() ? 获取可用工具
- call(name, args) ? 调用工具
- navigate(url) ? 导航
- get_text() ? 获取页面纯文本
- get_markdown() ? 获取页面 Markdown
- click(index) ? 点击元素
- fill(value, index_or_selector) ? 填表单
- screenshot(name) ? 截图
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from httpx_sse import connect_sse

logger = logging.getLogger(__name__)

MCP_SERVER_PORT = 8931
MCP_SERVER_HOST = "127.0.0.1"
MCP_SSE_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"
MCP_POST_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/mcp"

# ? TARS MCP Server ????
TARS_MODULE = (
    Path(os.environ.get("NVM_SYMLINK", ""))
    / "node_modules"
    / "@agent-infra"
    / "mcp-server-browser"
    / "dist"
    / "index.cjs"
)
# ??????? nodenv ? nvm-windows ?????
_CANDIDATE_PATHS = [
    Path(os.environ.get("WORKBUDDY_NODE_DIR", "")) / "node_modules/@agent-infra/mcp-server-browser/dist/index.cjs",
    Path.home() / ".workbuddy/binaries/node/versions/22.22.2/node_modules/@agent-infra/mcp-server-browser/dist/index.cjs",
    # npx ?????
    None,
]

_MSG_ID = 0


def _next_id() -> int:
    global _MSG_ID
    _MSG_ID += 1
    return _MSG_ID


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict


class TarsBrowserClient:
    """TARS MCP Browser Client ???? HTTP SSE ????"""

    def __init__(self, host: str = MCP_SERVER_HOST, port: int = MCP_SERVER_PORT):
        self.base_url = f"http://{host}:{port}"
        self.sse_url = f"{self.base_url}/sse"
        self.post_url = f"{self.base_url}/mcp"
        self._process: Optional[subprocess.Popen] = None
        self._session_token: Optional[str] = None
        self._tools: dict[str, ToolInfo] = {}

    def is_running(self) -> bool:
        """检查 MCP Server 是否在运行（用 POST 快速探测）"""
        try:
            r = httpx.post(
                self.post_url,
                json={"jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}},
                headers={"Accept": "application/json, text/event-stream"},
                timeout=3,
            )
            return r.status_code == 200
        except Exception:
            return False

    def start_server(
        self,
        browser: str = "chrome",
        vision: bool = False,
        headless: bool = False,
        output_dir: Optional[str] = None,
    ) -> bool:
        """?? MCP Browser Server"""
        if self.is_running():
            logger.info("TARS MCP Server already running on %s", self.post_url)
            return True

        cmd = ["mcp-server-browser"]
        cmd.extend(["--port", str(MCP_SERVER_PORT)])
        cmd.extend(["--host", MCP_SERVER_HOST])
        cmd.extend(["--browser", browser])
        if vision:
            cmd.append("--vision")
        if headless:
            cmd.append("--headless")
        if output_dir:
            cmd.extend(["--output-dir", output_dir])

        log_path = output_dir and f"{output_dir}/tars-server.log" or None
        if log_path:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if not log_path else open(log_path, "w"),
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            # ????????????
            for _ in range(15):
                if self.is_running():
                    logger.info("TARS MCP Server started on %s", self.post_url)
                    return True
                time.sleep(0.5)
            logger.error("TARS MCP Server failed to start")
            return False
        except FileNotFoundError:
            logger.warning("mcp-server-browser not found globally, trying npx...")
            return self._start_via_npx(vision, headless, output_dir)

    def _start_via_npx(
        self, vision: bool, headless: bool, output_dir: Optional[str]
    ) -> bool:
        """? npx ???? mcp-server-browser"""
        cmd = [
            "npx",
            "@agent-infra/mcp-server-browser",
            "--port", str(MCP_SERVER_PORT),
            "--host", MCP_SERVER_HOST,
        ]
        if vision:
            cmd.append("--vision")
        if headless:
            cmd.append("--headless")
        if output_dir:
            cmd.extend(["--output-dir", output_dir])

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for _ in range(20):
                if self.is_running():
                    logger.info("TARS MCP Server started via npx on %s", self.post_url)
                    return True
                time.sleep(1)
            return False
        except Exception as e:
            logger.error("Failed to start via npx: %s", e)
            return False

    def stop_server(self):
        """?? MCP Server"""
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
            logger.info("TARS MCP Server stopped")

    async def tools_list(self) -> list[ToolInfo]:
        """????????"""
        if self._tools:
            return list(self._tools.values())

        result = await self._mcp_call("tools/list", {})
        tools_data = result.get("tools", [])
        for t in tools_data:
            self._tools[t["name"]] = ToolInfo(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
        return list(self._tools.values())

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """?????"""
        return await self._mcp_call("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })

    async def navigate(self, url: str) -> str:
        """? URL"""
        result = await self.call("browser_navigate", {"url": url})
        return result.get("content", [{}])[0].get("text", "")

    async def get_text(self) -> str:
        """????????"""
        result = await self.call("browser_get_text", {})
        return result.get("content", [{}])[0].get("text", "")

    async def get_markdown(self) -> str:
        """?? Markdown ??"""
        result = await self.call("browser_get_markdown", {})
        return result.get("content", [{}])[0].get("text", "")

    async def click(self, index: int):
        """????"""
        return await self.call("browser_click", {"index": index})

    async def fill(
        self, value: str, index: int | None = None, selector: str | None = None
    ):
        """???"""
        args = {"value": value}
        if index is not None:
            args["index"] = index
        if selector:
            args["selector"] = selector
        return await self.call("browser_form_input_fill", args)

    async def screenshot(self, name: str = "screenshot") -> bytes | None:
        """????? PNG ??"""
        result = await self.call("browser_screenshot", {"name": name})
        # ?? resource ?
        for content in result.get("content", []):
            if content.get("type") == "resource":
                return content.get("resource", {}).get("blob")
        # ?? MCP ???? resource URI
        resources = result.get("resource", [])
        for r in resources:
            if isinstance(r, dict) and "blob" in r:
                return r["blob"]
        return None

    async def vision_capture(self) -> dict | None:
        """Vision ????"""
        result = await self.call("browser_vision_screen_capture", {})
        for content in result.get("content", []):
            if content.get("type") == "image":
                return content
        return None

    async def evaluate(self, script: str) -> Any:
        """? JS"""
        result = await self.call("browser_evaluate", {"script": script})
        return result.get("content", [{}])[0].get("text", "")

    async def _mcp_call(self, method: str, params: dict) -> dict:
        """MCP ????"""
        payload = {
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": method,
            "params": params,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.post_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error']}")

            return data.get("result", {})

    async def close(self):
        """????"""
        self.stop_server()


# ????
async def demo():
    """???? TARS ???????
    Example:
        python -c "from mcp_client import demo; import asyncio; asyncio.run(demo())"
    """
    client = TarsBrowserClient()

    if not client.is_running():
        print("?? TARS MCP Server...")
        if not client.start_server():
            print("???? TARS MCP Server")
            return

    print(f"TARS MCP Server running on {client.post_url}")

    # ???????
    tools = await client.tools_list()
    print(f"\n??? {len(tools)} ??")
    for t in tools[:5]:
        print(f"  - {t.name}: {t.description[:60]}")

    # ??
    print("\n1. ????...")
    result = await client.navigate("https://www.baidu.com")
    print(f"   {result[:100]}...")

    # ????
    print("\n2. ??????...")
    text = await client.get_text()
    print(f"   ({len(text)} chars) {text[:200]}...")

    print("\n? Demo ????")


if __name__ == "__main__":
    asyncio.run(demo())


