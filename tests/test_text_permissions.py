import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import sunday


class PermissionTests(unittest.TestCase):
    def test_permission_fails_closed_when_terminal_input_is_unavailable(self):
        with patch.object(sunday, "TERMINAL_INPUT_READY") as ready:
            ready.is_set.return_value = False
            self.assertFalse(sunday.request_permission("test action"))

    def test_terminal_reader_routes_confirmation_to_pending_permission(self):
        response = {"approved": False}
        completed = sunday.threading.Event()
        with (
            patch.object(sunday, "PENDING_PERMISSION", (response, completed)),
            patch("builtins.input", side_effect=["yes", EOFError]),
        ):
            sunday._terminal_input_loop()

        self.assertTrue(response["approved"])
        self.assertTrue(completed.is_set())
        self.assertIsNone(sunday.PENDING_PERMISSION)

    def test_voice_permission_reply_resolves_pending_action(self):
        response = {"approved": False}
        completed = sunday.threading.Event()
        with patch.object(sunday, "PENDING_PERMISSION", (response, completed)):
            self.assertTrue(sunday._resolve_pending_permission(
                sunday._permission_answer("Haan")
            ))

        self.assertTrue(response["approved"])
        self.assertTrue(completed.is_set())
        self.assertIsNone(sunday.PENDING_PERMISSION)

    def test_permission_is_asked_and_answer_is_spoken(self):
        def answer_by_voice(completed, timeout):
            self.assertEqual(timeout, 120)
            self.assertFalse(completed.is_set())
            self.assertFalse(sunday.PENDING_PERMISSION[0]["approved"])
            sunday._resolve_pending_permission(True)

        with (
            patch.object(sunday, "TERMINAL_INPUT_READY") as terminal_ready,
            patch.object(sunday, "VOICE_PERMISSION_READY") as voice_ready,
            patch.object(sunday, "speak") as speak,
            patch.object(sunday, "_listen_for_permission_voice", side_effect=answer_by_voice),
        ):
            terminal_ready.is_set.return_value = False
            voice_ready.is_set.return_value = True
            approved = sunday.request_permission("PC ko lock karna")

        self.assertTrue(approved)
        self.assertEqual(speak.call_count, 2)
        self.assertIn("permission dete hain", speak.call_args_list[0].args[0])
        self.assertIn("Permission mil gayi", speak.call_args_list[1].args[0])

    def test_voice_listener_accepts_spoken_yes(self):
        response = {"approved": False}
        completed = sunday.threading.Event()
        recognizer = MagicMock()
        recognizer.listen.return_value = object()
        recognizer.recognize_google.return_value = "haan"
        microphone = MagicMock()
        microphone.__enter__.return_value = object()

        with (
            patch.object(sunday, "PENDING_PERMISSION", (response, completed)),
            patch.object(sunday.sr, "Recognizer", return_value=recognizer),
            patch.object(sunday.sr, "Microphone", return_value=microphone),
        ):
            sunday._listen_for_permission_voice(completed, timeout=5)

        self.assertTrue(response["approved"])
        self.assertTrue(completed.is_set())

    def test_shutdown_is_not_scheduled_when_permission_is_denied(self):
        with (
            patch.object(sunday, "request_permission", return_value=False),
            patch.object(sunday.subprocess, "run") as run,
        ):
            result = sunday.system_shutdown(15)

        self.assertIn("permission nahi mili", result)
        run.assert_not_called()

    def test_delete_does_not_remove_file_when_permission_is_denied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "keep.txt"
            target.write_text("important", encoding="utf-8")
            with (
                patch.object(sunday, "_resolve_user_path", return_value=target),
                patch.object(sunday, "request_permission", return_value=False),
            ):
                result = sunday.file_delete("keep.txt")

            self.assertIn("permission nahi mili", result)
            self.assertTrue(target.exists())

    def test_text_commands_bypass_voice_keyword_filter(self):
        with (
            patch.object(sunday, "is_system_noise", return_value=False),
            patch.object(sunday, "is_command_like", return_value=False),
            patch.object(sunday, "speak") as speak,
            patch.object(sunday, "API_KEYS", []),
        ):
            sunday.process_command("tell me something", from_text=True)

        speak.assert_called_once_with("I didn't understand that")

    def test_voice_commands_keep_existing_keyword_filter(self):
        with (
            patch.object(sunday, "is_system_noise", return_value=False),
            patch.object(sunday, "is_command_like", return_value=False),
            patch.object(sunday, "speak") as speak,
        ):
            sunday.process_command("tell me something")

        speak.assert_not_called()

    def test_cursor_move_does_not_prompt_and_uses_coordinates(self):
        with (
            patch.object(sunday.pyautogui, "size", return_value=(1920, 1080)),
            patch.object(sunday, "request_permission") as permission,
            patch.object(sunday.pyautogui, "moveTo") as move_to,
        ):
            result = sunday.handle_screen_command(
                "cursor ko 500 300 par le jao",
                "cursor ko 500 300 par le jao",
            )

        self.assertIn("move kar diya", result)
        permission.assert_not_called()
        move_to.assert_called_once_with(500, 300, duration=0.25)

    def test_cursor_move_refuses_out_of_screen_coordinates(self):
        with (
            patch.object(sunday.pyautogui, "size", return_value=(1920, 1080)),
            patch.object(sunday, "request_permission") as permission,
            patch.object(sunday.pyautogui, "moveTo") as move_to,
        ):
            result = sunday.handle_screen_command(
                "move cursor to 1920 300",
                "move cursor to 1920 300",
            )

        self.assertIn("screen ke bahar", result)
        permission.assert_not_called()
        move_to.assert_not_called()

    def test_typing_preserves_case_without_popup(self):
        with (
            patch.object(sunday.pyautogui, "write") as write,
            patch.object(sunday.time, "sleep") as sleep,
        ):
            result = sunday.handle_screen_command(
                "type karo Hello Faraway!",
                "type karo hello faraway!",
            )

        self.assertIn("type kar diye", result)
        sleep.assert_called_once_with(3)
        write.assert_called_once_with("Hello Faraway!", interval=0.01)

    def test_click_at_current_cursor_does_not_prompt(self):
        with (
            patch.object(sunday, "request_permission") as permission,
            patch.object(sunday.pyautogui, "click") as click,
        ):
            result = sunday.handle_screen_command("right click", "right click")

        self.assertIn("Right Click", result)
        permission.assert_not_called()
        click.assert_called_once_with(button="right", clicks=1, interval=0.1)

    def test_open_and_close_apps_do_not_prompt(self):
        with (
            patch.object(sunday, "request_permission") as permission,
            patch.object(sunday.subprocess, "Popen") as popen,
        ):
            result = sunday.open_app_smart("calculator")

        self.assertIn("Opening calculator", result)
        popen.assert_called_once()
        permission.assert_not_called()

        with (
            patch.object(sunday, "request_permission") as permission,
            patch.object(sunday.psutil, "process_iter", return_value=[]),
        ):
            result = sunday.close_app("calculator")

        self.assertIn("not running", result)
        permission.assert_not_called()

    def test_open_terminal_uses_existing_console(self):
        self.assertIn("isi terminal", sunday.handle_terminal_command("open terminal"))

    def test_terminal_runner_rejects_shell_operators(self):
        result = sunday._run_terminal_command("python --version & whoami")
        self.assertIn("shell operators", result)

    def test_terminal_runner_requires_approval_for_execution(self):
        with (
            patch.object(sunday, "request_permission", return_value=False) as permission,
            patch.object(sunday.subprocess, "run") as run,
        ):
            result = sunday._run_terminal_command("python --version")

        self.assertIn("permission nahi mili", result)
        permission.assert_called_once()
        run.assert_not_called()

    def test_terminal_input_routes_commands_to_command_queue(self):
        with (
            patch("builtins.input", side_effect=["tell me something", EOFError]),
            patch.object(sunday, "TERMINAL_INPUT_READY"),
            patch.object(sunday, "PENDING_PERMISSION", None),
        ):
            sunday._terminal_input_loop()

        self.assertEqual(sunday.TEXT_COMMAND_QUEUE.get_nowait(), "tell me something")
        sunday.TEXT_COMMAND_QUEUE.task_done()

    def test_terminal_runner_runs_python_with_argument_list_after_approval(self):
        expected = type("Completed", (), {"stdout": "Python test", "stderr": "", "returncode": 0})()
        with (
            patch.object(sunday, "request_permission", return_value=True),
            patch.object(sunday.subprocess, "run", return_value=expected) as run,
        ):
            result = sunday._run_terminal_command("python --version")

        self.assertIn("Python test", result)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.args[0], [sunday.sys.executable, "--version"])
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_terminal_runner_rejects_scripts_outside_project(self):
        with patch.object(sunday, "request_permission") as permission:
            result = sunday._run_terminal_command("python ..\\outside.py")

        self.assertIn("project folder", result)
        permission.assert_not_called()

    def test_gemini_errors_are_not_printed_raw(self):
        output = StringIO()
        with (
            patch.object(sunday, "API_KEYS", ["key-one"]),
            patch.object(sunday, "EXHAUSTED_KEYS", set()),
            patch.object(sunday, "API_KEY_CURSOR", 0),
            patch.object(sunday, "hud", None),
            patch.object(
                sunday,
                "_create_gemini_client",
                return_value=type(
                    "Client",
                    (),
                    {
                        "models": type(
                            "Models",
                            (),
                            {
                                "generate_content": staticmethod(
                                    lambda **kwargs: (
                                        None
                                        if not kwargs
                                        else (_ for _ in ()).throw(
                                            RuntimeError("provider secret diagnostic")
                                        )
                                    )
                                )
                            },
                        )()
                    },
                )(),
            ),
            patch.object(sunday.time, "sleep"),
            redirect_stdout(output),
        ):
            self.assertIsNone(sunday._call_gemini("prompt", max_attempts_per_key=1))

        self.assertNotIn("provider secret diagnostic", output.getvalue())
        self.assertIn("Request failed", output.getvalue())


class ApiKeyRotationTests(unittest.TestCase):
    def test_loads_any_numbered_env_keys_in_order_without_duplicates(self):
        keys = sunday._load_api_keys({
            "GEMINI_API_KEY_12": "key-twelve",
            "GEMINI_API_KEY_2": "key-two",
            "GEMINI_API_KEY": "key-single",
            "GEMINI_API_KEY_5": "key-two",
            "OTHER_API_KEY": "ignored",
        })

        self.assertEqual(keys, ["key-two", "key-twelve", "key-single"])

    def test_quota_on_one_key_moves_to_next_key_and_advances_cursor(self):
        class Models:
            def __init__(self, should_throttle):
                self.should_throttle = should_throttle

            def generate_content(self, **kwargs):
                self.last_model = kwargs["model"]
                if self.should_throttle:
                    raise RuntimeError("429 quota exceeded")
                return type("Response", (), {"text": "answer"})()

        clients = {
            "key-one": type(
                "Client",
                (),
                {"models": Models(True)},
            )(),
            "key-two": type(
                "Client",
                (),
                {"models": Models(False)},
            )(),
            "key-three": type(
                "Client",
                (),
                {"models": Models(False)},
            )(),
        }

        exhausted_keys = set()
        with (
            patch.object(sunday, "API_KEYS", ["key-one", "key-two", "key-three"]),
            patch.object(sunday, "EXHAUSTED_KEYS", exhausted_keys),
            patch.object(sunday, "API_KEY_CURSOR", 0),
            patch.object(sunday, "hud", None),
            patch.object(
                sunday,
                "_create_gemini_client",
                side_effect=lambda api_key: clients[api_key],
            ) as create_client,
            patch.object(sunday.time, "sleep"),
        ):
            result = sunday._call_gemini("prompt", max_attempts_per_key=1)
            available = sunday._get_available_keys()

        self.assertEqual(result, "answer")
        self.assertEqual(
            [call.args[0] for call in create_client.call_args_list],
            ["key-one", "key-two"],
        )
        self.assertIn("key-one", exhausted_keys)
        self.assertEqual(available, ["key-three", "key-two"])

    def test_starts_a_new_cycle_after_every_key_is_exhausted(self):
        with (
            patch.object(sunday, "API_KEYS", ["key-one", "key-two"]),
            patch.object(sunday, "EXHAUSTED_KEYS", {"key-one", "key-two"}),
            patch.object(sunday, "API_KEY_CURSOR", 1),
        ):
            self.assertEqual(sunday._get_available_keys(), ["key-two", "key-one"])
            self.assertEqual(sunday.EXHAUSTED_KEYS, set())


if __name__ == "__main__":
    unittest.main()
