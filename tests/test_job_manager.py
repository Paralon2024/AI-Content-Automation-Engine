import asyncio
import unittest

from api import job_manager


class JobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        job_manager.register_loop(asyncio.get_running_loop())

    async def _collect(self, job_id: str) -> list[str]:
        return [message async for message in job_manager.stream_job(job_id)]

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
