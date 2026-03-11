"""
编译 api/references 中的 .proto 文件到 core/proto_gen/
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROTO_ROOT = BASE_DIR / "api" / "references" / "ClassIsland.Shared"
OUT_DIR = BASE_DIR / "core" / "proto_gen"


def compile_protos():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").touch()

    proto_files = list(PROTO_ROOT.glob("Protobuf/**/*.proto"))
    if not proto_files:
        print("No .proto files found!")
        sys.exit(1)

    print(f"Found {len(proto_files)} proto files")

    for pf in proto_files:
        print(f"  Compiling {pf.relative_to(PROTO_ROOT)} ...")
        result = subprocess.run(
            [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={PROTO_ROOT}",
                f"--python_out={OUT_DIR}",
                f"--grpc_python_out={OUT_DIR}",
                str(pf),
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}")
            sys.exit(1)

    # 创建子目录 __init__.py
    for d in OUT_DIR.rglob("*"):
        if d.is_dir():
            (d / "__init__.py").touch()

    # 修复 import 路径: protobuf 生成的 Python 代码使用绝对 import，
    # 需要改为相对 import 或加上包前缀
    _fix_imports(OUT_DIR)

    print(f"Done! Generated files in {OUT_DIR}")


def _fix_imports(out_dir: Path):
    """修复生成代码中的 import 路径"""
    for py_file in out_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        original = content
        # 将 `from Protobuf.xxx import yyy` 改为 `from core.proto_gen.Protobuf.xxx import yyy`
        # 将 `import Protobuf.xxx` 改为 `import core.proto_gen.Protobuf.xxx`
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("from Protobuf"):
                line = "from core.proto_gen." + line[5:]
            elif line.startswith("import Protobuf"):
                line = "import core.proto_gen." + line[7:]
            new_lines.append(line)
        content = "\n".join(new_lines)
        if content != original:
            py_file.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    compile_protos()
