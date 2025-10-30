import os
import sys
import tempfile
from importlib import import_module, util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_socket_module(temp_root: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module_path = Path(__file__).resolve().parents[2]
    backend_root = module_path / "upstream" / "chainlit" / "backend"
    fake_config_dir = temp_root / ".chainlit"
    fake_config_dir.mkdir(parents=True, exist_ok=True)
    (fake_config_dir / "config.toml").write_text(
        """[meta]\ngenerated_by = \"0.3.1\"\n\n[project]\nuser_env = []\n\n[features]\n\n[UI]\nname = \"Test\"\n""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHAINLIT_APP_ROOT", str(temp_root))
    monkeypatch.syspath_prepend(str(backend_root))

    with pytest.MonkeyPatch.context() as module_patch:
        chainlit_pkg = ModuleType("chainlit")
        chainlit_pkg.__path__ = []  # type: ignore[attr-defined]
        module_patch.setitem(sys.modules, "chainlit", chainlit_pkg)

        def stub_module(name: str, attrs: dict[str, object]) -> ModuleType:
            module = ModuleType(name)
            for attr_name, attr_value in attrs.items():
                setattr(module, attr_name, attr_value)
            module_patch.setitem(sys.modules, name, module)
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
        sys.modules["chainlit_socket_module"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop("chainlit_socket_module", None)

    return module


@pytest.fixture()
def socket_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    with tempfile.TemporaryDirectory(prefix="chainlit_app_root_") as temp_dir:
        module = _load_socket_module(Path(temp_dir), monkeypatch)
        yield module


@pytest.fixture()
def get_token(socket_module: ModuleType):
    return socket_module._get_token


def test_get_token_uses_cookie_over_other_sources(get_token):
    environ = {
        "HTTP_COOKIE": "access_token=cookie-token",
        "HTTP_AUTHORIZATION": "Bearer header-token",
    }

    result = get_token(environ, {"token": "auth-token"})

    assert result == "cookie-token"


def test_get_token_falls_back_to_authorization_header(get_token):
    environ = {
        "HTTP_AUTHORIZATION": "Bearer header-token",
    }

    result = get_token(environ, {"token": "auth-token"})

    assert result == "header-token"


def test_get_token_uses_auth_payload_as_last_resort(get_token):
    environ = {}

    result = get_token(environ, {"token": "auth-token"})

    assert result == "auth-token"


def test_socket_loader_replaces_stubbed_chainlit_server(socket_module: ModuleType):
    assert "chainlit.server" not in sys.modules

    spec = util.find_spec("chainlit.server")

    assert spec is not None and spec.origin is not None
    assert Path(spec.origin).name == "server.py"


def test_socket_loader_restores_sys_modules(socket_module: ModuleType):
    assert "chainlit_socket_module" not in sys.modules
    assert "chainlit.server" not in sys.modules

    with pytest.raises(FileNotFoundError):
        import_module("chainlit.server")

    assert "chainlit.server" not in sys.modules


def test_socket_loader_cleans_up_after_failure(monkeypatch: pytest.MonkeyPatch):
    original_spec_from_file_location = util.spec_from_file_location

    def failing_spec_from_file_location(*args, **kwargs):
        spec = original_spec_from_file_location(*args, **kwargs)
        assert spec is not None and spec.loader is not None

        def _raise(module: ModuleType) -> None:  # pragma: no cover - simple helper
            raise RuntimeError("forced failure during socket module load")

        monkeypatch.setattr(spec.loader, "exec_module", _raise)
        return spec

    monkeypatch.setattr(util, "spec_from_file_location", failing_spec_from_file_location)

    original_chainlit = sys.modules.get("chainlit")
    original_chainlit_server = sys.modules.get("chainlit.server")

    with tempfile.TemporaryDirectory(prefix="chainlit_app_root_") as temp_dir:
        with pytest.raises(RuntimeError):
            _load_socket_module(Path(temp_dir), monkeypatch)

    assert sys.modules.get("chainlit.server") is original_chainlit_server
    assert sys.modules.get("chainlit") is original_chainlit
