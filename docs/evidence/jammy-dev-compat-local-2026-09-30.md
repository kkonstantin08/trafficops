# Ubuntu 22.04 development-mode compatibility

This is local implementation evidence only. No VM was accessed and no packages were installed.

The user-reported VM preflight is Ubuntu 22.04.5, ARM64, 4 vCPU, 3.8 GiB total RAM, 2.9 GiB available, and 15 GB free on a 30 GB root logical volume. `bootstrap.sh` checks `MemTotal >= 3 GiB`; that reported total clears the current preflight threshold, but does not establish that the full stack fits. Ubuntu 24.04 remains the default acceptance environment. Ubuntu 22.04 is accepted only by the explicit `make bootstrap-dev` target and does not prove DEP-001.

The Docker repository's official [Jammy ARM64 package index](https://download.docker.com/linux/ubuntu/dists/jammy/stable/binary-arm64/Packages.gz) contains the exact pinned package versions below:

| Package | Version | SHA-256 |
| --- | --- | --- |
| `docker-ce` | `5:29.8.1-1~ubuntu.22.04~jammy` | `16c998bce2c0e434b37a7c3e5fe57417d341af75ce89166b16633af239b56a59` |
| `docker-ce-cli` | `5:29.8.1-1~ubuntu.22.04~jammy` | `89d399ffe9fc879fd405041d867a2659d4ee8641c1d815d025da8a2473ac6e9d` |
| `docker-buildx-plugin` | `0.37.1-1~ubuntu.22.04~jammy` | `82a5d634bb99104903fc3cb36235e7e3be7df2ad9e91fe6a362dcd847ab6badd` |
| `containerd.io` | `2.3.6-1~ubuntu.22.04~jammy` | `c1cfd009fed5b02ff4f1d7d35f1dc312b2dc338a8ff33c6c152ccaacaeb089a1` |

Jammy's Python 3.10 lacks `tomllib`; its official Ubuntu package is [`python3-tomli`](https://packages.ubuntu.com/jammy/arm64/python3-tomli). Dev bootstrap installs it and the existing containerd configuration validator falls back from `tomllib` to `tomli`. The application image still uses Python 3.12.12.

Local checks: platform selection tests cover Noble default, Jammy package mapping, and refusal to run Jammy without the dev flag. The containerd validator test also forces the `tomli` import path. These checks do not establish live Kubernetes or Ubuntu runtime behavior.
