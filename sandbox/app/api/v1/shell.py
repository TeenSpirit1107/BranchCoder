from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
from app.schemas.shell import (
    ShellExecRequest, ShellViewRequest, ShellWaitRequest,
    ShellWriteToProcessRequest, ShellKillProcessRequest,
)
from app.schemas.response import Response
from app.services.shell import shell_service
from app.core.exceptions import AppException, BadRequestException

router = APIRouter()

MAX_ERROR_OUTPUT_BYTES = 4000

def _collect_shell_diagnostics(session_id: str, command: str | None = None, exec_dir: str | None = None) -> Dict[str, Any]:
    """Collect recent shell output and exit code for better error visibility."""
    diagnostics: Dict[str, Any] = {
        "session_id": session_id,
        "command": command,
        "exec_dir": exec_dir,
    }
    try:
        # Try to get latest output (may raise if session not found)
        view = None
        try:
            view = shell_service.active_shells.get(session_id)
            if view is not None:
                raw_output: str = view.get("output", "")
                if raw_output:
                    diagnostics["output_tail"] = raw_output[-MAX_ERROR_OUTPUT_BYTES:]
            # Exit code if any
            process = view.get("process") if view else None
            diagnostics["exit_code"] = getattr(process, "returncode", None)
        except Exception:
            pass
    except Exception:
        # Best effort only
        pass
    return diagnostics

@router.post("/exec", response_model=Response)
async def exec_command(request: ShellExecRequest):
    """
    Execute command in the specified shell session
    """
    # If no session ID is provided, automatically create one
    if not request.id or request.id == "":
        request.id = shell_service.create_session_id()
    try:
        result = await shell_service.exec_command(
            session_id=request.id,
            exec_dir=request.exec_dir,
            command=request.command
        )
        # If the command finished and returned non-zero, surface it clearly in message
        message = "Command executed"
        if result.returncode is not None and result.returncode != 0:
            message = f"Command exited with non-zero code: {result.returncode}"
        return Response(
            success=True,
            message=message,
            data=result.model_dump()
        )
    except AppException as e:
        diag = _collect_shell_diagnostics(request.id, request.command, request.exec_dir)
        # Merge original data if available
        if isinstance(e.data, dict):
            diag.update({k: v for k, v in e.data.items() if k not in diag})
        err = Response.error(message=e.message, data=diag)
        return JSONResponse(status_code=e.status_code, content=err.model_dump())
    except Exception as e:
        diag = _collect_shell_diagnostics(request.id, request.command, request.exec_dir)
        diag["error_type"] = e.__class__.__name__
        err = Response.error(message=str(e), data=diag)
        return JSONResponse(status_code=500, content=err.model_dump())

@router.post("/view", response_model=Response)
async def view_shell(request: ShellViewRequest):
    """
    View output of the specified shell session
    """
    if not request.id or request.id == "":
        raise BadRequestException("Session ID not provided")
        
    try:
        result = await shell_service.view_shell(session_id=request.id)
        return Response(
            success=True,
            message="Session content retrieved successfully",
            data=result.model_dump()
        )
    except AppException as e:
        diag = _collect_shell_diagnostics(request.id)
        if isinstance(e.data, dict):
            diag.update({k: v for k, v in e.data.items() if k not in diag})
        err = Response.error(message=e.message, data=diag)
        return JSONResponse(status_code=e.status_code, content=err.model_dump())
    except Exception as e:
        diag = _collect_shell_diagnostics(request.id)
        diag["error_type"] = e.__class__.__name__
        err = Response.error(message=str(e), data=diag)
        return JSONResponse(status_code=500, content=err.model_dump())

@router.post("/wait", response_model=Response)
async def wait_for_process(request: ShellWaitRequest):
    """
    Wait for the process in the specified shell session to return
    """
    try:
        result = await shell_service.wait_for_process(
            session_id=request.id,
            seconds=request.seconds
        )
        # Attach output tail on completion for better context
        diag = _collect_shell_diagnostics(request.id)
        payload = result.model_dump()
        if "output_tail" in diag:
            payload["output_tail"] = diag["output_tail"]
        return Response(
            success=True,
            message=f"Process completed, return code: {result.returncode}",
            data=payload
        )
    except AppException as e:
        diag = _collect_shell_diagnostics(request.id)
        if isinstance(e.data, dict):
            diag.update({k: v for k, v in e.data.items() if k not in diag})
        err = Response.error(message=e.message, data=diag)
        return JSONResponse(status_code=e.status_code, content=err.model_dump())
    except Exception as e:
        diag = _collect_shell_diagnostics(request.id)
        diag["error_type"] = e.__class__.__name__
        err = Response.error(message=str(e), data=diag)
        return JSONResponse(status_code=500, content=err.model_dump())

@router.post("/write", response_model=Response)
async def write_to_process(request: ShellWriteToProcessRequest):
    """
    Write input to the process in the specified shell session
    """
    if not request.id or request.id == "":
        raise BadRequestException("Session ID not provided")
    try:
        result = await shell_service.write_to_process(
            session_id=request.id,
            input_text=request.input,
            press_enter=request.press_enter
        )
        return Response(
            success=True,
            message="Input written",
            data=result.model_dump()
        )
    except AppException as e:
        diag = _collect_shell_diagnostics(request.id)
        if isinstance(e.data, dict):
            diag.update({k: v for k, v in e.data.items() if k not in diag})
        err = Response.error(message=e.message, data=diag)
        return JSONResponse(status_code=e.status_code, content=err.model_dump())
    except Exception as e:
        diag = _collect_shell_diagnostics(request.id)
        diag["error_type"] = e.__class__.__name__
        err = Response.error(message=str(e), data=diag)
        return JSONResponse(status_code=500, content=err.model_dump())

@router.post("/kill", response_model=Response)
async def kill_process(request: ShellKillProcessRequest):
    """
    Terminate the process in the specified shell session
    """
    try:
        result = await shell_service.kill_process(session_id=request.id)
        message = "Process terminated" if result.status == "terminated" else "Process ended"
        # Include output tail to help confirm what happened before termination
        diag = _collect_shell_diagnostics(request.id)
        payload = result.model_dump()
        if "output_tail" in diag:
            payload["output_tail"] = diag["output_tail"]
        return Response(
            success=True,
            message=message,
            data=payload
        )
    except AppException as e:
        diag = _collect_shell_diagnostics(request.id)
        if isinstance(e.data, dict):
            diag.update({k: v for k, v in e.data.items() if k not in diag})
        err = Response.error(message=e.message, data=diag)
        return JSONResponse(status_code=e.status_code, content=err.model_dump())
    except Exception as e:
        diag = _collect_shell_diagnostics(request.id)
        diag["error_type"] = e.__class__.__name__
        err = Response.error(message=str(e), data=diag)
        return JSONResponse(status_code=500, content=err.model_dump())