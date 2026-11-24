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

    async def test_fast_job_logs_are_available_to_a_late_stream_subscriber(self) -> None:
        job_id = job_manager.create_job()
        await asyncio.to_thread(
            job_manager.run_in_job,
            job_id,
            lambda: print("fast job output"),
        )
        # Allow the queued terminal callback to run before opening the SSE stream.
        await asyncio.sleep(0)

        self.assertIn(job_id, job_manager._jobs)
        messages = await self._collect(job_id)

        self.assertEqual(messages, ["fast job output", "[DONE]"])
        self.assertNotIn(job_id, job_manager._jobs)

    async def test_completed_job_log_cache_is_bounded(self) -> None:
        previous_limit = job_manager._MAX_RETAINED_COMPLETED_LOGS
        job_manager._MAX_RETAINED_COMPLETED_LOGS = 2
        job_ids = []
        try:
            for _ in range(3):
                job_id = job_manager.create_job()
                job_ids.append(job_id)
                await asyncio.to_thread(job_manager.run_in_job, job_id, lambda: None)
                await asyncio.sleep(0)
        finally:
            job_manager._MAX_RETAINED_COMPLETED_LOGS = previous_limit

        self.assertNotIn(job_ids[0], job_manager._jobs)
        self.assertIn(job_ids[1], job_manager._jobs)
        self.assertIn(job_ids[2], job_manager._jobs)
        # Drain retained queues to avoid cross-test state.
        await self._collect(job_ids[1])
        await self._collect(job_ids[2])

    async def test_base_exception_is_not_reported_as_success(self) -> None:
        class FatalJobError(BaseException):
            pass

        job_id = job_manager.create_job()

        def fail() -> None:
            raise FatalJobError("fatal worker failure")

        with self.assertRaisesRegex(FatalJobError, "fatal worker failure"):
            await asyncio.to_thread(job_manager.run_in_job, job_id, fail)

        await asyncio.sleep(0)
        messages = await self._collect(job_id)
        self.assertTrue(any("fatal worker failure" in message for message in messages))
        self.assertEqual(messages[-1], "[FAILED]")
        self.assertNotIn("[DONE]", messages)

    async def test_unknown_job_emits_failure_instead_of_hanging(self) -> None:
        messages = await self._collect("missing-job-id")

        self.assertEqual(messages[-1], "[FAILED]")
        self.assertIn("Job not found", messages[0])


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
        # Check the stream after finalization to cover a late browser connection.
        await asyncio.sleep(0)
        messages = await self._collect(job_id)

        self.assertTrue(any("expected test failure" in message for message in messages))
        self.assertEqual(messages[-1], "[FAILED]")
        self.assertNotIn("[DONE]", messages)
        self.assertNotIn(job_id, job_manager._jobs)
        self.assertEqual(await self._collect(job_id), ["[FAILED]"])


if __name__ == "__main__":
    unittest.main()
