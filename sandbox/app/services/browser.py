import asyncio
import base64
import logging
import os
import shlex
import time
from typing import Any, Dict, List, Literal, Optional

from browser_use import Controller
from browser_use.browser.context import BrowserSession
from browser_use.dom.service import DomService
from fastapi import HTTPException
from patchright.async_api import Browser, BrowserContext, Page, async_playwright

from app.schemas.browser import (
    ActivateTabRequest,
    ClickRequest,
    CloseRequest,
    CloseTabByIdRequest,
    CloseTabRequest,
    EvaluateRequest,
    GoBackRequest,
    InitRequest,
    InputRequest,
    KeyRequest,
    NavigateRequest,
    OpenTabRequest,
    ScreenshotRequest,
    ScrollRequest,
    ScrollToTextRequest,
    SelectDropdownOptionRequest,
    SelectRequest,
    SendKeysRequest,
    SwitchTabByIdRequest,
    UploadFileRequest,
    WaitRequest,
)
from app.schemas.response import Response

logger = logging.getLogger(__name__)


def _api_guard(func):
    async def _inner(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except HTTPException as e:
            try:
                detail = e.detail if hasattr(e, "detail") else str(e)
            except Exception:
                detail = str(e)
            logger.error(f"{func.__name__} HTTPException: {detail}")
            return Response.error(message=detail)
        except Exception as e:
            logger.exception(f"{func.__name__} failed: {e}")
            return Response.error(message=str(e))
    return _inner


class SessionTabs:
    def __init__(self, context: BrowserContext):
        self.context = context
        self.tabs: Dict[str, Page] = {}
        self.active_tab_id: Optional[str] = None
        self.lock = asyncio.Lock()
        self.last_active_at = time.time()
        # selector cache per tab id
        self.elements_map: Dict[str, List[Dict[str, str]]] = {}
        # 由 browser-use DomService 生成的 CSS 选择器映射（index -> css selector），按 tab 维度缓存
        self.css_selector_map: Dict[str, Dict[int, str]] = {}
        # 可选的 browser-use BrowserSession，按会话维度
        self.browser_session: Optional[BrowserSession] = None


class BrowserService:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        # 单例上下文与页面
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._last_active_at = time.time()
        # 惰性 Controller（browser-use）
        self._controller = Controller()
        # 单例 BrowserSession 与索引->selector 映射
        self._browser_session: Optional[BrowserSession] = None
        self._css_selector_map: Dict[int, str] = {}

    async def _ensure_browser_session_for(self, session_id: str):
        # 兼容旧方法签名，内部转到单例会话
        return await self._ensure_browser_session()

    async def _ensure_browser(self):
        if self._browser:
            return

        try:
            self._playwright = await async_playwright().start()
            # 在 VNC/Xvfb 环境下运行需要 DISPLAY，默认绑定到 :1（见 supervisord 的 xvfb 配置）
            if not os.environ.get("DISPLAY"):
                os.environ["DISPLAY"] = ":1"

            # 等待 Xvfb 就绪，避免短时间内连接 X server 失败
            try:
                await self._wait_for_x_server(os.environ["DISPLAY"], timeout_sec=10)
            except Exception:
                pass

            # 兼容原先 supervisor 启动 Chrome 的常用参数；可以通过 CHROME_ARGS 追加自定义参数
            launch_args: List[str] = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--disable-infobars",
                "--start-maximized",
                "--window-size=1280,1029",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--disable-gpu-sandbox",
                "--no-xshm",
                "--disable-notifications",
                "--disable-component-extensions-with-background-pages",
                "--disable-prompt-on-repost",
                "--disable-dialogs",
                "--disable-modal-dialogs",
                # 谨慎项：以下两项会降低安全隔离，仅在明确需要时通过 CHROME_ARGS 传入
                # "--disable-web-security",
                # "--disable-site-isolation-trials",
            ]

            extra = os.getenv("CHROME_ARGS", "").strip()
            if extra:
                launch_args += shlex.split(extra)

            # 说明：Playwright 自己管理与浏览器的调度连接，一般不需要 remote-debugging-port
            # 若确需暴露 CDP，可通过 CHROME_ARGS 传入对应参数
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=launch_args,
            )
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")

    async def _wait_for_x_server(self, display: str, timeout_sec: int = 10) -> None:
        """Wait until X server socket for given DISPLAY exists, or timeout."""
        disp_num = display.split(":")[-1].split(".")[0] if ":" in display else "1"
        sock_path = f"/tmp/.X11-unix/X{disp_num}"
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if os.path.exists(sock_path):
                return
            await asyncio.sleep(0.2)

    async def _ensure_context(self, viewport: Optional[Dict[str, int]] = None, user_agent: Optional[str] = None) -> None:
        if self._context and self._page:
            # 单例已存在时忽略后续 viewport/user_agent 变更，避免类型不匹配的重设
            return
        await self._ensure_browser()
        if self._browser is None:
            return
        try:
            context_kwargs: Dict[str, Any] = {
                "bypass_csp": True,
            }
            if viewport:
                context_kwargs["viewport"] = viewport
            if user_agent:
                context_kwargs["user_agent"] = user_agent
            self._context = await self._browser.new_context(**context_kwargs)
            self._page = await self._context.new_page()
        except Exception:
            self._context = None
            self._page = None

    async def _ensure_browser_session(self) -> Optional[BrowserSession]:
        if self._browser_session is not None:
            return self._browser_session
        await self._ensure_browser()
        if self._browser is None:
            return None
        try:
            self._browser_session = BrowserSession(browser=self._browser)
        except Exception:
            self._browser_session = None
        return self._browser_session

    async def _get_page(self) -> Page:
        await self._ensure_context()
        if not self._page:
            raise HTTPException(status_code=404, detail="page not found")
        return self._page

    async def _wait_for_page_settled(self, page: Page, max_wait_ms: int = 4000, min_wait_ms: int = 2000) -> None:
        """在点击等操作后，尽量等待页面进入稳定状态，避免读取到旧的交互元素。

        策略（尽力而为，均为短超时并忽略异常）：
        - 等待 load
        - 等待 networkidle（适配SPA可能不会真正idle）
        - 轮询 document.readyState 至 complete
        - 轻微延时以等待微任务队列
        """
        start_time = time.time()
        deadline = time.time() + (max_wait_ms / 1000.0)
        def remain_ms(max_slice: int) -> int:
            return max(0, min(max_slice, int((deadline - time.time()) * 1000)))
        # 1) 等待 load
        try:
            await page.wait_for_load_state('load', timeout=remain_ms(2000))
        except Exception:
            pass
        # 2) 等待 networkidle
        try:
            await page.wait_for_load_state('networkidle', timeout=remain_ms(1500))
        except Exception:
            pass
        # 3) 轮询 readyState
        try:
            while time.time() < deadline:
                state = await page.evaluate("() => document.readyState")
                if isinstance(state, str) and state.lower() == 'complete':
                    break
                await asyncio.sleep(0.15)
        except Exception:
            pass
        # 4) 轻微延时
        try:
            await asyncio.sleep(0.15)
            if time.time() - start_time < (min_wait_ms / 1000.0):
                await asyncio.sleep((min_wait_ms / 1000.0) - (time.time() - start_time))
        except Exception:
            pass

    async def _gc_loop(self):
        # 单例模式下无需 GC 循环，保留空实现以兼容
        return

    async def shutdown(self):
        # 关闭单例页面与上下文
        try:
            if self._page:
                try:
                    await self._page.close()
                except Exception:
                    pass
                self._page = None
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
        except Exception:
            pass
        # 关闭浏览器与 Playwright
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    @_api_guard
    async def init_session(self, req: InitRequest) -> Response:
        viewport = None
        if req.viewport:
            viewport = {"width": req.viewport.width, "height": req.viewport.height}
        async with self._lock:
            await self._ensure_context(viewport=viewport, user_agent=req.user_agent)
            if not self._page:
                return Response.error(message="browser not available")
            self._last_active_at = time.time()
            return Response(success=True, message="session initialized", data=None)

    @_api_guard
    async def close_session(self, req: CloseRequest) -> Response:
        async with self._lock:
            try:
                if self._page:
                    try:
                        await self._page.close()
                    except Exception:
                        pass
                    self._page = None
                if self._context:
                    try:
                        await self._context.close()
                    except Exception:
                        pass
                    self._context = None
                self._browser_session = None
                self._css_selector_map = {}
            finally:
                self._last_active_at = time.time()
        return Response(success=True, message="session closed", data=None)

    async def _close_session_internal(self, session_id: str):
        # 兼容旧签名，转到 close_session
        await self.close_session(CloseRequest())

    @_api_guard
    async def open_tab(self, req: OpenTabRequest) -> Response:
        # 单例：将“打开标签”视为确保页面存在并可选导航
        async with self._lock:
            await self._ensure_context()
            if not self._page:
                return Response.error(message="browser not available")
            if req.url:
                try:
                    await self._page.goto(req.url, timeout=15000)
                except Exception:
                    pass
            self._last_active_at = time.time()
            return Response(success=True, message="tab opened", data=None)

    @_api_guard
    async def close_tab(self, req: CloseTabRequest) -> Response:
        # 单例：不支持关闭唯一标签，返回成功但不执行
        async with self._lock:
            self._last_active_at = time.time()
            return Response(success=True, message="single tab mode; close ignored", data=None)

    @_api_guard
    async def activate_tab(self, req: ActivateTabRequest) -> Response:
        # 单例：始终只有一个 tab
        async with self._lock:
            self._last_active_at = time.time()
            return Response(success=True, message="single tab mode; activate noop", data=None)

    @_api_guard
    async def list_tabs(self) -> Response:
        async with self._lock:
            url = ""
            try:
                if self._page:
                    url = self._page.url
            except Exception:
                pass
            return Response(success=True, message="tabs listed", data={"tabs": [{"tab_id": "singleton", "url": url, "is_active": True}]})

    @_api_guard
    async def get_html(self) -> Response:
        page = await self._get_page()
        async with self._lock:
            html = await page.content()
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="html fetched", data={"html": html, "interactive_elements": interactive_elements})

    async def _get_elements(self) -> str:
        page = await self._get_page()
        bs = await self._ensure_browser_session()
        await self._wait_for_page_settled(page)
        if bs is None:
            return ""
        # 通过 browser-use 的 DomService 获取可交互元素与选择器映射
        try:
            dom_service = DomService(page)
            dom_state = await dom_service.get_clickable_elements()
            # 刷新索引->选择器映射（使用 xpath），同时标准化为以 / 或 // 开头
            new_map: Dict[int, str] = {}
            for idx, node in (dom_state.selector_map or {}).items():
                try:
                    raw_xpath = getattr(node, 'xpath', None)
                    if raw_xpath:
                        path = str(raw_xpath).strip()
                        if not (path.startswith('/') or path.startswith('//')):
                            path = '/' + path
                        new_map[int(idx)] = f"xpath={path}"
                except Exception:
                    pass
            self._css_selector_map = new_map
            # 使用 browser-use 的可读化字符串
            lines_str: str = dom_state.element_tree.clickable_elements_to_string()
            # 用于缓存存储
            await bs.get_state_summary(cache_clickable_elements_hashes=True)
            self._last_active_at = time.time()
            return lines_str
        except Exception:
            self._last_active_at = time.time()
            return ""

    @_api_guard
    async def get_elements(self) -> Response:
        lines_str: str = await self._get_elements()
        return Response(success=True, message="elements fetched", data={"interactive_elements": lines_str})

    @_api_guard
    async def click(self, req: ClickRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            target_details: Optional[Dict[str, Any]] = None
            if req.x is not None and req.y is not None:
                btn: Literal['left','middle','right'] = 'left'
                if req.button in ('left','middle','right'):
                    btn = req.button
                try:
                    target_details = await self._get_element_details_by_point(req.x, req.y)
                except Exception:
                    target_details = None
                await page.mouse.click(req.x, req.y, button=btn, click_count=req.clicks or 1)
                interactive_elements = await self._get_elements()
                self._last_active_at = time.time()
                return Response(success=True, message="clicked", data={"target_element": target_details, "interactive_elements": interactive_elements})
            elif req.index is not None:
                # 直接通过 browser-use Controller 按索引点击，失败则回退
                try:
                    browser_session = await self._ensure_browser_session()
                    if browser_session:
                        try:
                            target_details = await self._get_element_details_by_index(req.index)
                        except Exception:
                            target_details = None
                        await self._controller.registry.execute_action(
                            action_name='click_element_by_index',
                            params={"index": str(req.index)},
                            browser_session=browser_session
                        )
                        interactive_elements = await self._get_elements()
                        self._last_active_at = time.time()
                        return Response(success=True, message="clicked", data={"target_element": target_details, "interactive_elements": interactive_elements})
                except Exception:
                    pass
                el = await self._get_element_by_index(req.index)
                if not el:
                    return Response.error(message=f"element index {req.index} not found")
                element = await page.query_selector(el["selector"])
                if not element:
                    return Response.error(message="element not available")
                try:
                    try:
                        target_details = await self._get_element_details_by_selector(el["selector"])
                    except Exception:
                        target_details = None
                    await element.scroll_into_view_if_needed()
                except Exception:
                    pass
                await element.click()
                interactive_elements = await self._get_elements()
                self._last_active_at = time.time()
                return Response(success=True, message="clicked", data={"target_element": target_details, "interactive_elements": interactive_elements})
            else:
                return Response.error(message="either (x,y) or index is required")

    @_api_guard
    async def input(self, req: InputRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            used_controller = False
            target_details: Optional[Dict[str, Any]] = None
            if req.x is not None and req.y is not None:
                try:
                    target_details = await self._get_element_details_by_point(req.x, req.y)
                except Exception:
                    target_details = None
                await page.mouse.click(req.x, req.y)
                await page.keyboard.type(req.text)
            elif req.index is not None:
                # 直接通过 browser-use Controller 输入文本，失败则回退
                used_controller = False
                try:
                    browser_session = await self._ensure_browser_session()
                    if browser_session:
                        try:
                            target_details = await self._get_element_details_by_index(req.index)
                        except Exception:
                            target_details = None
                        await self._controller.registry.execute_action(
                            action_name='input_text',
                            params={"index": str(req.index), "text": req.text},
                            browser_session=browser_session
                        )
                        used_controller = True
                        if req.press_enter:
                            try:
                                await self._controller.registry.execute_action(
                                    action_name='send_keys',
                                    params={"keys": "Enter"},
                                    browser_session=browser_session
                                )
                            except Exception:
                                pass
                except Exception:
                    used_controller = False
                if not used_controller:
                    el = await self._get_element_by_index(req.index)
                    if not el:
                        return Response.error(message=f"element index {req.index} not found")
                    element = await page.query_selector(el["selector"])
                    if not element:
                        return Response.error(message="element not available")
                    try:
                        try:
                            target_details = await self._get_element_details_by_selector(el["selector"])
                        except Exception:
                            target_details = None
                        await element.fill("")
                        await element.type(req.text)
                    except Exception:
                        await element.click()
                        await page.keyboard.type(req.text)
            else:
                return Response.error(message="either (x,y) or index is required")
            if req.press_enter and not used_controller:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="input sent", data={"target_element": target_details, "interactive_elements": interactive_elements})

    @_api_guard
    async def select(self, req: SelectRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            el = await self._get_element_by_index(req.index)
            if not el:
                return Response.error(message=f"element index {req.index} not found")
            element = await page.query_selector(el["selector"])
            if not element:
                return Response.error(message="element not available")
            target_details: Optional[Dict[str, Any]] = None
            try:
                target_details = await self._get_element_details_by_selector(el["selector"])
            except Exception:
                target_details = None
            await element.select_option(index=req.option)
            self._last_active_at = time.time()
            interactive_elements = await self._get_elements()
            return Response(success=True, message="option selected", data={"target_element": target_details, "interactive_elements": interactive_elements})

    @_api_guard
    async def scroll(self, req: ScrollRequest) -> Response:
        async with self._lock:
            browser_session = await self._ensure_browser_session()
            if browser_session:
                res = await self._controller.registry.execute_action(
                    action_name='scroll',
                    params={"down": req.down, "num_pages": req.num_pages, "index": req.index},
                    browser_session=browser_session
                )
                interactive_elements = await self._get_elements()
                self._last_active_at = time.time()
                return Response(success=True, message="scrolled", data={"result": res.extracted_content, "interactive_elements": interactive_elements})
            else:
                return Response.error(message="browser session not available")

    @_api_guard
    async def key(self, req: KeyRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            # 直接使用 browser-use 的 send_keys 动作，失败则回退
            used_controller = False
            try:
                browser_session = await self._ensure_browser_session()
                if browser_session:
                    await self._controller.registry.execute_action(
                        action_name='send_keys',
                        params={"keys": req.key},
                        browser_session=browser_session
                    )
                    used_controller = True
            except Exception:
                used_controller = False
            if not used_controller:
                await page.keyboard.press(req.key)
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="key pressed", data={"interactive_elements": interactive_elements})

    @_api_guard
    async def evaluate(self, req: EvaluateRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            result = await page.evaluate(req.javascript)
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="evaluated", data={"result": result, "interactive_elements": interactive_elements})

    @_api_guard
    async def screenshot(self, req: ScreenshotRequest) -> Response:
        page = await self._get_page()
        async with self._lock:
            options: Dict[str, Any] = {}
            if req.full_page:
                options["full_page"] = True
            if req.clip:
                options["clip"] = {"x": req.clip.x, "y": req.clip.y, "width": req.clip.width, "height": req.clip.height}
            buf = await page.screenshot(**options)
            b64 = base64.b64encode(buf).decode("ascii")
            size = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="screenshot taken", data={"image_base64": b64, "width": size.get("w", 0), "height": size.get("h", 0), "interactive_elements": interactive_elements})

    @_api_guard
    async def navigate_to_url(self, req: NavigateRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            await bs.navigate(req.url, timeout_ms=25000)
            lines_str = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="navigated", data={"interactive_elements": lines_str})

    @_api_guard
    async def go_back(self, req: GoBackRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            await self._controller.registry.execute_action(
                action_name='go_back', params={}, browser_session=bs
            )
            lines_str = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="went back", data={"interactive_elements": lines_str})

    @_api_guard
    async def send_keys_action(self, req: SendKeysRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='send_keys', params={"keys": req.keys}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="keys sent", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def scroll_to_text(self, req: ScrollToTextRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='scroll_to_text', params={"text": req.text}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="scrolled to text", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def extract_structured_data(self) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            page = await bs.get_current_page()
            content = ''
            for iframe in page.frames:
                try:
                    await iframe.wait_for_load_state(timeout=1000)
                except Exception:
                    pass
                if iframe.url != page.url and not iframe.url.startswith('data:') and not iframe.url.startswith('about:'):
                    content += f"\n\nIFRAME {iframe.url}:\n"
                    try:
                        iframe_html = await asyncio.wait_for(iframe.content(), timeout=2.0)
                        # markdownify 在上方未导入，此处改为直接追加 HTML 以避免未使用导入
                        content += iframe_html
                    except Exception:
                        pass
            page_html_result = await asyncio.wait_for(page.content(), timeout=10.0)
            content += page_html_result
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="structured data extracted", data={"html": content, "interactive_elements": interactive_elements})

    @_api_guard
    async def select_dropdown_option(self, req: SelectDropdownOptionRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='select_dropdown_option', params={"index": req.index, "text": req.text}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="option selected", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def upload_file(self, req: UploadFileRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            interactive_elements = await self._get_elements()
            res = await self._controller.registry.execute_action(
                action_name='upload_file', params={"index": req.index, "path": req.path}, browser_session=bs
            )
            self._last_active_at = time.time()
            return Response(success=True, message="file uploaded", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def close_tab_by_id(self, req: CloseTabByIdRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='close_tab', params={"page_id": req.page_id}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="tab closed", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def switch_tab_by_id(self, req: SwitchTabByIdRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='switch_tab', params={"page_id": req.page_id}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="tab switched", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def wait_action(self, req: WaitRequest) -> Response:
        async with self._lock:
            bs = await self._ensure_browser_session()
            if not bs:
                return Response.error(message="browser session not available")
            res = await self._controller.registry.execute_action(
                action_name='wait', params={"seconds": req.seconds}, browser_session=bs
            )
            interactive_elements = await self._get_elements()
            self._last_active_at = time.time()
            return Response(success=True, message="waited", data={"result": res.extracted_content, "interactive_elements": interactive_elements})

    @_api_guard
    async def health(self) -> Response:
        return Response(success=True, message="ok", data={
            "playwright": "ready" if self._playwright else "not_ready",
            "browser": "launched" if self._browser else "closed",
            "singleton": bool(self._page),
        })

    async def _get_session(self, session_id: str) -> SessionTabs:
        # 单例模式，保留兼容但不使用
        raise HTTPException(status_code=404, detail="single-session mode")

    async def _ensure_tab_id(self, session_id: str, tab_id: Optional[str]) -> str:
        # 单例模式，无意义
        return "singleton"

    # 删除 _get_page 旧签名，统一使用无参版本

    async def _get_element_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        # 使用单例缓存映射
        if index in self._css_selector_map:
            return {"index": index, "selector": self._css_selector_map[index], "tag": "", "text": ""}
        return None

    async def _get_element_details_from_handle(self, element) -> Optional[Dict[str, Any]]:
        if not element:
            return None
        details: Optional[Dict[str, Any]] = None
        try:
            details = await element.evaluate(
                r"""
                (el) => {
                    const rect = el.getBoundingClientRect();
                    const attrs = {};
                    if (el.getAttributeNames) {
                        for (const name of el.getAttributeNames()) {
                            attrs[name] = el.getAttribute(name);
                        }
                    }
                    return {
                        tag: (el.tagName || '').toLowerCase(),
                        id: el.id || null,
                        classes: (typeof el.className === 'string') ? el.className : null,
                        name: el.getAttribute && el.getAttribute('name'),
                        type: el.getAttribute && el.getAttribute('type'),
                        role: el.getAttribute && el.getAttribute('role'),
                        aria_label: el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')),
                        text: (el.innerText || el.textContent || '').trim().slice(0, 500),
                        href: el.getAttribute && el.getAttribute('href'),
                        src: el.getAttribute && el.getAttribute('src'),
                        placeholder: el.getAttribute && el.getAttribute('placeholder'),
                        value: ('value' in el) ? el.value : null,
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        visible: !!(el.offsetParent !== null || (rect.width && rect.height)),
                        disabled: !!(el.disabled),
                        attributes: attrs,
                    };
                }
                """
            )
        except Exception as e:
            print(f"Error getting element details from handle: {e}")
            details = None
        try:
            box = await element.bounding_box()
            if details is None:
                details = {}
            details["bounding_box"] = box
        except Exception:
            pass
        return details

    async def _get_element_details_by_selector(self, selector: str) -> Optional[Dict[str, Any]]:
        page = await self._get_page()
        sel = selector
        candidates: List[str] = [sel]
        # 针对 xpath= 的 selector，补充可能的变体（缺少前导/，或 html/... 开头）
        if sel.startswith('xpath='):
            value = sel[len('xpath='):].strip()
            if value and not (value.startswith('/') or value.startswith('//')):
                candidates.append(f'xpath=/{value}')
            if value.startswith('html/'):
                # 试试以 // 作为起点
                candidates.append(f'xpath=//{value}')
                rest = value[5:] if len(value) > 5 else ''
                if rest:
                    candidates.append(f'xpath=//{rest}')
        element = None
        # 先在主文档尝试
        for cand in candidates:
            try:
                element = await page.query_selector(cand)
            except Exception:
                element = None
            if element:
                sel = cand
                break
        # 若未找到，在所有 frame 中尝试
        if not element:
            try:
                for frame in page.frames:
                    for cand in candidates:
                        try:
                            element = await frame.query_selector(cand)
                        except Exception:
                            element = None
                        if element:
                            sel = cand
                            break
                    if element:
                        break
            except Exception:
                element = None
        if not element:
            return None
        details = await self._get_element_details_from_handle(element)
        if details is not None:
            details['selector'] = sel
        return details

    async def _get_element_details_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        el = await self._get_element_by_index(index)
        print(f"Element: {el}")
        if not el:
            return None
        print(f"Element selector: {el['selector']}")
        return await self._get_element_details_by_selector(el["selector"])

    async def _get_element_details_by_point(self, x: float, y: float) -> Optional[Dict[str, Any]]:
        page = await self._get_page()
        # 先用 elementFromPoint 获取基本信息与一个简易 CSS 路径，再尝试回查 selector 获取更完整数据
        info = None
        try:
            info = await page.evaluate(
                r"""
                ([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    const attrs = {};
                    if (el.getAttributeNames) {
                        for (const name of el.getAttributeNames()) {
                            attrs[name] = el.getAttribute(name);
                        }
                    }
                    function cssPath(e) {
                        if (!e || e.nodeType !== 1) return null;
                        const parts = [];
                        let cur = e;
                        let depth = 0;
                        while (cur && depth < 5) {
                            let part = cur.nodeName.toLowerCase();
                            if (cur.id) { part += '#' + cur.id; parts.unshift(part); break; }
                            let cls = (typeof cur.className === 'string') ? cur.className.trim().split(/\s+/).slice(0,3).join('.') : '';
                            if (cls) part += '.' + cls;
                            let sib = cur; let nth = 1;
                            while ((sib = sib.previousElementSibling) != null) {
                                if (sib.nodeName === cur.nodeName) nth++;
                            }
                            if (nth > 1) part += `:nth-of-type(${nth})`;
                            parts.unshift(part);
                            cur = cur.parentElement;
                            depth++;
                        }
                        return parts.join(' > ');
                    }
                    return {
                        tag: (el.tagName || '').toLowerCase(),
                        id: el.id || null,
                        classes: (typeof el.className === 'string') ? el.className : null,
                        name: el.getAttribute && el.getAttribute('name'),
                        type: el.getAttribute && el.getAttribute('type'),
                        role: el.getAttribute && el.getAttribute('role'),
                        aria_label: el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')),
                        text: (el.innerText || el.textContent || '').trim().slice(0, 500),
                        href: el.getAttribute && el.getAttribute('href'),
                        src: el.getAttribute && el.getAttribute('src'),
                        placeholder: el.getAttribute && el.getAttribute('placeholder'),
                        value: ('value' in el) ? el.value : null,
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        visible: !!(el.offsetParent !== null || (rect.width && rect.height)),
                        disabled: !!(el.disabled),
                        attributes: attrs,
                        css_selector: cssPath(el)
                    };
                }
                """,
                [x, y]
            )
        except Exception:
            info = None
        # 如果拿到 css_selector，尽量回查以补充 selector 与 bounding_box
        if info and isinstance(info, dict) and info.get("css_selector"):
            try:
                details = await self._get_element_details_by_selector(info["css_selector"])  # type: ignore[index]
                if details:
                    return details
            except Exception:
                pass
        return info


browser_service = BrowserService()
