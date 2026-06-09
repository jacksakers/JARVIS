import os
import subprocess
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from skills.base_skill import BaseSkill


class SandboxInput(BaseModel):
    code: str = Field(
        description="The full, self-contained Python 3 source code to execute. Any outputs must be explicitly printed using print()."
    )
    filename: str = Field(
        default="scratchpad.py",
        description="The name of the temporary file to execute (e.g., 'test_algorithm.py'). Must end with '.py'."
    )


class PythonSandboxSkill(BaseSkill):
    name = "run_python_sandbox"
    description = (
        "Executes arbitrary Python code inside an isolated, local sandboxed environment. "
        "Returns the complete terminal output (stdout) and errors (stderr). "
        "Use this to test logic, build prototypes, or evaluate algorithms."
    )
    input_model = SandboxInput

    def execute(self, params: SandboxInput) -> str:
        # 1. Establish and enforce the sandbox directory boundary
        sandbox_dir = (Path.cwd() / "sandbox").resolve()
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # 2. Prevent path traversal attacks
        if not params.filename.endswith(".py"):
            return "Security Error: The target filename must end with a '.py' extension."

        target_path = (sandbox_dir / params.filename).resolve()
        if not target_path.is_relative_to(sandbox_dir):
            return "Security Error: Directory traversal detected. Execution blocked."

        # 3. Guardrails: Blocklist highly dangerous system manipulation keywords
        # This acts as a basic safety blanket on the host system
        dangerous_terms = [
            "os.system", "subprocess.Popen", "shutil.rmtree", "os.remove", 
            "os.rmdir", "os.unlink", "chmod", "os.kill"
        ]
        for term in dangerous_terms:
            if term in params.code:
                return f"Security Error: Code execution aborted. Found restricted keyword: '{term}'."

        try:
            # 4. Write the payload code into the sandbox directory
            target_path.write_text(params.code, encoding="utf-8")

            # 5. Execute the script using the current Python interpreter executable
            # Sets 'cwd' to sandbox_dir so relative file creation stays isolated
            result = subprocess.run(
                [sys.executable, str(target_path)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=10  # Hard timeout limit to catch accidental `while True:` loops
            )

            # 6. Parse and format terminal response streams
            output_segments = []
            if result.stdout:
                output_segments.append(f"--- TERMINAL OUTPUT (stdout) ---\n{result.stdout}")
            if result.stderr:
                output_segments.append(f"--- RUNTIME ERRORS (stderr) ---\n{result.stderr}")

            if not output_segments:
                return "Execution complete: Code finished successfully with an exit code of 0, but returned no stdout or stderr."

            return "\n\n".join(output_segments)

        except subprocess.TimeoutExpired:
            return "Execution Error: Process timed out. The code exceeded the maximum allowable execution window (10 seconds)."
        except Exception as exc:
            return f"Sandbox Execution Failed: {str(exc)}"
        finally:
            # Cleanup: Automatically shred the execution file after it completes or crashes
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass