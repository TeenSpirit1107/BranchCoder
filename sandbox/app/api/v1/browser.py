from fastapi import APIRouter

from app.schemas.response import Response
from app.schemas.browser import (
    InitRequest,
    CloseRequest,
    OpenTabRequest,
    CloseTabRequest,
    ActivateTabRequest,
    NavigateRequest,
    ClickRequest,
    InputRequest,
    SelectRequest,
    ScrollRequest,
    KeyRequest,
    EvaluateRequest,
    ScreenshotRequest,
    GoBackRequest,
    SendKeysRequest,
    ScrollToTextRequest,
    SelectDropdownOptionRequest,
    UploadFileRequest,
    CloseTabByIdRequest,
    SwitchTabByIdRequest,
    WaitRequest,
)
from app.services.browser import browser_service


router = APIRouter()


@router.post("/init", response_model=Response)
async def init_browser(req: InitRequest) -> Response:
    result = await browser_service.init_session(req)
    return result


@router.post("/close", response_model=Response)
async def close_session(req: CloseRequest) -> Response:
    return await browser_service.close_session(req)


@router.post("/tabs/open", response_model=Response)
async def open_tab(req: OpenTabRequest) -> Response:
    return await browser_service.open_tab(req)


@router.post("/tabs/close", response_model=Response)
async def close_tab(req: CloseTabRequest) -> Response:
    return await browser_service.close_tab(req)


@router.post("/tabs/activate", response_model=Response)
async def activate_tab(req: ActivateTabRequest) -> Response:
    return await browser_service.activate_tab(req)


@router.get("/tabs/list", response_model=Response)
async def list_tabs() -> Response:
    return await browser_service.list_tabs()


@router.post("/navigate", response_model=Response)
async def navigate(req: NavigateRequest) -> Response:
    return await browser_service.navigate_to_url(req)


@router.get("/html", response_model=Response)
async def get_html() -> Response:
    return await browser_service.get_html()


@router.get("/elements", response_model=Response)
async def get_elements() -> Response:
    return await browser_service.get_elements()


@router.post("/click", response_model=Response)
async def click(req: ClickRequest) -> Response:
    return await browser_service.click(req)


@router.post("/input", response_model=Response)
async def input_text(req: InputRequest) -> Response:
    return await browser_service.input(req)


@router.post("/select", response_model=Response)
async def select_option(req: SelectRequest) -> Response:
    return await browser_service.select(req)


@router.post("/scroll", response_model=Response)
async def scroll(req: ScrollRequest) -> Response:
    return await browser_service.scroll(req)


@router.post("/key", response_model=Response)
async def press_key(req: KeyRequest) -> Response:
    return await browser_service.key(req)


@router.post("/evaluate", response_model=Response)
async def evaluate(req: EvaluateRequest) -> Response:
    return await browser_service.evaluate(req)


@router.post("/screenshot", response_model=Response)
async def screenshot(req: ScreenshotRequest) -> Response:
    return await browser_service.screenshot(req)

# ====== 扩展路由（browser-use demo 动作） ======

@router.post("/go_back", response_model=Response)
async def go_back(req: GoBackRequest) -> Response:
    return await browser_service.go_back(req)


@router.post("/send_keys", response_model=Response)
async def send_keys(req: SendKeysRequest) -> Response:
    return await browser_service.send_keys_action(req)


@router.post("/scroll_to_text", response_model=Response)
async def scroll_to_text(req: ScrollToTextRequest) -> Response:
    return await browser_service.scroll_to_text(req)


@router.post("/extract_structured_data", response_model=Response)
async def extract_structured_data() -> Response:
    return await browser_service.extract_structured_data()


@router.post("/select_dropdown_option", response_model=Response)
async def select_dropdown_option(req: SelectDropdownOptionRequest) -> Response:
    return await browser_service.select_dropdown_option(req)


@router.post("/upload_file", response_model=Response)
async def upload_file(req: UploadFileRequest) -> Response:
    return await browser_service.upload_file(req)


@router.post("/close_tab_by_id", response_model=Response)
async def close_tab_by_id(req: CloseTabByIdRequest) -> Response:
    return await browser_service.close_tab_by_id(req)


@router.post("/switch_tab_by_id", response_model=Response)
async def switch_tab_by_id(req: SwitchTabByIdRequest) -> Response:
    return await browser_service.switch_tab_by_id(req)


@router.post("/wait", response_model=Response)
async def wait(req: WaitRequest) -> Response:
    return await browser_service.wait_action(req)


@router.get("/health", response_model=Response)
async def health() -> Response:
    return await browser_service.health()

