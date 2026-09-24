"""Escenarios con la app real (ventana incluida). Cada uno corre en su propio proceso."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCENARIOS = Path(__file__).parent / "scenarios"
PROJECT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="la app usa la API de Windows y un escritorio")


def _run(script: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCENARIOS / script)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


@pytest.mark.gui
def test_integracion_contra_obs_falso():
    result = _run("integration.py", timeout=300)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-3000:]


@pytest.mark.gui
@pytest.mark.real
def test_regresion_real_con_clicks():
    if not (PROJECT / "config.json").is_file():
        pytest.skip("falta config.json con credenciales de Twitch")
    result = _run("regression_real.py", timeout=600)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-3000:]
