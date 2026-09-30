"""Exception hierarchy. Each class carries the process exit code the CLI uses."""


class GtaskError(Exception):
    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(GtaskError):
    exit_code = 2


class AuthError(GtaskError):
    exit_code = 3


class NotFoundError(GtaskError):
    exit_code = 4


class AmbiguousError(GtaskError):
    exit_code = 4


class ApiError(GtaskError):
    exit_code = 1

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"API error {status}: {message}")
        self.status = status
