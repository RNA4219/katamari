import asyncio
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

        class _EmitterStub:
            def __init__(self) -> None:
                self.call_log: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
                self.audio_connections: list[str] = []
                self.processed_messages: list[object] = []

            def _record(
                self,
                name: str,
                args: tuple[object, ...] = (),
                kwargs: dict[str, object] | None = None,
            ) -> None:
                self.call_log.append((name, args, dict(kwargs or {})))

            async def task_start(self, *args: object, **kwargs: object) -> None:
                self._record("task_start", args, kwargs)

            async def task_end(self, *args: object, **kwargs: object) -> None:
                self._record("task_end", args, kwargs)

            async def init_thread(self, *args: object, **kwargs: object) -> None:
                self._record("init_thread", args, kwargs)

            async def update_audio_connection(self, state: str) -> None:
                self.audio_connections.append(state)
                self._record("update_audio_connection", (state,), {})

            async def process_message(self, payload: object) -> object:
                self.processed_messages.append(payload)
                self._record("process_message", (payload,), {})
                return payload

            async def clear(self, *args: object, **kwargs: object) -> None:
                self._record("clear", args, kwargs)

            async def emit(self, *args: object, **kwargs: object) -> None:
                self._record("emit", args, kwargs)

            async def resume_thread(self, *args: object, **kwargs: object) -> None:
                self._record("resume_thread", args, kwargs)

            async def send_resume_thread_error(self, *args: object, **kwargs: object) -> None:
                self._record("send_resume_thread_error", args, kwargs)

        class _ContextStub(SimpleNamespace):
            def __init__(self, session: SimpleNamespace | None = None) -> None:
                super().__init__(
                    emitter=_EmitterStub(),
                    session=session
                    or SimpleNamespace(
                        restored=False,
                        has_first_interaction=False,
                        current_task=None,
                        thread_id_to_resume=None,
                    ),
                )

        _context_store: dict[str, _ContextStub] = {}

        def _context_key(target: object) -> str:
            if isinstance(target, str):
                return target
            for attr in ("socket_id", "id"):
                value = getattr(target, attr, None)
                if isinstance(value, str) and value:
                    return value
            return str(id(target))

        def init_ws_context(session_or_sid: object) -> _ContextStub:
            key = _context_key(session_or_sid)
            context = _context_store.get(key)
            if context is None:
                context = _ContextStub()
                _context_store[key] = context
            if not isinstance(session_or_sid, str):
                context.session = session_or_sid
            return context

        stub_module(
            "chainlit.config",
            {
                "ChainlitConfig": object,
                "config": SimpleNamespace(
                    project=SimpleNamespace(user_env=[]),
                    code=SimpleNamespace(
                        on_audio_start=_noop_async,
                        on_audio_chunk=None,
                        on_audio_end=_noop_async,
                        on_window_message=None,
                        on_chat_start=None,
                        on_chat_resume=None,
                        on_message=None,
                        on_settings_update=None,
                        on_stop=None,
                    ),
                ),
            },
        )
        stub_module(
            "chainlit.context",
            {
                "init_ws_context": init_ws_context,
                "context_store": _context_store,
                "ContextStub": _ContextStub,
                "EmitterStub": _EmitterStub,
            },
        )
        stub_module("chainlit.data", {"get_data_layer": lambda: None})
        class _ErrorMessage:
            def __init__(self, **kwargs: object) -> None:
                self.payload = dict(kwargs)

            async def send(self) -> None:
                return None

        stub_module(
            "chainlit.message",
            {
                "ErrorMessage": _ErrorMessage,
                "Message": SimpleNamespace(from_dict=lambda data: data),
            },
        )

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
            _sessions: dict[str, "_WebsocketSession"] = {}
            _sessions_by_id: dict[str, "_WebsocketSession"] = {}

            @classmethod
            def get_by_id(cls, session_id):
                return cls._sessions_by_id.get(session_id)

            @classmethod
            def get(cls, socket_id):
                return cls._sessions.get(socket_id)

            @classmethod
            def require(cls, socket_id):
                session = cls.get(socket_id)
                if session is None:
                    raise KeyError(socket_id)
                return session

            def __init__(
                self,
                *,
                id=None,
                socket_id=None,
                emit=None,
                emit_call=None,
                client_type=None,
                user_env=None,
                user=None,
                token=None,
                chat_profile=None,
                thread_id=None,
                environ=None,
                **_: object,
            ) -> None:
                self.id = id or socket_id or "session"
                self.socket_id = socket_id or self.id
                self.emit = emit
                self.emit_call = emit_call
                self.client_type = client_type
                self.user_env = user_env
                self.user = user
                self.token = token
                self.chat_profile = chat_profile
                self.thread_id = thread_id
                self.environ = environ
                self.has_first_interaction = False
                self.current_task = None
                self.thread_id_to_resume = None
                self.chat_settings: dict[str, object] = {}
                self.to_clear = False
                self.restored = False
                self._config = SimpleNamespace(
                    features=SimpleNamespace(audio=SimpleNamespace(enabled=False)),
                    code=SimpleNamespace(
                        on_audio_start=_noop_async,
                        on_audio_chunk=None,
                        on_audio_end=_noop_async,
                        on_window_message=None,
                        on_chat_start=None,
                        on_chat_resume=None,
                        on_message=None,
                        on_settings_update=None,
                        on_stop=None,
                    ),
                )
                _WebsocketSession._sessions[self.socket_id] = self
                _WebsocketSession._sessions_by_id[self.id] = self

            def restore(self, **kwargs):
                self.restored = True
                for key, value in kwargs.items():
                    setattr(self, key, value)

            def get_config(self):
                return self._config

            async def delete(self) -> None:
                pass

            def to_persistable(self):
                return {}

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


def test_audio_end_uses_emitter_hooks(socket_module: ModuleType) -> None:
    session = socket_module.WebsocketSession(id="session-id", socket_id="sid")
    config = session.get_config()
    config.features.audio.enabled = True

    audio_end_calls: list[None] = []

    async def _on_audio_end() -> None:
        audio_end_calls.append(None)

    config.code.on_audio_end = _on_audio_end

    context = socket_module.init_ws_context(session)
    emitter = context.emitter

    async def _exercise() -> None:
        await socket_module.audio_end("sid")
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    method_names = [entry[0] for entry in emitter.call_log]

    assert method_names.count("task_start") == 1
    assert method_names.count("task_end") == 1
    assert method_names.index("task_start") < method_names.index("task_end")
    assert any(name == "init_thread" for name in method_names)
    assert session.has_first_interaction is True
    assert audio_end_calls


def test_audio_start_invokes_emitter_hooks(socket_module: ModuleType) -> None:
    session = socket_module.WebsocketSession(id="session-id", socket_id="sid")
    config = session.get_config()
    config.features.audio.enabled = True

    audio_start_calls: list[None] = []

    async def _on_audio_start() -> bool:
        audio_start_calls.append(None)
        return True

    config.code.on_audio_start = _on_audio_start

    context = socket_module.init_ws_context(session)
    emitter = context.emitter

    payload = {"message": {"content": "hello"}}

    async def _exercise() -> None:
        await socket_module.audio_start("sid")
        await socket_module.process_message(session, payload)

    asyncio.run(_exercise())

    assert audio_start_calls
    assert emitter.audio_connections == ["on"]
    assert emitter.processed_messages == [payload]

    method_names = [entry[0] for entry in emitter.call_log]

    assert method_names.count("update_audio_connection") == 1
    assert method_names.count("process_message") == 1


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
