"""Security operations."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend


def hash_password(backend: ContaoBackend, password: str, algorithm: str = "auto") -> dict:
    """
    Hash a password with Symfony's own hasher.

    Audit 2026-09-02 (H-3/M-10). This used to build
    `echo <password> | php bin/console …` and hand that string to `run_raw()`.
    `shlex.quote` made it safe against the shell *interpreting* the value — it did
    nothing about the value being *visible*: the whole string is an argument of
    the local ssh process, readable by every other user of this machine.

    The password goes down the pipe now instead of into the command line. Note
    that `--no-interaction` had to go with it: it is what suppressed the prompt
    that reads stdin.

    The leading blank line answers a prompt that comes *before* the password:
    Symfony asks which user class to hash for and offers the installation's own
    default (`[Contao\\User]` here). An empty line takes that default, which is
    the right answer on someone else's site — measured on c5 on 2026-09-02,
    where sending the password first made it the answer to the class question.
    """
    cmd = "security:hash-password"
    if algorithm != "auto":
        cmd += f" --algorithm={shlex.quote(algorithm)}"
    result = backend.run(cmd, stdin_data="\n" + password + "\n")
    return {"output": result["stdout"].strip()}
