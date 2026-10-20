"""A program that stands in for docker: it writes down how it was called and does nothing else."""

from dataclasses import dataclass
from pathlib import Path

from tests.tmux_support import wait_until


@dataclass(frozen=True)
class FakeDocker:
    program: Path
    log: Path

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def wait_for_calls(self, count: int = 1) -> list[str]:
        wait_until(lambda: len(self.calls()) >= count)
        return self.calls()


def install_fake_docker(directory) -> FakeDocker:
    program = Path(directory) / "fake-docker"
    log = Path(directory) / "docker-calls.log"
    program.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'if [ "$1" = "logs" ] || [ "$1" = "compose" ]; then echo "fake logs output"; sleep 30; fi\n'
    )
    program.chmod(0o755)
    return FakeDocker(program, log)
