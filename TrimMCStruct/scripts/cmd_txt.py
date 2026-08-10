"""
指令txt 文件格式插件 (Command Text)

支持读取和写入包含命令方块数据的 .txt 文件。
文件格式为 setblock 指令，命令方块附带 NBT 数据。

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


class CommandTxtPlugin(IPlugin):
    """
    指令txt 文件格式插件

    支持读取和写入包含命令方块数据的 .txt 文件。
    普通 setblock 指令不含命令数据。
    命令方块指令格式: setblock ~x ~y ~z command_block 0{"cmd","title",cond,redstone,delay,mode}
    """

    @property
    def name(self) -> str:
        return "cmd_txt"

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

                    base = f"setblock ~{x} ~{y} ~{z} {name}{state_str}"

                    idx = x * sz * sy + y * sz + z
                    nbt_data = struct._special_blocks.get(idx)
                    if nbt_data and nbt_data.get("id") == "CommandBlock":
                        cmd = cls._escape_cmd(nbt_data.get("Command", ""))
                        title = cls._escape_cmd(nbt_data.get("CustomName", ""))
                        cond = "true" if nbt_data.get("conditionalMode", False) else "false"
                        redstone = "true" if not bool(nbt_data.get("auto", 1)) else "false"
                        delay = nbt_data.get("TickDelay", 0)
                        mode = 0
                        if "repeating" in block.base_name.lower():
                            mode = 1
                        elif "chain" in block.base_name.lower():
                            mode = 2
                        nbt_str = f'{{"{cmd}","{title}",{cond},{redstone},{delay},{mode}}}'
                        base += f" {nbt_str}"

                    lines.append(base)

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

            cmd_data = None
            state_str = ""
            if remainder:
                rem = remainder.strip()
                if "{" in rem:
                    state_part = ""
                    nbt_part = ""
                    if rem.startswith("["):
                        bracket_match = re.search(r"\]\s*\{", rem)
                        if bracket_match:
                            bracket_end = bracket_match.start()
                            state_part = rem[:bracket_end + 1]
                            nbt_part = rem[bracket_end + 1:]
                        else:
                            nbt_part = rem
                    else:
                        nbt_part = rem

                    state_str = state_part
                    nbt_part = nbt_part.strip()
                    if nbt_part.startswith("{") and nbt_part.endswith("}"):
                        inner = nbt_part[1:-1]
                        parts = cls._split_nbt_fields(inner)
                        if len(parts) >= 6:
                            cmd = cls._unescape_cmd(parts[0].strip().strip('"'))
                            title = cls._unescape_cmd(parts[1].strip().strip('"'))
                            cond = parts[2].strip().lower() == "true"
                            redstone = parts[3].strip().lower() == "true"
                            try:
                                delay = int(parts[4].strip())
                            except Exception:
                                delay = 0
                            try:
                                mode = int(parts[5].strip())
                            except Exception:
                                mode = 0
                            cmd_data = {
                                "id": "CommandBlock",
                                "Command": cmd,
                                "CustomName": title,
                                "auto": 1 if not redstone else 0,
                                "TickDelay": delay,
                                "conditionalMode": cond,
                                "TrackOutput": 1,
                                "ExecuteOnFirstTick": 1,
                                "Version": 19,
                            }
                elif rem.startswith("["):
                    state_str = rem

            blocks.append((x, y, z, block_name, state_str, cmd_data))

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

        for x, y, z, block_name, state_str, cmd_data in blocks:
            lx = x - min_x
            ly = y - min_y
            lz = z - min_z
            states = cls._parse_state_str(state_str)
            block = Block("minecraft", block_name, states, compability_version=COMPABILITY_VERSION)
            struct_obj.set_block((lx, ly, lz), block)

            if cmd_data:
                idx = lx * size[2] * size[1] + ly * size[2] + lz
                struct_obj._special_blocks[idx] = cmd_data

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

    @staticmethod
    def _split_nbt_fields(s: str) -> list:
        parts = []
        current = ""
        in_quotes = False
        backslash_count = 0
        for ch in s:
            if ch == "\\":
                backslash_count += 1
                current += ch
                continue
            if ch == '"':
                if backslash_count % 2 == 0:
                    in_quotes = not in_quotes
                current += ch
            elif ch == "," and not in_quotes:
                parts.append(current)
                current = ""
            else:
                current += ch
            backslash_count = 0
        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _escape_cmd(s: str) -> str:
        s = s.replace("\\", "\\\\")
        s = s.replace('"', '\\"')
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        s = s.replace("\t", "\\t")
        return s

    @staticmethod
    def _unescape_cmd(s: str) -> str:
        result = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == "\\" and i + 1 < n:
                nxt = s[i + 1]
                if nxt == "n":
                    result.append("\n")
                elif nxt == "r":
                    result.append("\r")
                elif nxt == "t":
                    result.append("\t")
                elif nxt == '"':
                    result.append('"')
                elif nxt == "\\":
                    result.append("\\")
                else:
                    result.append(s[i])
                    result.append(nxt)
                i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)
