import pathlib
import shlex
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "scripts/platform.sh"
VERSIONS = ROOT / "deploy/versions.env"
BOOTSTRAP = (ROOT / "scripts/bootstrap.sh").read_text()
DEPLOY = (ROOT / "scripts/deploy.sh").read_text()
IMAGES = ("PROMETHEUS_IMAGE", "FLUENTD_IMAGE", "NODE_EXPORTER_IMAGE", "KUBE_STATE_METRICS_IMAGE")


class PlatformTest(unittest.TestCase):
    def run_shell(self, body):
        return subprocess.run(
            [
                "bash",
                "-c",
                f"source {shlex.quote(str(VERSIONS))}; "
                f"source {shlex.quote(str(PLATFORM))}; {body}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_platform_selection_maps_both_architectures(self):
        expected = {
            "arm64": (
                "linux-arm64",
                "f14e804dfee240f55525b667488fe9adca349e63e00c9af634c0beb1421ac310",
            ),
            "amd64": (
                "linux-amd64",
                "1e4ab49e429626cf6c6958d914248b78c9730803c2751b87627e171dc800e7bb",
            ),
        }
        for arch, (helm_platform, helm_sha) in expected.items():
            with self.subTest(arch=arch):
                result = self.run_shell(
                    f"trafficops_select_platform {arch} || exit; "
                    "printf '%s %s %s %s\\n' \"$PLATFORM_ARCH\" \"$HELM_PLATFORM\" \"$HELM_SHA256\" \"$PROMETHEUS_IMAGE\""
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                fields = result.stdout.strip().split(" ", 3)
                self.assertEqual(fields[:3], [arch, helm_platform, helm_sha])
                self.assertTrue(fields[3].endswith("@sha256:" + ("2d25f68eb7aa2e654dadd83b45e5757259b32a1e4b6bc370f1eec927f491265b" if arch == "arm64" else "e906cef998316bbe319f98711e1b4d8613ad37e14b08ff831d7036e77b7464f9")))

    def test_unknown_architecture_is_rejected(self):
        result = self.run_shell("trafficops_select_platform x86_64")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported Debian architecture", result.stderr)

    def test_all_observability_pins_and_common_versions_exist(self):
        version_names = (
            "KUBERNETES_VERSION",
            "KUBERNETES_PACKAGE_VERSION",
            "CONTAINERD_VERSION",
            "DOCKER_CE_VERSION",
            "DOCKER_BUILDX_VERSION",
            "HELM_VERSION",
            "FLANNEL_VERSION",
            "FLANNEL_CNI_VERSION",
            "ENVOY_GATEWAY_VERSION",
            "DEMO_IMAGE",
        )
        for name in version_names:
            self.assertRegex((ROOT / "deploy/versions.env").read_text(), rf"(?m)^{name}=.+$")

        for arch in ("arm64", "amd64"):
            with self.subTest(arch=arch):
                result = self.run_shell(
                    f"trafficops_select_platform {arch} || exit; "
                    f"printf '%s\\n' {' '.join('$' + name for name in IMAGES)}"
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                refs = result.stdout.splitlines()
                self.assertEqual(len(refs), len(IMAGES))
                for ref in refs:
                    self.assertRegex(ref, r"^[^/@:]+(?:/[^/@:]+)*:[^/@]+@sha256:[0-9a-f]{64}$")
                pins = dict(line.split("=", 1) for line in VERSIONS.read_text().splitlines())
                self.assertEqual(refs, [pins[f"{name}_{arch.upper()}"] for name in IMAGES])

    def test_bootstrap_and_deploy_use_shared_dpkg_platform_mapping(self):
        selector = 'trafficops_select_platform "$(dpkg --print-architecture)"'
        self.assertIn(selector, BOOTSTRAP)
        self.assertIn(selector, DEPLOY)
        self.assertIn("[arch=%s signed-by=/etc/apt/keyrings/docker.gpg]", BOOTSTRAP)
        self.assertIn('"$PLATFORM_ARCH" "$DOCKER_UBUNTU_CODENAME"', BOOTSTRAP)
        self.assertIn('helm-v${HELM_VERSION}-${HELM_PLATFORM}.tar.gz', BOOTSTRAP)
        self.assertIn('"$HELM_SHA256" "$helm_archive"', BOOTSTRAP)
        self.assertIn("trafficops_require_node_arch \"$PLATFORM_ARCH\" \"$node_platform\"", DEPLOY)

    def test_local_image_import_requires_matching_node_architecture(self):
        matched = self.run_shell("trafficops_require_node_arch amd64 amd64")
        self.assertEqual(matched.returncode, 0, matched.stderr)
        mismatched = self.run_shell("trafficops_require_node_arch arm64 amd64")
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("does not match", mismatched.stderr)

    def test_deploy_preflight_accepts_each_platform_and_rejects_mismatch(self):
        preflight = DEPLOY[DEPLOY.index('trafficops_select_platform "$(dpkg --print-architecture)"'):].split("\nSUDO=()", 1)[0]
        for host, node, count, succeeds in (
            ("amd64", "amd64", 1, True),
            ("arm64", "arm64", 1, True),
            ("amd64", "arm64", 1, False),
            ("arm64", "amd64", 1, False),
            ("amd64", "amd64", 0, False),
            ("amd64", "amd64", 2, False),
        ):
            with self.subTest(host=host, node=node, count=count):
                result = self.run_shell(f'''
set -Eeuo pipefail
fail() {{ printf '%s\\n' "$*" >&2; exit 1; }}
dpkg() {{ printf '%s\\n' {host}; }}
kctl() {{
  if [[ "$*" == 'get nodes --no-headers' ]]; then
    for ((i=0; i<{count}; i++)); do printf 'node Ready\\n'; done
  else
    printf '%s' {node}
  fi
}}
{preflight}
printf '%s' "$PLATFORM_ARCH"
''')
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                if succeeds:
                    self.assertEqual(result.stdout, host)


if __name__ == "__main__":
    unittest.main()
