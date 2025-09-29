#!/usr/bin/env bash
# Wrapper to run pytest without auto-loading site-installed plugins that may misbehave
# Usage: ./run_pytest.sh [pytest args]

set -euo pipefail

# Prevent pytest from auto-loading setuptools entry-point plugins
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

exec pytest "$@"
