"""Podman-based container manager for isolated skill script execution."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _sanitize_user_id(user_id: str) -> str:
    """Make user_id safe for use in a container name."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", user_id)


class ContainerManager:
    """Manages a per-user Podman container for isolated skill execution.

    One persistent container named ``skillbot-<user_id>`` runs
    ``sleep infinity`` and is reused across sessions.  Skill scripts
    are executed via ``podman exec`` rather than directly on the host.
    """

    def __init__(
        self,
        user_id: str,
        workspace_path: Path,
        image: str,
        skill_mount_paths: dict[str, Path],
    ) -> None:
        self.user_id = user_id
        self.workspace_path = workspace_path
        self.image = image
        self.skill_mount_paths = skill_mount_paths
        self.container_name = f"skillbot-{_sanitize_user_id(user_id)}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_running(
        self,
        requires_network: bool,
        pip_deps: list[str],
        npm_deps: list[str],
    ) -> None:
        """Ensure the container exists and is running.

        For MVP, always recreate to avoid configuration drift (e.g. a skill
        with network access was added after the container was created without
        network).
        """
        self._stop_and_remove()
        self._create_and_start(requires_network)
        self._install_deps(pip_deps, npm_deps)
        logger.info("Container '%s' is ready", self.container_name)

    def exec_script(self, script_path: Path, skill_name: str, args: str) -> str:
        """Run a skill script inside the container and return stdout.

        ``script_path`` is the *host* path of the script; this method
        translates it to the container path
        ``/skills/<skill_name>/scripts/<filename>`` before executing.
        """
        container_script = f"/skills/{skill_name}/scripts/{script_path.name}"
        workdir = f"/skills/{skill_name}/scripts"
        executor = _get_executor(script_path)
        cmd = [
            "podman",
            "exec",
            "-w",
            workdir,
            self.container_name,
            *executor,
            container_script,
        ]
        if args.strip():
            cmd.extend(args.strip().split())

        logger.debug("Container exec: %s", cmd)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            output = result.stdout
            if result.returncode != 0:
                output += f"\nSTDERR: {result.stderr}"
                output += f"\nExit code: {result.returncode}"
            return output.strip()
        except subprocess.TimeoutExpired:
            return "Error: Script execution timed out after 60 seconds"
        except Exception as e:
            return f"Error executing script in container: {e}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        """Return True if the container exists and is in a running state."""
        try:
            result = subprocess.run(
                [
                    "podman",
                    "inspect",
                    "--format",
                    "{{.State.Status}}",
                    self.container_name,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() == "running"
        except Exception:
            return False

    def _stop_and_remove(self) -> None:
        """Stop and remove an existing container (if any), ignoring errors."""
        try:
            subprocess.run(
                ["podman", "rm", "-f", self.container_name],
                capture_output=True,
                check=False,
            )
        except Exception as e:
            logger.debug("Could not remove container '%s': %s", self.container_name, e)

    def _create_and_start(self, requires_network: bool) -> None:
        """Create and start the container with the appropriate mounts and network."""
        network = "slirp4netns" if requires_network else "none"

        cmd = [
            "podman",
            "run",
            "-d",
            "--name",
            self.container_name,
            "--cap-drop=ALL",
            "--user",
            "1000:1000",
            f"--network={network}",
            "-v",
            f"{self.workspace_path}:/workspace:rw",
        ]

        for skill_name, scripts_dir in self.skill_mount_paths.items():
            cmd += ["-v", f"{scripts_dir}:/skills/{skill_name}/scripts:ro"]

        cmd += [self.image, "sleep", "infinity"]

        logger.info("Creating container: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start container '{self.container_name}': {result.stderr}"
            )
        logger.info("Container '%s' started", self.container_name)

    def _install_deps(self, pip_deps: list[str], npm_deps: list[str]) -> None:
        """Install Python and Node dependencies inside the running container."""
        if pip_deps:
            logger.info("Installing pip deps in container: %s", pip_deps)
            result = subprocess.run(
                [
                    "podman",
                    "exec",
                    self.container_name,
                    "pip",
                    "install",
                    "--quiet",
                    *pip_deps,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("pip install failed: %s", result.stderr)

        if npm_deps:
            logger.info("Installing npm deps in container: %s", npm_deps)
            result = subprocess.run(
                [
                    "podman",
                    "exec",
                    self.container_name,
                    "npm",
                    "install",
                    "-g",
                    *npm_deps,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("npm install failed: %s", result.stderr)


def _get_executor(script_path: Path) -> list[str]:
    """Return the interpreter command list for a given script extension."""
    ext = script_path.suffix
    if ext == ".py":
        return ["python"]
    if ext == ".sh":
        return ["bash"]
    if ext == ".js":
        return ["node"]
    if ext == ".ts":
        return ["npx", "tsx"]
    return []
