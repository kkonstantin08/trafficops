import pathlib
import subprocess
import unittest


class BootstrapTaintTest(unittest.TestCase):
    def test_removal_repeat_and_api_failures(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "scripts/bootstrap.sh").read_text()
        self.assertIn("node_taints=$(", source)
        block = source[source.index("node_taints=$("):source.index("if kctl --kubeconfig=/etc/kubernetes/admin.conf get ds")]
        for taints, get_code, remove_code, expected_code, removed in [
            ("node-role.kubernetes.io/control-plane", 0, 0, 0, True),
            ("node.kubernetes.io/not-ready", 0, 0, 0, False),
            ("", 9, 0, 9, False),
            ("node-role.kubernetes.io/control-plane", 0, 8, 8, True),
        ]:
            with self.subTest(taints=taints, get_code=get_code, remove_code=remove_code):
                script = f'''set -Eeuo pipefail
kctl() {{
  [[ "$*" != *--ignore-not-found* ]] || return 99
  if [[ "$2" == get ]]; then
    printf '%s\\n' '{taints}'
    return {get_code}
  fi
  [[ "$*" == *"taint nodes --all node-role.kubernetes.io/control-plane-" ]] || return 98
  echo removed
  return {remove_code}
}}
{block}
'''
                result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected_code, result.stderr)
                self.assertEqual("removed" in result.stdout, removed)


if __name__ == "__main__":
    unittest.main()
