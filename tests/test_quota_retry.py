import ast
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class QuotaRetryTests(unittest.TestCase):
    def helper(self, responses):
        path = Path(__file__).resolve().parents[1] / "azure_title.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_post_waiting_for_quota")
        post, sleep = Mock(side_effect=responses), Mock()
        namespace = dict(requests=SimpleNamespace(post=post),
                         time=SimpleNamespace(sleep=sleep), datetime=datetime,
                         timezone=timezone, parsedate_to_datetime=parsedate_to_datetime)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        return namespace[node.name], post, sleep

    def response(self, status, headers=None, text=""):
        return SimpleNamespace(status_code=status, headers=headers or {},
                               text=text, close=Mock())

    def test_quota_keeps_retrying_beyond_normal_retry_limit(self):
        success = self.response(200)
        call, post, sleep = self.helper([self.response(429) for _ in range(4)] + [success])
        payload = {"messages": []}
        self.assertIs(call("endpoint", json=payload), success)
        self.assertEqual(post.call_count, 5)
        self.assertEqual(sum(c.args[0] for c in sleep.call_args_list), 900)
        self.assertTrue(all(c.kwargs["json"] is payload for c in post.call_args_list))

    def test_retry_after_and_nonquota_errors(self):
        denied = self.response(401)
        call, post, sleep = self.helper([
            self.response(429, {"Retry-After": "2"}), denied])
        self.assertIs(call("endpoint"), denied)
        sleep.assert_called_once_with(2)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
