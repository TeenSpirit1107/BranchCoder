from typing import Optional
from pydantic import BaseModel, Field


class Viewport(BaseModel):
    width: int = Field(1280)
    height: int = Field(1029)


class InitRequest(BaseModel):
    viewport: Optional[Viewport] = None
    user_agent: Optional[str] = None


class CloseRequest(BaseModel):
    pass


class OpenTabRequest(BaseModel):
    url: Optional[str] = None


class CloseTabRequest(BaseModel):
    pass


class ActivateTabRequest(BaseModel):
    pass


class NavigateRequest(BaseModel):
    url: str
    timeout_ms: Optional[int] = Field(default=15000)


class ClickRequest(BaseModel):
    index: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    button: Optional[str] = Field(default="left")
    clicks: Optional[int] = Field(default=1)


class InputRequest(BaseModel):
    text: str
    press_enter: Optional[bool] = Field(default=False)
    index: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None


class SelectRequest(BaseModel):
    index: int
    option: int


class ScrollRequest(BaseModel):
    down: bool  # True to scroll down, False to scroll up
    num_pages: float  # Number of pages to scroll (0.5 = half page, 1.0 = one page, etc.)
    index: int | None = None  # Optional element index to find scroll container for


class KeyRequest(BaseModel):
    key: str


class EvaluateRequest(BaseModel):
    javascript: str
    timeout_ms: Optional[int] = Field(default=5000)


class Clip(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ScreenshotRequest(BaseModel):
    full_page: Optional[bool] = Field(default=False)
    clip: Optional[Clip] = None

# ====== browser-use demo 对应的请求模型 ======

class GoBackRequest(BaseModel):
    pass


class SendKeysRequest(BaseModel):
    keys: str


class ScrollToTextRequest(BaseModel):
    text: str

class SelectDropdownOptionRequest(BaseModel):
    index: int
    text: str


class UploadFileRequest(BaseModel):
    index: int
    path: str

class CloseTabByIdRequest(BaseModel):
    page_id: int


class SwitchTabByIdRequest(BaseModel):
    page_id: int


class WaitRequest(BaseModel):
    seconds: int
