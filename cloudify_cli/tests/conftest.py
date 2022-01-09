import pytest


@pytest.fixture()
def class_caplog(request, caplog):
    request.cls.caplog = caplog


@pytest.fixture()
def class_tmpdir(request, tmpdir):
    request.cls.tmpdir = tmpdir
