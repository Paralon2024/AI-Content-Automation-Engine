import asyncio
import sys
import threading
import uuid
from collections import OrderedDict
from typing import AsyncGenerator, Dict, TextIO

_jobs: Dict[str, asyncio.Queue[str]] = {}
_job_states: OrderedDict[str, str] = OrderedDict()
_completed_jobs: OrderedDict[str, None] = OrderedDict()
_MAX_RETAINED_JOB_STATES = 500
_MAX_QUEUED_LOG_LINES = 1000
_MAX_RETAINED_COMPLETED_LOGS = 50
_loop: asyncio.AbstractEventLoop | None = None

_DONE = "__DONE__"
_job_states_lock = threading.Lock()
_stream_lock = threading.RLock()


class ThreadLocalStream:
    """Route writes from a job's thread to its writer; pass other threads through."""

    def __init__(self, fallback: TextIO) -> None:
        self._fallback = fallback
        self._local = threading.local()

    def _target(self) -> TextIO:
        return getattr(self._local, "target", self._fallback)

    def bind(self, target: TextIO) -> TextIO | None:
        previous = getattr(self._local, "target", None)
        self._local.target = target
        return previous

    def restore(self, previous: TextIO | None) -> None:
        if previous is None:
            if hasattr(self._local, "target"):
                del self._local.target
        else:
            self._local.target = previous

    def write(self, value: str) -> int:
        return self._target().write(value)

    def flush(self) -> None:
        self._target().flush()

    def __getattr__(self, name: str):
        target = self._target()
        try:
            return getattr(target, name)
        except AttributeError:
            return getattr(self._fallback, name)


_stdout_dispatcher: ThreadLocalStream | None = None
_stderr_dispatcher: ThreadLocalStream | None = None


def _ensure_stream_dispatchers() -> tuple[ThreadLocalStream, ThreadLocalStream]:
    """Install transparent process streams that route job output by thread."""
    global _stdout_dispatcher, _stderr_dispatcher

    with _stream_lock:
        if isinstance(sys.stdout, ThreadLocalStream):
            _stdout_dispatcher = sys.stdout
        else:
            _stdout_dispatcher = ThreadLocalStream(sys.stdout)
            sys.stdout = _stdout_dispatcher  # type: ignore[assignment]

        if isinstance(sys.stderr, ThreadLocalStream):
            _stderr_dispatcher = sys.stderr
        else:
            _stderr_dispatcher = ThreadLocalStream(sys.stderr)
            sys.stderr = _stderr_dispatcher  # type: ignore[assignment]

        return _stdout_dispatcher, _stderr_dispatcher


def register_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop
    _ensure_stream_dispatchers()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = asyncio.Queue(maxsize=_MAX_QUEUED_LOG_LINES)
    with _job_states_lock:
        _job_states[job_id] = "running"
    return job_id


def _put(job_id: str, msg: str) -> None:
    if not _loop:
        return

    def enqueue() -> None:
        q = _jobs.get(job_id)
        if q is None:
            return
        # A disconnected client must not allow unbounded memory growth.
        # Preserve the newest output and terminal marker when the queue is full.
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    try:
        _loop.call_soon_threadsafe(enqueue)
    except RuntimeError:
        # The application is shutting down and its event loop is already closed.
        return


class JobWriter:
    """Captures print() output from pipeline threads and routes it to an async queue."""

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                _put(self._job_id, line)
        return len(text)

    def flush(self) -> None:
        if self._buf.strip():
            _put(self._job_id, self._buf)
            self._buf = ""


def run_in_job(job_id: str, fn: object) -> None:
    """Run fn() while capturing only this worker thread's stdout and stderr."""
    stdout_stream, stderr_stream = _ensure_stream_dispatchers()
    writer = JobWriter(job_id)
    previous_out = stdout_stream.bind(writer)
    previous_err = stderr_stream.bind(writer)
    failed = False

    try:
        fn()  # type: ignore[operator]
    except Exception as exc:
        failed = True
        writer.write(f"❌ Error: {type(exc).__name__}: {exc}\n")
    except BaseException as exc:
        failed = True
        writer.write(f"❌ Error: {type(exc).__name__}: {exc}\n")
        raise
    finally:
        try:
            writer.flush()
        finally:
            stderr_stream.restore(previous_err)
            stdout_stream.restore(previous_out)

        with _job_states_lock:
            _job_states[job_id] = "failed" if failed else "completed"
            _job_states.move_to_end(job_id)
            while len(_job_states) > _MAX_RETAINED_JOB_STATES:
                _job_states.popitem(last=False)

        terminal = "__FAILED__" if failed else _DONE

        # Enqueue the terminal event and retain the bounded log queue until
        # the first stream subscriber consumes it or the completed-log cache evicts it.
        if _loop and _loop.is_running():
            def finalize() -> None:
                q = _jobs.get(job_id)
                if q is not None:
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    try:
                        q.put_nowait(terminal)
                    except asyncio.QueueFull:
                        pass

                    # Keep completed logs briefly so a fast job can finish before
                    # the browser opens its SSE connection. Eviction is bounded.
                    with _job_states_lock:
                        _completed_jobs[job_id] = None
                        _completed_jobs.move_to_end(job_id)
                        while len(_completed_jobs) > _MAX_RETAINED_COMPLETED_LOGS:
                            expired_job_id, _ = _completed_jobs.popitem(last=False)
                            _jobs.pop(expired_job_id, None)

            try:
                _loop.call_soon_threadsafe(finalize)
            except RuntimeError:
                # The event loop may already be closed during process shutdown.
                pass


async def stream_job(job_id: str) -> AsyncGenerator[str, None]:
    q = _jobs.get(job_id)
    if q is None:
        # A client may reconnect after the terminal event was consumed.
        # Retain a bounded terminal status so it can still learn the outcome.
        with _job_states_lock:
            state = _job_states.get(job_id)
        if state == "completed":
            yield "[DONE]"
        elif state == "failed":
            yield "[FAILED]"
        else:
            # Unknown IDs occur after a backend restart or bounded-cache eviction.
            # Emit a terminal failure so EventSource does not reconnect forever.
            yield "Job not found; the server may have restarted or its log history expired."
            yield "[FAILED]"
        return
    while True:
        try:
            msg = await asyncio.wait_for(q.get(), timeout=15)
        except asyncio.TimeoutError:
            # Keep long-running generation jobs alive. A heartbeat is an SSE
            # comment, so EventSource does not dispatch it as an application log.
            yield ": keep-alive"
            continue
        if msg == _DONE or msg == "__FAILED__":
            # The first stream to consume the terminal event releases the queue.
            # The terminal state remains available for later reconnects.
            if _jobs.get(job_id) is q:
                _jobs.pop(job_id, None)
            with _job_states_lock:
                _completed_jobs.pop(job_id, None)
            yield "[DONE]" if msg == _DONE else "[FAILED]"
            return
        yield msg
