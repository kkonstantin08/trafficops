import pathlib
import shlex
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "scripts/bootstrap.sh").read_text()
VERSIONS = ROOT / "deploy/versions.env"


class BootstrapPlatformTest(unittest.TestCase):
    def run_selection(self, version, flag=""):
        if "select_platform_packages() {" not in BOOTSTRAP:
            self.fail("bootstrap has no platform package selection function")
        function = BOOTSTRAP.split("select_platform_packages() {\n", 1)[1].split(
            "\n}\n", 1
        )[0]
        script = f"""
source {shlex.quote(str(VERSIONS))}
fail() {{ printf 'ERROR: %s\\n' "$*" >&2; exit 1; }}
select_platform_packages() {{
{function}
}}
VERSION_ID={version}
select_platform_packages {flag!r}
printf '%s\\n' "$DOCKER_UBUNTU_CODENAME" "$DOCKER_CE_VERSION" "$DOCKER_BUILDX_VERSION" "$CONTAINERD_VERSION"
"""
        return subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, check=False
        )

    def test_noble_default_keeps_acceptance_package_versions(self):
        result = self.run_selection("24.04")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "noble",
                "5:29.8.1-1~ubuntu.24.04~noble",
                "0.37.1-1~ubuntu.24.04~noble",
                "2.3.6-1~ubuntu.24.04~noble",
            ],
        )

    def test_jammy_requires_dev_flag_and_uses_jammy_arm64_packages(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("bootstrap-dev:\n\tsudo ./scripts/bootstrap.sh --dev-ubuntu-22.04", makefile)
        self.assertIn("prerequisites+=(python3-tomli)", BOOTSTRAP)

        refused = self.run_selection("22.04")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("make bootstrap-dev", refused.stderr)

        allowed = self.run_selection("22.04", "--dev-ubuntu-22.04")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(
            allowed.stdout.splitlines(),
            [
                "jammy",
                "5:29.8.1-1~ubuntu.22.04~jammy",
                "0.37.1-1~ubuntu.22.04~jammy",
                "2.3.6-1~ubuntu.22.04~jammy",
            ],
        )


if __name__ == "__main__":
    unittest.main()
