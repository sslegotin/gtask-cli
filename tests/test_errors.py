from gtask.errors import (
    AmbiguousError,
    ApiError,
    AuthError,
    GtaskError,
    NotFoundError,
    UsageError,
)


def test_exit_codes():
    assert GtaskError("x").exit_code == 1
    assert UsageError("x").exit_code == 2
    assert AuthError("x").exit_code == 3
    assert NotFoundError("x").exit_code == 4
    assert AmbiguousError("x").exit_code == 4
    assert ApiError(500, "boom").exit_code == 1


def test_message_and_str():
    err = NotFoundError("no such list")
    assert err.message == "no such list"
    assert str(err) == "no such list"


def test_api_error_carries_status():
    err = ApiError(404, "Not Found")
    assert err.status == 404
    assert err.message == "API error 404: Not Found"
    assert isinstance(err, GtaskError)
