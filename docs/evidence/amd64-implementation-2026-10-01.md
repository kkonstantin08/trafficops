# AMD64 implementation — 2026-10-01

## Revision

- Base SHA: `20e5d247b4b044cec80f1a3c3f03abd940c3574c`. Перед работой локальная/удалённая `main` совпадали, рабочее дерево было чистым.
- Branch: `fix/amd64-bootstrap`.
- Resulting implementation commit SHA: `db61c3dd488287b7aea70d9c4c8aa6be2ab318ba`.
- Этот evidence добавляется отдельным documentation-only commit после получения CI реализации. Его собственный SHA не включается в его содержимое; проверяемая ревизия кода указана выше. Ни один commit этапа не merged в `main`.
- Дата и среда проверки: 1 октября 2026, Europe/Moscow; macOS ARM64, Python 3.14.5, Bash 3.2.57. Ubuntu VM не запускалась и не изменялась.

## Problem

Bootstrap отвергал архитектуры кроме `arm64`, создавал Docker APT source с `arch=arm64`, скачивал `linux-arm64` Helm с одной checksum и печатал ARM64 в результате. Четыре observability image refs были закреплены по ARM64 platform-specific digest; перенос этих refs на AMD64 не был корректным выбором платформы. CI multiarch build demo-образа не доказывал поддержку bootstrap всего стенда.

## Changes

- [platform.sh](../../scripts/platform.sh): общий `trafficops_select_platform` для Debian `arm64`/`amd64`; другие значения отклоняются. Mapping выбирает platform arch, Helm archive/checksum и четыре observability refs.
- [bootstrap.sh](../../scripts/bootstrap.sh): вызывает общий selector с `dpkg --print-architecture`; использует фактическую архитектуру для Docker APT, Helm URL/extraction/checksum и итогового сообщения. Noble/Jammy package-selection, версии и остальная логика сохранены.
- [deploy.sh](../../scripts/deploy.sh): использует тот же selector, читает `status.nodeInfo.architecture` единственного Kubernetes-узла и требует совпадения с локальным хостом **до сборки, импорта и изменений ресурсов**. Observability substitutions используют выбранные refs. Local image build/import по-прежнему выполняется внутри VM.
- [versions.env](../../deploy/versions.env): добавлена AMD64 Helm checksum, четыре пары `_IMAGE_ARM64`/`_IMAGE_AMD64`. ARM64 digests и все существовавшие версии сохранены.
- [test_platform.py](../../tests/test_platform.py): rootless/offline выбор обеих архитектур, неизвестная архитектура, Docker/Helm wiring, checksums, все refs/versions, matching/mismatched node arch и фактический extracted deploy-preflight с подставными `dpkg`/`kctl`, включая 0/2 узла.
- [CI](../../.github/workflows/ci.yml): syntax check включает helper; новые Python tests входят в существующий unittest discovery. Actions versions/runtime warnings не менялись.
- [README](../../README.md) и [verification](../verification.md): обновлены архитектурные формулировки, явно разделены code/CI validation AMD64 и ранее предоставленное ARM64 live evidence.

Связанные ID: DEP-001/002/004/006, DOC-002/003, OPT-002. Acceptance matrix не изменялась; DEP-002/004/006 не объявляются выполненными. Baseline-файл сохранён без изменений. Приложение, UI, controller, canary policy и Kubernetes YAML/архитектура не менялись.

## Architecture mapping

| component | arm64 | amd64 | pinning method |
| --- | --- | --- | --- |
| Ubuntu | 24.04, dpkg=arm64 | 24.04, dpkg=amd64 | Проверка ОС/arch; не обещание clean runtime |
| Kubernetes packages | kubeadm/kubelet/kubectl 1.36.5-1.1 | Те же версии | Exact APT package version; официальный index содержит обе architectures |
| containerd.io | 2.3.6-1~ubuntu.24.04~noble | Та же версия | Exact Docker APT version, фактический arch в source |
| Docker CE/CLI | 5:29.8.1-1~ubuntu.24.04~noble | Та же версия | Exact Docker APT version |
| Buildx | 0.37.1-1~ubuntu.24.04~noble | Та же версия | Exact Docker APT version |
| Helm | linux-arm64, 3.22.0 | linux-amd64, 3.22.0 | Отдельные official SHA256, обязательный sha256sum check |
| Prometheus | PROMETHEUS_IMAGE_ARM64 | PROMETHEUS_IMAGE_AMD64 | v3.14.0 + platform-specific digest |
| Fluentd | FLUENTD_IMAGE_ARM64 | FLUENTD_IMAGE_AMD64 | v1.19.3-debian-2.2 + platform-specific digest |
| node-exporter | NODE_EXPORTER_IMAGE_ARM64 | NODE_EXPORTER_IMAGE_AMD64 | v1.12.1 + platform-specific digest |
| kube-state-metrics | KUBE_STATE_METRICS_IMAGE_ARM64 | KUBE_STATE_METRICS_IMAGE_AMD64 | v2.20.0 + platform-specific digest |
| Flannel | linux/arm64 descriptor | linux/amd64 descriptor | Existing v0.28.9 multiarch tag в официальном release manifest |
| Flannel CNI | linux/arm64 descriptor | linux/amd64 descriptor | Existing v1.9.1-flannel3 multiarch tag |
| Envoy Gateway | linux/arm64 descriptor | linux/amd64 descriptor | Existing Helm chart v1.9.1 / gateway image tag v1.9.1 |
| Envoy Proxy | linux/arm64 descriptor | linux/amd64 descriptor | Existing default distroless-v1.39.1 multiarch image |
| Demo/controller image | linux/arm64 | linux/amd64 | Existing Dockerfile, Python multiarch digest; CI builds both, local deploy builds/imports host image |

### Helm verification

Official checksum responses получены независимо исполнителем и оркестратором по HTTPS. Проверка TLS не отключалась. Проверялось содержимое official checksum metadata; установка/исполнение Helm в Ubuntu не выполнялись.

| archive | SHA256 | official source |
| --- | --- | --- |
| helm-v3.22.0-linux-arm64.tar.gz | `f14e804dfee240f55525b667488fe9adca349e63e00c9af634c0beb1421ac310` | [sha256sum](https://get.helm.sh/helm-v3.22.0-linux-arm64.tar.gz.sha256sum) |
| helm-v3.22.0-linux-amd64.tar.gz | `1e4ab49e429626cf6c6958d914248b78c9730803c2751b87627e171dc800e7bb` | [sha256sum](https://get.helm.sh/helm-v3.22.0-linux-amd64.tar.gz.sha256sum) |

### Observability OCI indexes and pins

Команда для каждого официального registry ref: `docker buildx imagetools inspect IMAGE:TAG --raw`. В возвращённом index выбирались только descriptors с `platform.os=linux` и `platform.architecture=arm64|amd64`; attestations/прочие платформы не принимались за executable image. Пары digests ниже независимо повторно проверены оркестратором и сопоставлены с `versions.env`. Старые ARM64 refs совпали с baseline.

| official image tag | arm64 child digest | amd64 child digest | observed index digest |
| --- | --- | --- | --- |
| `prom/prometheus:v3.14.0` | `sha256:2d25f68eb7aa2e654dadd83b45e5757259b32a1e4b6bc370f1eec927f491265b` | `sha256:e906cef998316bbe319f98711e1b4d8613ad37e14b08ff831d7036e77b7464f9` | `sha256:5ce7540c3c00ef4ab0c9d2c995c6a5b9c421f44b4a115d97a2c7af3b1c21cbb0` |
| `fluent/fluentd:v1.19.3-debian-2.2` | `sha256:5b3b1325f180f75e2c41672d03d30f3a26440d34667c49d6b9b0f9e5b766d734` | `sha256:13ba7ec2fa8fe9141e905c31c1d0043abeb3f364bb02fec6618d45374fe10ea3` | `sha256:b6794cd63b153a2cbc2f7c447ac5036597a3c093b393e786c4fff8abe2c4b911` |
| `quay.io/prometheus/node-exporter:v1.12.1` | `sha256:c9ef89f9464f09e7234decaae68a80ab856ff0014435677a99fd48b03dd410ea` | `sha256:da83fae85603c4e47e6c68369a7d746e2dda683dc35ea2e234b4f171e0d92798` | `sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0` |
| `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.20.0` | `sha256:92b46557c71ecac53825772e4827dbcd9fca876b1950060f8fb2f2ef0d7a27af` | `sha256:01171220c7c059afc85034ffe687bfe7249e41c0cc46fbe9a5128503ceee3016` | `sha256:42cfe3723a5f058171c627537fb57a3ea0f26e4380fa18555a95cb1a1b4cfc5b` |

Pinning deploy использует **child digests**, index digests здесь сохранены как наблюдённый registry snapshot. Upstream источники: [Prometheus](https://github.com/prometheus/prometheus/releases/tag/v3.14.0), [Fluentd image](https://github.com/fluent/fluentd-docker-image/releases/tag/v1.19.3-2.2), [node-exporter](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1), [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics/releases/tag/v2.20.0).

### Package compatibility

Официальные package indexes получены и разобраны через Python stdlib (HTTPS с установленным certifi CA bundle). Найдены точные version/architecture записи:

| package | version | architectures |
| --- | --- | --- |
| containerd.io | `2.3.6-1~ubuntu.24.04~noble` | arm64, amd64 |
| docker-buildx-plugin | `0.37.1-1~ubuntu.24.04~noble` | arm64, amd64 |
| docker-ce | `5:29.8.1-1~ubuntu.24.04~noble` | arm64, amd64 |
| docker-ce-cli | `5:29.8.1-1~ubuntu.24.04~noble` | arm64, amd64 |
| kubeadm | `1.36.5-1.1` | arm64, amd64 |
| kubectl | `1.36.5-1.1` | arm64, amd64 |
| kubelet | `1.36.5-1.1` | arm64, amd64 |

Источники и SHA256 полученных index bytes (снимок на дату проверки, не новая настройка APT):

- [kubernetes](https://pkgs.k8s.io/core:/stable:/v1.36/deb/Packages): `9d60cc41640cc8e54ec7263dc1cab17ebc35c08704523be09ff50e7c1dd066f5`.
- [docker-amd64](https://download.docker.com/linux/ubuntu/dists/noble/stable/binary-amd64/Packages.gz): `4c74b468bc684576541595906cc064c53fd13d8c84519eadfb6b494bbdcdf3a3`.
- [docker-arm64](https://download.docker.com/linux/ubuntu/dists/noble/stable/binary-arm64/Packages.gz): `950a315201cb5d5b44e38224a35024d1fa8aba781382d1476857aa8b94385803`.

Это доказательство доступных metadata точных package versions для обеих платформ, а не установка пакетов и не решение их зависимостей в чистой Noble VM. APT sources/ключи и механика установки не заменены.

### Other runtime image compatibility

Та же команда `docker buildx imagetools inspect REF --raw` подтвердила linux/arm64 и linux/amd64 у следующих indexes:

| image tag | arm64 child digest | amd64 child digest |
| --- | --- | --- |
| `ghcr.io/flannel-io/flannel-cni-plugin:v1.9.1-flannel3` | `sha256:ad93ab911b9d4a797f5b565d4932995465f842defe3f332c342cc2b1314d04d6` | `sha256:b60bc0d7ea43bc261720e4e12870f23e9b73127138e7aa8769aabab980e85153` |
| `envoyproxy/gateway:v1.9.1` | `sha256:b45ad63b5aeec34791b7b944a877a6542738dd4f48c07a8f4db1e9fce983823e` | `sha256:2999d87c3a2b3e890e0ee1a2b11a159b60963aadb2cbb9f2c0a49e0197df3c72` |
| `envoyproxy/envoy:distroless-v1.39.1` | `sha256:62649e9cb5073a995b57d888f98382927ad15e91c53affac92a8a48a365027db` | `sha256:9c9ca6bef1e4e355b00b4657cbe123baf3b4a78613cb949b6cbabaab897a6c28` |
| `registry.k8s.io/kube-apiserver:v1.36.5` | `sha256:fd2aeee57db21e3e988ae7845dd549f8fdc036a3de985dc70aad4a69ad8ceb5a` | `sha256:78487f7b4b1a588d9630f758f6677895eabe00d93c4cbbea3d6b06e5f476a371` |
| `registry.k8s.io/kube-controller-manager:v1.36.5` | `sha256:15f8587dc75f4f473bcff3c514193f192924e1e087936556bec94b5c087a32c3` | `sha256:a7b63e85c7914ff6d49d97004a09b8a469efa6fe41f58d2c1faa2606ed8cb742` |
| `registry.k8s.io/kube-scheduler:v1.36.5` | `sha256:a09834fd62d185544da5ab50c137af000a72b933098fbdda822d391df1566ea0` | `sha256:249bcbdb401e4882c125e5b6958aab09954ea59d06289af380e60dd58115405e` |
| `registry.k8s.io/kube-proxy:v1.36.5` | `sha256:69a64a13f7159f977d9be0b63c915d1814edd281e2514d2a22bd9a5536237a0a` | `sha256:54f6c76e0413be01177617704c8b6e2c291a4ec2226a944216b62d5ac1d625df` |
| `registry.k8s.io/pause:3.10.1` | `sha256:e9c466420bcaeede00f46ecfa0ca8cd854c549f2f13330e2723173d88f2de70f` | `sha256:e5b941ef8f71de54dc3a13398226c269ba217d06650a21bd3afcf9d890cf1f41` |
| `ghcr.io/flannel-io/flannel:v0.28.9` | `sha256:b3de04e839cb73a9bf9cafced28de1c344bb4e2e9ca408b7ac500ce811db899f` | `sha256:d666a036197fe6c8928f82b670d89f38f5830d25e70bfcc35641da06f03cfcad` |

Официальный [Flannel release manifest](https://github.com/flannel-io/flannel/releases/download/v0.28.9/kube-flannel.yml) также проверен: использует ровно flannel v0.28.9 и flannel-cni-plugin v1.9.1-flannel3. [Матрица Envoy Gateway](https://gateway.envoyproxy.io/news/releases/matrix/) включает Kubernetes 1.36 для Gateway 1.9. Отдельный architecture-specific pin для этих existing multiarch tags не нужен для выбора платформы; tags/chart versions сохранены как в baseline, не преобразованы в новые digest pins. Runtime совместимость определяется только будущим live-запуском.

## Verification

- Baseline suite до изменения: `python3 -m unittest discover -s tests -p 'test_*.py'` — 34 tests, OK (8.105 s).
- Исполнитель сообщил RED до helper implementation: 6 отказов/subtest failures из-за отсутствовавшего helper/refs; после реализации первоначальные 5 новых tests стали GREEN. Оркестратор проверил итоговый код и самостоятельно выполнил окончательные checks.
- Итоговый `python3 -m unittest tests.test_platform -v` — 6 tests, OK (0.053 s); включает реальные shell mapping и extracted preflight с mock commands.
- Итоговый full unittest — 40 tests, OK (8.148 s).
- `bash -n scripts/platform.sh scripts/bootstrap.sh scripts/deploy.sh scripts/verify.sh scripts/validate_manifests.sh` — exit 0.
- `node --check web/app.js` и `node tests/test_release_ui.js` — exit 0; `Release UI availability checks passed`.
- `./scripts/validate_manifests.sh` — 36 resources / 7 files, Valid 36, Invalid 0, Errors 0, Skipped 0. Это schema validation, не Kubernetes admission/runtime.
- Независимая сверка 8 image pins и 2 Helm sums с official snapshots — совпали; все старые версии и ARM64 pins сохранены.
- `git diff --check` и staged diff check — exit 0; baseline, requirements/acceptance, demo, controller, web и Kubernetes YAML не изменены.

## CI

[CI реализации 36841143105](https://github.com/kkonstantin08/trafficops/actions/runs/36841143105) для `db61c3dd488287b7aea70d9c4c8aa6be2ab318ba` запущен автоматически по push и завершён `completed / success`. Job validate прошёл: 40 Python tests, 36 schemas, shell/JS checks, release UI availability и Buildx сборка `linux/amd64,linux/arm64` без публикации образа. Ни Kubernetes, ни bootstrap/deploy/runtime в CI не запускались. CI финального documentation-only HEAD проверяется отдельно после публикации evidence.

## Limitations

**AMD64 clean-room runtime verification has not yet been performed.**

Этап подтверждает code-level support, package/image metadata и локальную/CI validation. Ни bootstrap, ни deploy/verify на чистой Ubuntu 24.04 AMD64 не запускались. Не подтверждены Kubernetes admission, container runtime, CNI networking, полный Gateway/Prometheus/Fluentd путь и повторная установка на AMD64. Existing [ARM64 пользовательский live transcript](vm-ubuntu24-2026-10-01.md) относится к предыдущему состоянию стенда и не доказывает live-регрессию нового SHA; clean ARM64 bootstrap также остаётся отдельной проверкой.

DEP-002/004/006 остаются с прежними неполными статусами. Требования финального паспорта и submission не затрагивались. Существующие предупреждения Starlette/httpx и GitHub Actions Node.js runtime не исправлялись. Прочие несоответствия baseline этим этапом не решались. Ветка не merged; clean-room тестирование не начато.
