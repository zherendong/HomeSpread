"""记录已安装的运行依赖闭包，排除构建与测试工具。

仅在主动升级依赖并完成审计后运行。构建消费已提交的锁文件，
不会自动重写锁文件或静默升级依赖。
"""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def main():
    pending = ["pymobiledevice3", "PySide6-Essentials"]
    found = {}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in found:
            continue
        dist = distribution(name)
        found[name] = dist.version
        for text in dist.requires or []:
            req = Requirement(text)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                pending.append(req.name)
    lines = ["# macOS arm64 / CPython 3.12 运行依赖快照。",
             "# 由 scripts/lock_macos.py 生成；升级依赖并完成审计后主动更新。"]
    lines += [f"{name}=={version}" for name, version in sorted(found.items())]
    (ROOT / "requirements-macos.lock").write_text("\n".join(lines) + "\n")
    print(f"已锁定 {len(found)} 个运行时组件")


if __name__ == "__main__":
    main()
