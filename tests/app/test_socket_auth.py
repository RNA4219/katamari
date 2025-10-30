from collections.abc import Iterator
from contextlib import contextmanager
import os
import sys
import tempfile
from importlib import util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


pytestmark = pytest.mark.socket_module


def _load_socket_module(temp_root: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module_path = Path(__file__).resolve().parents[2]
    backend_root = module_path / "upstream" / "chainlit" / "backend"
    fake_config_dir = temp_root / ".chainlit"
    fake_config_dir.mkdir(parents=True, exist_ok=True)
    (fake_config_dir / "config.toml").write_text(
        """[meta]\ngenerated_by = \"0.3.1\"\n\n[project]\nuser_env = []\n\n[features]\n\n[UI]\nname = \"Test\"\n""",
        encoding="utf-8",
    )
    stubbed_modules: list[str] = []

    @contextmanager
    def preserve_environment() -> Iterator[None]:
        original_app_root = os.environ.get("CHAINLIT_APP_ROOT")
        original_syspath = list(sys.path)
        try:
            yield
        finally:
            if original_app_root is None:
                os.environ.pop("CHAINLIT_APP_ROOT", None)
            else:
                os.environ["CHAINLIT_APP_ROOT"] = original_app_root
            sys.path[:] = original_syspath

    with preserve_environment():
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
            stubbed_modules.append(name)
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

        try:
            module_path = backend_root / "chainlit" / "socket.py"
            spec = util.spec_from_file_location("chainlit_socket_module", module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Unable to load socket module for tests")
            module = util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return module
        finally:
            for name in reversed(stubbed_modules):
                monkeypatch.delitem(sys.modules, name, raising=False)
            monkeypatch.delitem(sys.modules, "chainlit", raising=False)


@pytest.fixture()
def socket_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    with tempfile.TemporaryDirectory(prefix="chainlit_app_root_") as temp_dir:
        module = _load_socket_module(Path(temp_dir), monkeypatch)
        yield module


@pytest.fixture()
def get_token(socket_module: ModuleType):
    return socket_module._get_token


def test_socket_loader_restores_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    temp_root = tmp_path / "chainlit-app"
    temp_root.mkdir()

    monkeypatch.setenv("CHAINLIT_APP_ROOT", "original-root")
    sentinel_path = tmp_path / "sentinel"
    sentinel_path.mkdir()
    monkeypatch.syspath_prepend(str(sentinel_path))
    baseline_syspath = list(sys.path)

    _load_socket_module(temp_root, monkeypatch)

    assert os.environ.get("CHAINLIT_APP_ROOT") == "original-root"
    assert sys.path == baseline_syspath


def test_socket_loader_restores_environment_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    temp_root = tmp_path / "chainlit-app"
    temp_root.mkdir()

    monkeypatch.delenv("CHAINLIT_APP_ROOT", raising=False)

    sentinel_path = tmp_path / "sentinel"
    sentinel_path.mkdir()
    monkeypatch.syspath_prepend(str(sentinel_path))

    baseline_env = dict(os.environ)
    baseline_syspath = list(sys.path)

    environ_type = type(os.environ)
    recorded_mutations: list[tuple[str, str | None]] = []

    original_setitem = environ_type.__setitem__
    original_delitem = environ_type.__delitem__

    def tracking_setitem(self, key: str, value: str) -> None:
        recorded_mutations.append(("set", key, value))
        original_setitem(self, key, value)

    def tracking_delitem(self, key: str) -> None:
        recorded_mutations.append(("del", key, None))
        original_delitem(self, key)

    monkeypatch.setattr(environ_type, "__setitem__", tracking_setitem)
    monkeypatch.setattr(environ_type, "__delitem__", tracking_delitem)

    with monkeypatch.context() as isolated_patch:
        _load_socket_module(temp_root, isolated_patch)

    assert os.environ == baseline_env
    assert sys.path == baseline_syspath
    assert recorded_mutations


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


def test_socket_loader_replaces_stubbed_chainlit_server(
    socket_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert "chainlit.server" not in sys.modules

    app_root = tmp_path / "chainlit-app"
    config_dir = app_root / ".chainlit"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """[meta]\ngenerated_by = \"0.3.1\"\n\n[project]\nuser_env = []\n\n[features]\n\n[UI]\nname = \"Test\"\n""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHAINLIT_APP_ROOT", str(app_root))

    backend_root = Path(__file__).resolve().parents[2] / "upstream" / "chainlit" / "backend"
    original_syspath = list(sys.path)
    try:
        sys.path.insert(0, str(backend_root))
        spec = util.find_spec("chainlit.server")
    finally:
        sys.path[:] = original_syspath

    assert spec is not None and spec.origin is not None
    assert Path(spec.origin).name == "server.py"
