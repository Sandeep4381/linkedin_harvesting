"""Exercise orchestration without browser, database or AI dependencies."""
import ast
import asyncio
from pathlib import Path
import unittest


class ResumePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_resume_prepares_during_upload_and_queue_drains(self):
        source = Path(__file__).resolve().parents[1] / "recruit_manual.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == "process_candidate_profiles")
        started = asyncio.Event()
        next_ready = asyncio.Event()
        profiles = {}
        order = []
        active = 0

        async def prepare(api, args, profile_page, applicant_page, job,
                          urls, rows, persist, ready):
            rows["first"] = {"url": "first", "status": "resume_ready"}
            await ready.put(rows["first"])
            await asyncio.wait_for(started.wait(), 1)
            self.assertEqual(rows["first"]["status"], "resume_ready")
            rows["second"] = {"url": "second", "status": "resume_ready"}
            await ready.put(rows["second"])
            next_ready.set()

        async def upload(page, row, api, persist, code):
            nonlocal active
            active += 1
            self.assertEqual(active, 1)
            if row["url"] == "first":
                started.set()
                await asyncio.wait_for(next_ready.wait(), 1)
                active -= 1
                raise RuntimeError("upload failed")
            order.append(row["url"])
            row["status"] = "saved"
            active -= 1

        def skip(api, row, exc, persist):
            row["status"] = "skipped_processing_failed"

        namespace = dict(asyncio=asyncio, prepare_candidate_profiles=prepare,
                         create_applicant=upload, skip_failed_profile=skip,
                         FINAL={"saved", "skipped_processing_failed"})
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        result = await asyncio.wait_for(namespace["process_candidate_profiles"](
            None, None, None, None, {"code": "job"},
            ["first", "second"], profiles, lambda: None), 2)
        self.assertTrue(result)
        self.assertEqual(order, ["second"])
        self.assertEqual(profiles["first"]["status"], "skipped_processing_failed")


if __name__ == "__main__":
    unittest.main()
