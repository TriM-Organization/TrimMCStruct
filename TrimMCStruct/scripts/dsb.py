"""
.dsb 文件格式插件 (DSB Structure)

支持读取和写入 DSB 结构文件格式。
DSB 格式包含二进制头部和 JSON 数据负载。
支持命令方块数据的完整保留。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import json
import re
import struct as _struct

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class DSBPlugin(IPlugin):
    """
    .dsb 文件格式插件

    DSB 是自定义二进制格式，包含：
    - 17字节头部 (DSB! magic + 元数据)
    - JSON 数据负载
    """

    @property
    def name(self) -> str:
        return "dsb"

    @property
    def extensions(self) -> list[str]:
        return [".dsb"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        header = file_obj.read(17)
        if len(header) < 17:
            raise ValueError("DSB 文件头部不完整")

        magic, ver, comp, enc, uncomp_size, comp_size, flag = _struct.unpack("<4sBBHIIB", header)
        if magic != b"DSB!":
            raise ValueError("不是有效的 DSB 文件")

        json_data = file_obj.read(uncomp_size).decode("utf-8")
        data = json.loads(json_data)

        blocks = data.get("blocks", [])
        cbs = data.get("cbs", [])

        if not blocks:
            return MatrixStructure((0, 0, 0))

        min_x = min(b.get("x", 0) for b in blocks)
        min_y = min(b.get("y", 0) for b in blocks)
        min_z = min(b.get("z", 0) for b in blocks)
        max_x = max(b.get("x", 0) for b in blocks)
        max_y = max(b.get("y", 0) for b in blocks)
        max_z = max(b.get("z", 0) for b in blocks)

        size = (max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1)
        struct_obj = MatrixStructure(size)
        struct_obj._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        cb_map = {}
        for cb in cbs:
            pos = (cb.get("x", 0), cb.get("y", 0), cb.get("z", 0))
            cb_map[pos] = cb

        for b in blocks:
            x = b.get("x", 0)
            y = b.get("y", 0)
            z = b.get("z", 0)
            lx = x - min_x
            ly = y - min_y
            lz = z - min_z

            block_id = b.get("id", "minecraft:stone")
            state_str = b.get("st", "")
            states = cls._parse_state_str(state_str)
            block = Block("minecraft", block_id, states, compability_version=COMPABILITY_VERSION)
            struct_obj.set_block((lx, ly, lz), block)

            if (x, y, z) in cb_map:
                cb = cb_map[(x, y, z)]
                cmd_data = {
                    "id": "CommandBlock",
                    "Command": cb.get("cmd", ""),
                    "CustomName": cb.get("ttl", ""),
                    "auto": 1 if cb.get("rs", True) else 0,
                    "TickDelay": cb.get("dl", 0),
                    "conditionalMode": cb.get("cond", False),
                    "TrackOutput": 1,
                    "ExecuteOnFirstTick": 1,
                    "Version": 19,
                }
                idx = lx * size[2] * size[1] + ly * size[2] + lz
                struct_obj._special_blocks[idx] = cmd_data

        return struct_obj

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        blocks = []
        cbs = []
        sx, sy, sz = struct.size

        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        continue

                    state_str = self._states_to_str(block.states)
                    blocks.append({
                        "x": x,
                        "y": y,
                        "z": z,
                        "id": block.identifier,
                        "st": state_str,
                        "da": 0,
                    })

                    block_idx = x * sz * sy + y * sz + z
                    nbt_data = struct._special_blocks.get(block_idx)
                    if isinstance(nbt_data, dict) and nbt_data.get("id") == "CommandBlock":
                        mode = 0
                        if "repeating" in block.base_name.lower():
                            mode = 1
                        elif "chain" in block.base_name.lower():
                            mode = 2
                        cbs.append({
                            "x": x,
                            "y": y,
                            "z": z,
                            "id": block.identifier,
                            "st": state_str,
                            "mo": mode,
                            "cmd": nbt_data.get("Command", ""),
                            "ttl": nbt_data.get("CustomName", ""),
                            "cond": nbt_data.get("conditionalMode", False),
                            "rs": bool(nbt_data.get("auto", 1)),
                            "dl": nbt_data.get("TickDelay", 0),
                            "trk": True,
                            "eof": False,
                        })

        dsb_data = {
            "ver": 1,
            "author": "",
            "blocks": blocks,
            "cbs": cbs,
        }
        json_str = json.dumps(dsb_data, ensure_ascii=False, separators=(",", ":"))
        payload = json_str.encode("utf-8")
        header = _struct.pack("<4sBBHIIB", b"DSB!", 1, 0, 0, len(payload), 0, 0)
        file_obj.write(header + payload)

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        with open(path, "wb") as f:
            self.dump(struct, f)

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
    def _states_to_str(states: dict) -> str:
        if not states:
            return ""
        parts = []
        for k, v in sorted(states.items()):
            if isinstance(v, bool):
                parts.append(f'"{k}"={"true" if v else "false"}')
            elif isinstance(v, str):
                parts.append(f'"{k}"="{v}"')
            else:
                parts.append(f'"{k}"={v}')
        return "[" + ",".join(parts) + "]"
