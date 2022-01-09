import pytest


@pytest.fixture()
def class_caplog(request, caplog):
    request.cls.caplog = caplog
