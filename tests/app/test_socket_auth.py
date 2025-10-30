import os
import sys
import tempfile
from collections.abc import Generator
from importlib import util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pytest import MonkeyPatch


def _load_socket_module(monkeypatch: MonkeyPatch) -> ModuleType:
    module_path = Path(__file__).resolve().parents[2]
    backend_root = module_path / "upstream" / "chainlit" / "backend"
    temp_root = Path(tempfile.mkdtemp(prefix="chainlit_app_root_"))
    fake_config_dir = temp_root / ".chainlit"
    fake_config_dir.mkdir(parents=True, exist_ok=True)
    (fake_config_dir / "config.toml").write_text(
        """[meta]\ngenerated_by = \"0.3.1\"\n\n[project]\nuser_env = []\n\n[features]\n\n[UI]\nname = \"Test\"\n""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHAINLIT_APP_ROOT", str(temp_root))
    monkeypatch.syspath_prepend(str(backend_root))

    chainlit_pkg = ModuleType("chainlit")
    chainlit_pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "chainlit", chainlit_pkg)

    def stub_module(name: str, attrs: dict[str, object]) -> ModuleType:
        module = ModuleType(name)
        for attr_name, attr_value in attrs.items():
            setattr(module, attr_name, attr_value)
        monkeypatch.setitem(sys.modules, name, module)
        setattr(chainlit_pkg, name.split(".")[-1], module)
        return module

    class _Logger:
        def exception(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

    stub_module(
        "chainlit.logger",
        {"logger": _Logger()},
    )

    async def _noop_async(*args, **kwargs):
        return None

    stub_module(
        "chainlit.auth",
        {
            "get_current_user": _noop_async,
            "get_token_from_cookies": lambda cookies: cookies.get("access_token"),
            "require_login": lambda: False,
        },
    )

    stub_module("chainlit.chat_context", {"chat_context": SimpleNamespace(add=lambda *args, **kwargs: None)})
    stub_module("chainlit.config", {"ChainlitConfig": object, "config": SimpleNamespace(project=SimpleNamespace(user_env=[]), code=SimpleNamespace(on_chat_start=None, on_chat_resume=None))})
    stub_module("chainlit.context", {"init_ws_context": lambda sid: SimpleNamespace(emitter=SimpleNamespace(task_end=_noop_async, clear=_noop_async, emit=_noop_async, resume_thread=_noop_async, send_resume_thread_error=_noop_async), session=SimpleNamespace(restored=False, has_first_interaction=False, current_task=None, thread_id_to_resume=None))})
    stub_module("chainlit.data", {"get_data_layer": lambda: None})
    stub_module("chainlit.message", {"ErrorMessage": object, "Message": SimpleNamespace(from_dict=lambda data: data)})
    class _SIO:
        def emit(self, *args, **kwargs):
            return None

        def call(self, *args, **kwargs):
            return None

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    stub_module("chainlit.server", {"sio": _SIO()})

    class _WebsocketSession:
        @classmethod
        def get_by_id(cls, session_id):
            return None

        def __init__(self, *args, **kwargs):
            pass

        def restore(self, **kwargs):
            pass

    stub_module("chainlit.session", {"WebsocketSession": _WebsocketSession})
    stub_module(
        "chainlit.types",
        {
            "InputAudioChunk": object,
            "InputAudioChunkPayload": object,
            "MessagePayload": object,
        },
    )
    stub_module("chainlit.user", {"PersistedUser": object, "User": object})
    stub_module("chainlit.user_session", {"user_sessions": {}})

    module_path = backend_root / "chainlit" / "socket.py"
    spec = util.spec_from_file_location("chainlit_socket_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load socket module for tests")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def socket_module() -> Generator[ModuleType, None, None]:
    monkeypatch = MonkeyPatch()
    try:
        module = _load_socket_module(monkeypatch)
        yield module
    finally:
        monkeypatch.undo()


def test_load_socket_module_restores_environment_and_sys_path():
    has_original_env = "CHAINLIT_APP_ROOT" in os.environ
    original_env_value = os.environ.get("CHAINLIT_APP_ROOT")
    original_sys_path = list(sys.path)

    monkeypatch = MonkeyPatch()
    try:
        _load_socket_module(monkeypatch)
    finally:
        monkeypatch.undo()

    if has_original_env:
        assert os.environ.get("CHAINLIT_APP_ROOT") == original_env_value
    else:
        assert "CHAINLIT_APP_ROOT" not in os.environ
    assert sys.path == original_sys_path


def test_get_token_uses_cookie_over_other_sources(socket_module: ModuleType):
    environ = {
        "HTTP_COOKIE": "access_token=cookie-token",
        "HTTP_AUTHORIZATION": "Bearer header-token",
    }

    result = socket_module._get_token(environ, {"token": "auth-token"})

    assert result == "cookie-token"


def test_get_token_falls_back_to_authorization_header(socket_module: ModuleType):
    environ = {
        "HTTP_AUTHORIZATION": "Bearer header-token",
    }

    result = socket_module._get_token(environ, {"token": "auth-token"})

    assert result == "header-token"


def test_get_token_uses_auth_payload_as_last_resort(socket_module: ModuleType):
    environ = {}

    result = socket_module._get_token(environ, {"token": "auth-token"})

    assert result == "auth-token"
