import json
import shlex
import subprocess
from pathlib import Path

from ollama import chat


MODEL = "qwen3:4b"

WORKSPACE = Path(
    "/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph"
).resolve()

MAX_STEPS = 20
COMMAND_TIMEOUT = 7200
MAX_OUTPUT = 16000


# ============================================================
# SAFETY
# ============================================================

FORBIDDEN_COMMANDS = [
    "sudo ",
    "rm -rf",
    "rm -fr",
    "shutdown",
    "reboot",
    "halt",
    "mkfs",
    "diskutil erase",
    "diskutil partition",
    "dd if=",
    "git reset --hard",
    "git clean -f",
    "git clean -fd",
    "git checkout -- .",
    "git restore .",
    "git push --force",
    "git push -f",
]


def safe_path(path: str) -> Path:
    """Resolve a path and guarantee that it is inside WORKSPACE."""
    p = (WORKSPACE / path).resolve()

    if p != WORKSPACE and WORKSPACE not in p.parents:
        raise ValueError(
            f"Path outside workspace is forbidden: {path}"
        )

    return p


# ============================================================
# TOOLS
# ============================================================

def read_file(path: str) -> str:
    """Read a UTF-8 text file from the project.

    Args:
        path: Path relative to the project root.

    Returns:
        File contents.
    """
    p = safe_path(path)

    if not p.exists():
        return f"ERROR: file does not exist: {path}"

    if not p.is_file():
        return f"ERROR: not a file: {path}"

    return p.read_text(
        encoding="utf-8",
        errors="replace",
    )[:MAX_OUTPUT]


def write_file(path: str, content: str) -> str:
    """Write complete UTF-8 contents to a project file.

    Args:
        path: Path relative to project root.
        content: Complete new contents of the file.

    Returns:
        Result of the operation.
    """
    p = safe_path(path)

    p.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existed = p.exists()

    p.write_text(
        content,
        encoding="utf-8",
    )

    action = "updated" if existed else "created"

    return f"OK: {action} {path}"


def list_directory(path: str = ".") -> str:
    """List files and directories.

    Args:
        path: Directory relative to project root.

    Returns:
        Directory listing.
    """
    p = safe_path(path)

    if not p.exists():
        return f"ERROR: directory does not exist: {path}"

    if not p.is_dir():
        return f"ERROR: not a directory: {path}"

    items = []

    for item in sorted(
        p.iterdir(),
        key=lambda x: (
            not x.is_dir(),
            x.name.lower(),
        ),
    ):
        kind = "DIR " if item.is_dir() else "FILE"
        items.append(
            f"{kind} {item.relative_to(WORKSPACE)}"
        )

    return "\n".join(items)[:MAX_OUTPUT]


def run_command(command: str) -> str:
    """Run a shell command inside the project directory.

    Use this for git, PlatformIO, npm, python, tests and other
    project-related commands.

    Args:
        command: Shell command to execute.

    Returns:
        Exit code and combined stdout/stderr.
    """
    lower = command.lower()

    for forbidden in FORBIDDEN_COMMANDS:
        if forbidden in lower:
            return (
                "BLOCKED: dangerous command: "
                + command
            )

    try:
        result = subprocess.run(
            command,
            cwd=WORKSPACE,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=COMMAND_TIMEOUT,
            env=None,
        )

        output = result.stdout or ""

        if len(output) > MAX_OUTPUT:
            output = (
                "... output truncated ...\n"
                + output[-MAX_OUTPUT:]
            )

        return (
            f"exit={result.returncode}\n"
            f"{output}"
        )

    except subprocess.TimeoutExpired as exc:
        output = ""

        if exc.stdout:
            if isinstance(exc.stdout, bytes):
                output = exc.stdout.decode(
                    errors="replace"
                )
            else:
                output = exc.stdout

        return (
            f"ERROR: timeout after "
            f"{COMMAND_TIMEOUT}s\n"
            f"{output[-4000:]}"
        )


def git_status() -> str:
    """Return the current Git branch and working tree status."""
    return run_command(
        "git branch --show-current && "
        "git status --short"
    )


def git_diff() -> str:
    """Return the current unstaged and staged Git diff."""
    return run_command(
        "git diff && "
        "git diff --cached"
    )


def search_files(query: str) -> str:
    """Search text recursively inside project files.

    Args:
        query: Literal text to search for.

    Returns:
        Matching file names and lines.
    """
    escaped = shlex.quote(query)

    command = (
        "grep -RIn "
        "--exclude-dir=.git "
        "--exclude-dir=.pio "
        "--exclude-dir=node_modules "
        "--exclude-dir=build "
        f"-- {escaped} . "
        "| head -n 200"
    )

    return run_command(command)


TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff,
    "search_files": search_files,
}


# ============================================================
# AGENT PROMPT
# ============================================================

SYSTEM = """
You are a LOCAL EXECUTION AGENT.

Another AI is the main programmer.
You are the local hands of that programmer.

Your job is to EXECUTE tasks on the local project.

You have tools for:
- reading files
- writing files
- listing directories
- searching source code
- running shell commands
- checking Git status
- checking Git diff

IMPORTANT RULES:

1. NEVER invent command output.
2. NEVER invent files or directories.
3. NEVER claim a test passed unless you actually ran it.
4. NEVER claim a file was changed unless write_file changed it.
5. Inspect relevant files before modifying them.
6. Work only inside the configured project.
7. Never use sudo.
8. Never perform destructive Git operations.
9. Never delete large directories.
10. If a command fails, inspect the actual error.
11. You may make reasonable execution/environment fixes.
12. Do not redesign the requested feature unless explicitly asked.
13. After modifying source code, inspect git_diff.
14. If the task requests tests, actually execute them.
15. Do not repeat a tool call that already produced the needed result.
16. Once the requested work is complete, STOP calling tools.

Shell programs such as:
git
pio
npm
node
python
grep
find
ls
pwd

must be executed using run_command.

You are an executor, not the primary software architect.
"""


# ============================================================
# AGENT ENGINE
# ============================================================

def call_signature(name: str, args: dict) -> str:
    return json.dumps(
        {
            "name": name,
            "args": args,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def execute_tool(
    name: str,
    args: dict,
) -> str:

    print(
        f"\n>>> {name}("
        f"{json.dumps(args, ensure_ascii=False)})"
    )

    function = TOOLS.get(name)

    if function is None:
        result = (
            f"ERROR: unknown tool '{name}'. "
            "Use run_command for shell commands."
        )

    else:
        try:
            result = function(**args)
        except Exception as exc:
            result = (
                f"ERROR: {type(exc).__name__}: "
                f"{exc}"
            )

    print(result[:5000])

    if len(result) > 5000:
        print("\n[terminal display truncated]")

    return result


def print_execution_report(history):
    print("\n")
    print("=" * 60)
    print("EXECUTION REPORT")
    print("=" * 60)

    if not history:
        print("No tools were executed.")
        print("=" * 60)
        return

    for number, item in enumerate(
        history,
        start=1,
    ):
        print(
            f"\n[{number}] "
            f"{item['name']}"
        )

        if item["args"]:
            print(
                json.dumps(
                    item["args"],
                    indent=2,
                    ensure_ascii=False,
                )
            )

        print(item["result"])

    print("\n" + "=" * 60)
    print("END")
    print("=" * 60)


def execute(prompt: str):

    messages = [
        {
            "role": "system",
            "content": SYSTEM,
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    executed = set()
    history = []

    for step in range(
        1,
        MAX_STEPS + 1,
    ):

        response = chat(
            model=MODEL,
            messages=messages,
            tools=list(TOOLS.values()),
            think=False,
            options={
                "temperature": 0,
            },
        )

        messages.append(
            response.message
        )

        calls = (
            response.message.tool_calls
            or []
        )

        # Model finished normally.
        if not calls:

            content = (
                response.message.content
                or ""
            ).strip()

            if content:
                print("\nAGENT:\n")
                print(content)

            print_execution_report(
                history
            )
            return

        new_call_found = False

        for call in calls:

            name = call.function.name
            args = (
                call.function.arguments
                or {}
            )

            sig = call_signature(
                name,
                args,
            )

            if sig in executed:
                print(
                    "\n[duplicate tool call ignored]"
                )
                continue

            new_call_found = True
            executed.add(sig)

            result = execute_tool(
                name,
                args,
            )

            history.append(
                {
                    "name": name,
                    "args": args,
                    "result": result,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": result,
                }
            )

        # Qwen entered a loop.
        if not new_call_found:
            print(
                "\n[agent attempted only "
                "duplicate calls - stopping]"
            )

            print_execution_report(
                history
            )
            return

    print(
        "\n[maximum agent steps reached]"
    )

    print_execution_report(
        history
    )


# ============================================================
# INTERACTIVE LOOP
# ============================================================

print()
print("Local Agent")
print(f"Model:     {MODEL}")
print(f"Workspace: {WORKSPACE}")
print("Type 'quit' to exit.")
print()


while True:
    try:
        prompt = input("TASK> ").strip()

        if prompt.lower() in {
            "quit",
            "exit",
        }:
            break

        if not prompt:
            continue

        execute(prompt)

    except KeyboardInterrupt:
        print("\n")
        break
