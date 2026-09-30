# Этап 1: локальные проверки

Дата: 30 сентября 2026. Среда: macOS, `Darwin arm64`, Python 3.14.5, Ruby 2.6.10. Это проверки файлов и приложения вне Kubernetes; результат не подтверждает запуск на Ubuntu VM.

## Пройдено

`python3 -m unittest discover -s tests -p test_demo.py`:

```text
Ran 5 tests in 3.541s
OK
```

Покрыты ответы v1/v2, маркеры, счётчики пользовательских запросов, исключение `/healthz` и `/metrics`, HTTP 500, access/error JSON-записи.

`bash -n scripts/bootstrap.sh scripts/deploy.sh scripts/verify.sh && git diff --check`: код завершения `0`, вывода нет.

`ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_stream(File.read(path)); puts "YAML OK: #{path}" }' deploy/base.yaml deploy/envoy-proxy.yaml deploy/gateway.yaml deploy/route.yaml`:

```text
YAML OK: deploy/base.yaml
YAML OK: deploy/envoy-proxy.yaml
YAML OK: deploy/gateway.yaml
YAML OK: deploy/route.yaml
```

Манифесты образов проверены через `docker buildx imagetools inspect`: `python:3.12.12-slim-bookworm` (`sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`), `envoyproxy/gateway:v1.9.1` (`sha256:0049bcb384c591c6a6dd043fe5c9929ef6e74f230e12dd678d2d3701df9b301e`), `envoyproxy/envoy:distroless-v1.39.1` (`sha256:eb2c01c13125d1629637cb4e4cce7207009fb7cc2c8027f9742758549d15b6f4`), `ghcr.io/flannel-io/flannel:v0.28.9` (`sha256:708a2c9c1cfbfe529d1dbb249cb7113af117f3ed26b5e3e4c8ee015e10555204`), `ghcr.io/flannel-io/flannel-cni-plugin:v1.9.1-flannel3` (`sha256:9fccdf677e6e26e76a4aa60da2113bab9852e8317287ba51b2c29778d2351345`) и `registry.k8s.io/pause:3.10.1` (`sha256:278fb9dbcca9518083ad1e11276933a2e96f23de604a3a08cc3c80002767d24c`). У каждого образа в манифесте есть платформа `linux/arm64`.

Через тот же `docker buildx imagetools inspect` отдельно подтверждены `linux/arm64` для `registry.k8s.io/{kube-apiserver,kube-controller-manager,kube-scheduler,kube-proxy}:v1.36.5`. Актуальность Kubernetes 1.36.5 проверена на официальной странице релизов; Envoy Gateway 1.9.1 — в официальной compatibility matrix. Точные пакетные версии и Helm checksum записаны в `deploy/versions.env`.

## Не пройдено в этой среде

Попытка `docker info --format '{{.ServerVersion}}' && docker build --tag trafficops-demo:0.1.0 --file Dockerfile .` остановилась до сборки: Docker daemon недоступен (`unix:///Users/kk0sta/.docker/run/docker.sock: no such file or directory`). Образ приложения локально не собран.

Команды `make bootstrap`, `make deploy` и `make verify` не запускались. Нет фактических результатов Ubuntu 24.04, kubeadm, готовности Envoy Gateway, принятия маршрута и запроса через Gateway. Эти пункты остаются частичными или непроверенными в [таблице приёмки](../requirements/06-acceptance.md).

## Дополнительная проверка конфигурации containerd

30 сентября исправлен сценарий, когда пакет `containerd.io` создаёт конфигурацию уже во время установки. Bootstrap запоминает наличие `/etc/containerd/config.toml` до первого `apt-get`; существующий файл не переписывается и проходит проверку TOML, CRI, `SystemdCgroup` и sandbox image. Если файла не было, созданная пакетом конфигурация сохраняется как `/etc/containerd/config.toml.trafficops-package-default.bak`, затем устанавливается минимальная конфигурация v3 с `required_plugins`, `pinned_images.sandbox` и `SystemdCgroup=true`.

Схема сверена с официальной [containerd 2.3.6 CRI configuration](https://github.com/containerd/containerd/blob/v2.3.6/docs/cri/config.md) и [Kubernetes container runtime instructions](https://kubernetes.io/docs/setup/production-environment/container-runtimes/): для containerd 2.x используется plugin `io.containerd.cri.v1.runtime`, а sandbox image задаётся в `io.containerd.cri.v1.images.pinned_images.sandbox`. Старое поле `sandbox_image` не применяется.

`python3 -m unittest tests.test_bootstrap_containerd_config`:

```text
Ran 1 test
OK
```

Тест разбирает именно встроенный TOML шаблон и выполняет встроенный валидатор: корректная v3 конфигурация проходит; конфигурация с `disabled_plugins=["cri"]` отклоняется, а файл остаётся неизменным. `bash -n scripts/bootstrap.sh`, `python3 -m unittest discover -s tests -p 'test_demo.py'` (6 tests) и `git diff --check` прошли. Проверка изменения файлов после установки пакета и запуск `containerd` доступны только на Ubuntu VM и здесь не выполнялись.
