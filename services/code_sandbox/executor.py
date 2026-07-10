import subprocess
import tempfile
import os
from dataclasses import dataclass


LANGUAGE_CONFIGS = {
    "python": {
        "ext": ".py",
        "cmd": lambda f: ["python", f],
        "timeout": 10,
    },
    "c": {
        "ext": ".c",
        "cmd": lambda f: None,  # two-step: compile then run
        "compile": lambda f, o: ["gcc", f, "-o", o, "-Wall"],
        "run": lambda o: [o],
        "timeout": 10,
    },
    "cpp": {
        "ext": ".cpp",
        "cmd": lambda f: None,
        "compile": lambda f, o: ["g++", f, "-o", o, "-std=c++17", "-Wall"],
        "run": lambda o: [o],
        "timeout": 10,
    },
    "java": {
        "ext": ".java",
        "cmd": lambda f: None,
        "compile": lambda f, _: ["javac", f],
        "run": lambda _: ["java", "Main"],
        "timeout": 15,
    },
    "javascript": {
        "ext": ".js",
        "cmd": lambda f: ["node", f],
        "timeout": 10,
    },
    "bash": {
        "ext": ".sh",
        "cmd": lambda f: ["bash", f],
        "timeout": 10,
    },
}


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float


def execute_code(language: str, source_code: str) -> ExecutionResult:
    """
    Execute code in a temporary directory.
    Returns ExecutionResult with stdout, stderr, and success flag.
    """
    import time

    config = LANGUAGE_CONFIGS.get(language.lower())
    if not config:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Language not supported: {language}",
            exit_code=1,
            execution_time_ms=0,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        ext = config["ext"]
        fname = "Main" + ext if language == "java" else "code" + ext
        fpath = os.path.join(tmpdir, fname)
        opath = os.path.join(tmpdir, "out")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(source_code)

        try:
            start = time.time()

            # compilation step (C, C++, Java)
            if "compile" in config:
                result = subprocess.run(
                    config["compile"](fpath, opath),
                    capture_output=True,
                    text=True,
                    timeout=config["timeout"],
                    cwd=tmpdir,
                )
                if result.returncode != 0:
                    return ExecutionResult(
                        success=False,
                        stdout="",
                        stderr=result.stderr,
                        exit_code=result.returncode,
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                run_cmd = config["run"](opath)
            else:
                run_cmd = config["cmd"](fpath)

            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=config["timeout"],
                cwd=tmpdir,
            )
            elapsed = (time.time() - start) * 1000

            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout[:2000],
                stderr=result.stderr[:1000],
                exit_code=result.returncode,
                execution_time_ms=elapsed,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Execution timed out.",
                exit_code=124,
                execution_time_ms=config["timeout"] * 1000,
            )
        except FileNotFoundError as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Compiler/runtime not found: {e}",
                exit_code=127,
                execution_time_ms=0,
            )
