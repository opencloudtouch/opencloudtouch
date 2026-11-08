"""Check whether the OCT redirect block is present in a speaker's /etc/hosts."""

# ``grep -c`` prints 0 and exits 1 when nothing matches; ``; true`` keeps the exit code clean without a second
# "0" (the former ``|| echo '0'`` fallback produced "0\n0", which was read as "found").
HOSTS_MARKER_COUNT_COMMAND = "grep -c 'OCT-START' /etc/hosts 2>/dev/null; true"


def hosts_redirect_present(output: str | None) -> bool:
    """True if the command output reports at least one OCT-START line."""
    tokens = (output or "").split()
    return bool(tokens) and tokens[0].isdigit() and int(tokens[0]) > 0
