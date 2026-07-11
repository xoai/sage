import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.settings import SERVICE_NAME


def test_service_name():
    assert SERVICE_NAME == "payments"
