import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "scripts/bootstrap.sh").read_text()
PAUSE_IMAGE = "registry.k8s.io/pause:3.10.1"


class ContainerdBootstrapConfigTest(unittest.TestCase):
    def test_v3_config_and_preexisting_config_validation(self):
        template = BOOTSTRAP.split('  cat >"$config_tmp" <<EOF\n', 1)[1].split(
            "\nEOF\n", 1
        )[0].replace("$pause_image", PAUSE_IMAGE)
        config = tomllib.loads(template)
        self.assertEqual(config["version"], 3)
        self.assertEqual(
            config["required_plugins"],
            ["io.containerd.cri.v1.runtime", "io.containerd.cri.v1.images"],
        )
        plugins = config["plugins"]
        self.assertEqual(
            plugins["io.containerd.cri.v1.images"]["pinned_images"]["sandbox"],
            PAUSE_IMAGE,
        )
        self.assertIs(
            plugins["io.containerd.cri.v1.runtime"]["containerd"]["runtimes"]["runc"][
                "options"
            ]["SystemdCgroup"],
            True,
        )

        validator = BOOTSTRAP.split(
            '  python3 - "$containerd_config" "$pause_image" <<\'PY\'\n', 1
        )[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory(prefix="trafficops-containerd-test-") as tmp:
            path = pathlib.Path(tmp) / "config.toml"
            path.write_text(template)
            result = subprocess.run(
                [sys.executable, "-c", validator, str(path), PAUSE_IMAGE],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            invalid = 'version = 3\ndisabled_plugins = ["cri"]\n'
            path.write_text(invalid)
            result = subprocess.run(
                [sys.executable, "-c", validator, str(path), PAUSE_IMAGE],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("disables CRI", result.stderr)
            self.assertEqual(path.read_text(), invalid)


if __name__ == "__main__":
    unittest.main()
