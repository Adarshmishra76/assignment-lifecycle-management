from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, detail: str, code: str = "error") -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(404, detail, "not_found")


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(409, detail, "conflict")


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(403, detail, "forbidden")


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(401, detail, "unauthorized")


class ValidationAppError(AppError):
    def __init__(self, detail: str = "Validation error") -> None:
        super().__init__(422, detail, "validation_error")


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": "http_error"},
    )
