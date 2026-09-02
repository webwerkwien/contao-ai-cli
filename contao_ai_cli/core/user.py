"""Contao backend user management."""
import secrets
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.core.contao_ops import run_json_or_raw, build_set_args, join_args


def user_list(backend: ContaoBackend) -> list:
    return run_json_or_raw(backend, "contao:user:list --format=json")


def user_create(backend: ContaoBackend, username: str, password: str,
                name: str, email: str, language: str = "en",
                admin: bool = False) -> dict:
    """Create a backend user. username, name, email, language, password are mandatory.

    Audit 2026-09-02 (H-2/M-10), replacing the TODO that stood here since April.
    The caller's password no longer reaches any command line.

    ## Why this one is two steps and `user_password` is not

    Feeding `contao:user:create` through its prompts does not work. Measured on
    c5 on 2026-09-02, the sequence is password, confirmation, *admin yes/no*, and
    then a **mandatory group selection whose options are the groups of that
    particular site** — an empty answer is refused. There is no line we could
    send that is correct on an installation we have not seen. And with
    `--no-interaction` the command asks nothing at all, the password prompt
    included.

    So the account is created with a throwaway secret and immediately
    re-passworded through the prompt path, which has only the two password
    questions.

    Note: the throwaway *is* briefly an argument, and that is a deliberate trade,
    not an oversight: it is `secrets.token_urlsafe`, so it is not the user's
    password, is not reused anywhere, and is not attacker-chosen. If the second
    step fails, the account exists with that value — which is why the failure is
    raised loudly rather than folded into the result.
    """
    throwaway = secrets.token_urlsafe(32)

    cmd = (f"contao:user:create "
           f"--username={shlex.quote(username)} "
           f"--password={shlex.quote(throwaway)} "
           f"--name={shlex.quote(name)} "
           f"--email={shlex.quote(email)} "
           f"--language={shlex.quote(language)} "
           f"--no-interaction")
    if admin:
        cmd += " --admin"
    result = backend.run(cmd)

    try:
        user_password(backend, username, password)
    except Exception as e:
        raise ContaoBackendError(
            f"User '{username}' was created, but setting the requested password failed: {e}. "
            f"The account currently has a random password nobody holds — set one with "
            f"`user password --username {username}` or delete the account."
        ) from e

    return {"status": "created", "username": username, "output": result["stdout"]}


def user_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update backend user fields via contao-ai-core-bundle."""
    set_args = build_set_args(fields)
    cmd = join_args("contao:user:update", shlex.quote(username), set_args, "--no-interaction")
    return run_json_or_raw(backend, cmd)


def user_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a backend user via contao-ai-core-bundle."""
    return run_json_or_raw(backend, f"contao:user:delete {shlex.quote(username)} --no-interaction")


def user_password(backend: ContaoBackend, username: str, password: str) -> dict:
    """
    Set a back end user's password.

    Audit 2026-09-02 (H-3/M-10), and the TODO that stood here since April.
    `--password=` put the plaintext into the argument list of the local ssh
    process and of the remote php process. Contao says as much in its own help
    text — *"using this option is not recommended for security reasons"* — and
    offers the prompt instead. That is what this uses now.

    Two lines: the password and its confirmation. `--no-interaction` had to go,
    since it is what suppressed the prompts. Measured against Contao 5 on c5 on
    2026-09-02.
    """
    # username is a positional argument, not a flag
    cmd = f"contao:user:password {shlex.quote(username)}"
    result = backend.run(cmd, stdin_data=f"{password}\n{password}\n")
    return {"status": "updated", "username": username, "output": result["stdout"]}
