import asyncio
import sys
import uuid
from collections import OrderedDict
from typing import AsyncGenerator, Dict

_jobs: Dict[str, asyncio.Queue[str]] = {}
_job_states: OrderedDict[str, str] = OrderedDict()
_MAX_RETAINED_JOB_STATES = 500
_loop: asyncio.AbstractEventLoop | None = None

_DONE = "__DONE__"


def register_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = asyncio.Queue()
    _job_states[job_id] = "running"
    return job_id


def _put(job_id: str, msg: str) -> None:
    if _loop and job_id in _jobs:
        asyncio.run_coroutine_threadsafe(_jobs[job_id].put(msg), _loop)


class JobWriter:
    """Captures print() output from pipeline threads and routes it to an async queue."""

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id
        self._buf = ""

    def write(self, text: str) -> None:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                _put(self._job_id, line)

    def flush(self) -> None:
        if self._buf.strip():
            _put(self._job_id, self._buf)
            self._buf = ""


def run_in_job(job_id: str, fn: object) -> None:
    """Run fn() in the current thread, capturing stdout → job queue."""
    writer = JobWriter(job_id)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = writer  # type: ignore[assignment]
    sys.stderr = writer  # type: ignore[assignment]
    failed = False
    try:
        fn()  # type: ignore[operator]
    except Exception as exc:
        failed = True
        writer.write(f"❌ Error: {type(exc).__name__}: {exc}\n")
    finally:
        writer.flush()
        sys.stdout = old_out
        sys.stderr = old_err
        _job_states[job_id] = "failed" if failed else "completed"
        _job_states.move_to_end(job_id)
        while len(_job_states) > _MAX_RETAINED_JOB_STATES:
            _job_states.popitem(last=False)
        _put(job_id, "__FAILED__" if failed else _DONE)


async def stream_job(job_id: str) -> AsyncGenerator[str, None]:
    q = _jobs.get(job_id)
    if q is None:
        # A client may reconnect after the terminal event was consumed.
        # Retain a bounded terminal status so it can still learn the outcome.
        state = _job_states.get(job_id)
        if state == "completed":
            yield "[DONE]"
        elif state == "failed":
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
        if msg == _DONE:
            yield "[DONE]"
            _jobs.pop(job_id, None)
            return
        if msg == "__FAILED__":
            yield "[FAILED]"
            _jobs.pop(job_id, None)
            return
        yield msg
