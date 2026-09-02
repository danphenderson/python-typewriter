import builtins
import importlib
import importlib.metadata
import sys


def test_package_import_falls_back_when_tomllib_is_unavailable(monkeypatch):
    class FakeTomli:
        @staticmethod
        def load(_file_obj):
            return {"project": {"version": "9.9.9"}}

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tomllib":
            raise ModuleNotFoundError("No module named 'tomllib'")
        if name == "tomli":
            return FakeTomli
        return original_import(name, globals, locals, fromlist, level)

    def missing_distribution(_distribution_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(importlib.metadata, "version", missing_distribution)
    sys.modules.pop("typewriter", None)

    typewriter = importlib.import_module("typewriter")

    assert typewriter.__version__ == "9.9.9"
