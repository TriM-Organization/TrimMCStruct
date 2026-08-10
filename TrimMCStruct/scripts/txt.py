"""
.txt 文件格式插件 (Setblock Text)

支持读取和写入普通 setblock 指令文本。
此格式不支持命令方块数据，仅包含方块信息。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import re

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class TxtPlugin(IPlugin):
    """
    .txt 文件格式插件

    支持读取和写入普通 setblock 指令文本。
    此格式不支持命令方块数据，仅包含方块信息。
    """

    @property
    def name(self) -> str:
        return "txt"

    @property
    def extensions(self) -> list[str]:
        return [".txt"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        if isinstance(file_obj, str):
            content = file_obj
        else:
            content = file_obj.read().decode("utf-8")
        return cls._parse_content(content)

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "r", encoding="utf-8") as f:
            return cls.load(f.read())

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        sx, sy, sz = struct.size
        lines = []

        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        continue

                    name = block.base_name
                    states = block.states
                    state_str = ""
                    if states:
                        parts = []
                        for k, v in sorted(states.items()):
                            if isinstance(v, bool):
                                parts.append(f'"{k}"={"true" if v else "false"}')
                            elif isinstance(v, str):
                                parts.append(f'"{k}"="{v}"')
                            else:
                                parts.append(f'"{k}"={v}')
                        state_str = " [" + ",".join(parts) + "]"

                    lines.append(f"setblock ~{x} ~{y} ~{z} {name}{state_str}")

        file_obj.write("\n".join(lines))

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            self.dump(struct, f)

    @classmethod
    def _parse_content(cls, content: str) -> MatrixStructure:
        """解析 txt 内容，返回 MatrixStructure"""
        lines = content.splitlines()
        pattern = re.compile(
            r"^\s*setblock\s+"
            r"(~?-?\d+)\s+"
            r"(~?-?\d+)\s+"
            r"(~?-?\d+)\s+"
            r"([^\s\[]+)(?:\s+(\d+))?\s*(.*)"
        )

        blocks = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = pattern.match(line)
            if not m:
                continue
            x_str, y_str, z_str, block_name, data_val, remainder = m.groups()

            def parse_coord(s):
                if s.startswith("~"):
                    s = s[1:]
                    if s == "":
                        return 0
                return int(s)

            x = parse_coord(x_str)
            y = parse_coord(y_str)
            z = parse_coord(z_str)

            state_str = ""
            if remainder:
                rem = remainder.strip()
                if rem.startswith("["):
                    state_str = rem

            blocks.append((x, y, z, block_name, state_str))

        if not blocks:
            return MatrixStructure((0, 0, 0))

        min_x = min(b[0] for b in blocks)
        min_y = min(b[1] for b in blocks)
        min_z = min(b[2] for b in blocks)
        max_x = max(b[0] for b in blocks)
        max_y = max(b[1] for b in blocks)
        max_z = max(b[2] for b in blocks)

        size = (max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1)
        struct_obj = MatrixStructure(size)
        struct_obj._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        for x, y, z, block_name, state_str in blocks:
            lx = x - min_x
            ly = y - min_y
            lz = z - min_z
            states = cls._parse_state_str(state_str)
            block = Block("minecraft", block_name, states, compability_version=COMPABILITY_VERSION)
            struct_obj.set_block((lx, ly, lz), block)

        return struct_obj

    @staticmethod
    def _parse_state_str(state_str: str) -> dict:
        states = {}
        if not state_str or state_str == "[]":
            return states
        s = state_str.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        pattern = re.compile(r'"([^"]+)"\s*=\s*("[^"]*"|[^,]+)')
        for m in pattern.finditer(s):
            k = m.group(1)
            v_str = m.group(2).strip()
            if v_str.startswith('"') and v_str.endswith('"'):
                states[k] = v_str[1:-1]
            elif v_str.lower() == "true":
                states[k] = True
            elif v_str.lower() == "false":
                states[k] = False
            else:
                try:
                    states[k] = int(v_str)
                except ValueError:
                    try:
                        states[k] = float(v_str)
                    except ValueError:
                        states[k] = v_str
        return states
