import json
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO


def extract_code(user_input: str) -> str | None:
    user_input = user_input.strip()
    if "```" not in user_input:
        return None
    sections = user_input.split("```python")
    if len(sections) < 2:
        sections = user_input.split("```")
        if len(sections) < 2:
            return None
        code_block = sections[1]
    else:
        code_block = sections[1]
    code = code_block.split("```")[0]
    return code.strip() or None


def run_code(code: str) -> dict:
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    local_vars: dict = {}
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, {}, local_vars)
        return {
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
            "locals": local_vars,
        }
    except Exception as exc:  # pragma: no cover - sandboxed execution
        return {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
        }


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "payload missing"}))
        return
    payload = json.loads(sys.argv[-1])
    user_input = payload.get("input", "")
    code = payload.get("code")
    if not code:
        code = extract_code(user_input)
    if not code:
        print(json.dumps({"info": "No Python code block detected."}, ensure_ascii=False))
        return
    result = run_code(code)
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
