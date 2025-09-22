from fastapi import HTTPException
from typing import Any, Dict, Optional


class APIException(HTTPException):
    def __init__(
        self,
        code: int,
        msg: str,
        status_code: int = 400,
        headers: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.msg = msg
        super().__init__(status_code=status_code, detail=msg, headers=headers)


class NotFoundError(APIException):
    def __init__(self, msg: str = "Resource not found"):
        super().__init__(code=404, msg=msg, status_code=404)


class BadRequestError(APIException):
    def __init__(self, msg: str = "Bad request parameters"):
        super().__init__(code=400, msg=msg, status_code=400)


class ServerError(APIException):
    def __init__(self, msg: str = "Internal server error"):
        super().__init__(code=500, msg=msg, status_code=500)


class UnauthorizedError(APIException):
    def __init__(self, msg: str = "Unauthorized"):
        super().__init__(code=401, msg=msg, status_code=401) 

class FileNotFoundError(APIException):
    def __init__(self, msg: str = "File not found"):
        super().__init__(code=404, msg=msg, status_code=404)

class PermissionDeniedError(APIException):
    def __init__(self, msg: str = "Permission denied"):
        super().__init__(code=403, msg=msg, status_code=403)

class OperationError(APIException):
    def __init__(self, msg: str = "Operation failed"):
        super().__init__(code=400, msg=msg, status_code=400)
