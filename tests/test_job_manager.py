import asyncio
import io
import threading
import unittest

from api import job_manager


class JobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        job_manager.register_loop(asyncio.get_running_loop())

    async def _collect(self, job_id: str) -> list[str]:
        return [message async for message in job_manager.stream_job(job_id)]

    async def test_concurrent_jobs_capture_only_their_own_output(self) -> None:
        first_job = job_manager.create_job()
        second_job = job_manager.create_job()
        barrier = threading.Barrier(2)

        def emit(label: str) -> None:
            print(f"{label}: start")
            barrier.wait(timeout=5)
            print(f"{label}: end")

        first_stream = asyncio.create_task(self._collect(first_job))
        second_stream = asyncio.create_task(self._collect(second_job))
        # Let both stream generators obtain their queues before the workers finish.
        await asyncio.sleep(0)

        await asyncio.gather(
            asyncio.to_thread(job_manager.run_in_job, first_job, lambda: emit("first")),
            asyncio.to_thread(job_manager.run_in_job, second_job, lambda: emit("second")),
        )
        first_messages, second_messages = await asyncio.gather(first_stream, second_stream)

        self.assertEqual(first_messages, ["first: start", "first: end", "[DONE]"])
        self.assertEqual(second_messages, ["second: start", "second: end", "[DONE]"])

    async def test_unbound_thread_local_stream_uses_fallback(self) -> None:
        fallback = io.StringIO()
        captured = io.StringIO()
        stream = job_manager.ThreadLocalStream(fallback)
        previous = stream.bind(captured)
        try:
            stream.write("job output")
            outside_thread = threading.Thread(target=lambda: stream.write("outside output"))
            outside_thread.start()
            outside_thread.join(timeout=5)
            self.assertFalse(outside_thread.is_alive())
        finally:
            stream.restore(previous)

        self.assertEqual(captured.getvalue(), "job output")
        self.assertEqual(fallback.getvalue(), "outside output")

    async def test_successful_job_emits_done(self) -> None:
        job_id = job_manager.create_job()
        await asyncio.to_thread(job_manager.run_in_job, job_id, lambda: None)

        self.assertEqual(await self._collect(job_id), ["[DONE]"])
        self.assertNotIn(job_id, job_manager._jobs)
        # A reconnect after the queue is cleaned still sees the final state.
        self.assertEqual(await self._collect(job_id), ["[DONE]"])

    async def test_failed_job_is_not_reported_as_success(self) -> None:
        job_id = job_manager.create_job()

        def fail() -> None:
            raise ValueError("expected test failure")

        await asyncio.to_thread(job_manager.run_in_job, job_id, fail)
        messages = await self._collect(job_id)

        self.assertTrue(any("expected test failure" in message for message in messages))
        self.assertEqual(messages[-1], "[FAILED]")
        self.assertNotIn("[DONE]", messages)
        self.assertNotIn(job_id, job_manager._jobs)
        self.assertEqual(await self._collect(job_id), ["[FAILED]"])


if __name__ == "__main__":
    unittest.main()
