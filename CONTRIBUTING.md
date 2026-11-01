# Contributing to Modbus Manager

Thanks for your interest in contributing.

## Where the guides live

- **How to contribute** (fork, branch, where to put templates and docs, PRs, testing, pre-commit): **[Contributing — GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki/Contributing)**
- **Template YAML reference** (sensors, controls, `dynamic_config`, calculated sensors, etc.): **[Template Reference — GitHub Wiki](https://github.com/TCzerny/ha-modbus-manager/wiki/Template-Reference)**

Do not duplicate full YAML structure documentation in pull requests; follow the Template Reference and link it when discussing schema.

## Development environment

The repo ships a VS Code dev container.

1. Open the repo in VS Code and choose **Reopen in Container**. On first creation, `scripts/setup` installs Home Assistant, the dev tools and the pre-commit hooks.
2. Start Home Assistant with `scripts/develop`, then open http://localhost:8123.
3. After changing Python code, stop Home Assistant with Ctrl+C and run `scripts/develop` again.

Home Assistant loads the integration straight from `custom_components/modbus_manager` in the repo. Its config lives in `config/`, and only `config/configuration.yaml` is committed.

The Home Assistant version is pinned in `requirements_dev.txt`. To upgrade, bump the pin and rebuild the container.

Run the tests with `python3 -m pytest tests`.

## Quick links

- [Issues](https://github.com/TCzerny/ha-modbus-manager/issues)
- [Discussions](https://github.com/TCzerny/ha-modbus-manager/discussions)
- [Repository](https://github.com/TCzerny/ha-modbus-manager)

Please be respectful and constructive in issues and pull requests.
