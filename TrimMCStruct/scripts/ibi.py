"""
.ibi 文件格式插件 (IBI Import Package)

支持读取和写入 IBI 导入包格式。
IBI 格式包含两段加密数据：第一段为 setblock 指令文本，第二段为命令方块 JSON。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import base64
import io
import json
import random
import re
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class IBIPlugin(IPlugin):
    """
    .ibi 文件格式插件

    IBI 是基岩版导入包格式，包含两段加密数据：
    - 第一段：setblock 指令文本（普通方块）
    - 第二段：命令方块 JSON 数据
    """

    @property
    def name(self) -> str:
        return "ibi"

    @property
    def extensions(self) -> list[str]:
        return [".ibi"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        magic = file_obj.read(9)
        if magic != b"IBImport ":
            raise ValueError("不是有效的 IBI 文件")

        data = file_obj.read()
        segments = cls._decode_varint_segments(data)

        if len(segments) < 1:
            raise ValueError("IBI 文件中没有有效数据段")

        txt_content = segments[0].decode("utf-8", errors="replace")
        json_content = []
        if len(segments) >= 2:
            try:
                json_content = json.loads(segments[1].decode("utf-8", errors="replace"))
            except Exception:
                pass

        return cls._parse_ibI(txt_content, json_content)

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        txt_lines = []
        json_list = []
        title_counter = 1

        sx, sy, sz = struct.size

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

                    txt_lines.append(f"setblock ~{x} ~{y} ~{z} {name}{state_str}")

                    idx = x * sz * sy + y * sz + z
                    nbt_data = struct._special_blocks.get(idx)
                    if nbt_data and nbt_data.get("id") == "CommandBlock":
                        cmd = nbt_data.get("Command", "")
                        title = nbt_data.get("CustomName", "")
                        encoded_cmd = base64.b64encode(cmd.encode("utf-8")).decode("utf-8")
                        encoded_title = base64.b64encode(str(title_counter).encode("utf-8")).decode("utf-8")
                        title_counter += 1

                        mode = 0
                        if "repeating" in name.lower():
                            mode = 2
                        elif "chain" in name.lower():
                            mode = 1

                        json_list.append({
                            "posX": f"~{x}",
                            "posY": f"~{y}",
                            "posZ": f"~{z}",
                            "CommandMessage": encoded_cmd,
                            "Commandtitle": encoded_title,
                            "mode": mode,
                            "isTime": nbt_data.get("TickDelay", 0),
                            "Conditional": nbt_data.get("conditionalMode", False),
                            "isRedstone": not bool(nbt_data.get("auto", 1)),
                        })

        txt_content = "\n".join(txt_lines)
        json_bytes = json.dumps(json_list, ensure_ascii=False, indent=4).encode("utf-8")

        def encrypt_and_write(data: bytes, out_f, first: bool):
            key = random.randint(1, 255)
            encrypted = bytes([b ^ key for b in data])
            if first:
                out_f.write(b"IBImport ")
            out_f.write(cls._encode_varint(len(encrypted)))
            out_f.write(bytes([key]))
            out_f.write(encrypted)

        encrypt_and_write(txt_content.encode("utf-8"), file_obj, first=True)
        encrypt_and_write(json_bytes, file_obj, first=False)

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        with open(path, "wb") as f:
            self.dump(struct, f)

    @classmethod
    def _parse_ibI(cls, txt_content: str, json_content: list) -> MatrixStructure:
        """解析 IBI 内容，返回 MatrixStructure"""
        lines = txt_content.splitlines()
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
        struct = MatrixStructure(size)
        struct._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        for x, y, z, block_name, state_str in blocks:
            lx = x - min_x
            ly = y - min_y
            lz = z - min_z
            states = cls._parse_state_str(state_str)
            block = Block("minecraft", block_name, states, compability_version=COMPABILITY_VERSION)
            struct.set_block((lx, ly, lz), block)

        for item in json_content:
            px = int(item.get("posX", "~0")[1:]) if item.get("posX", "~0").startswith("~") else int(item.get("posX", 0))
            py = int(item.get("posY", "~0")[1:]) if item.get("posY", "~0").startswith("~") else int(item.get("posY", 0))
            pz = int(item.get("posZ", "~0")[1:]) if item.get("posZ", "~0").startswith("~") else int(item.get("posZ", 0))

            lx = px - min_x
            ly = py - min_y
            lz = pz - min_z

            if not (0 <= lx < size[0] and 0 <= ly < size[1] and 0 <= lz < size[2]):
                continue

            block = struct.get_block((lx, ly, lz))
            if block is None or "command_block" not in block.base_name.lower():
                continue

            try:
                cmd = base64.b64decode(item.get("CommandMessage", "")).decode("utf-8")
            except Exception:
                cmd = ""
            try:
                title = base64.b64decode(item.get("Commandtitle", "")).decode("utf-8")
            except Exception:
                title = ""

            mode = item.get("mode", 0)
            nbt_data = {
                "id": "CommandBlock",
                "Command": cmd,
                "CustomName": title,
                "auto": 1 if item.get("isRedstone", True) else 0,
                "TickDelay": item.get("isTime", 0),
                "conditionalMode": item.get("Conditional", False),
                "TrackOutput": 1,
                "ExecuteOnFirstTick": 1,
                "Version": 19,
            }
            idx = lx * size[2] * size[1] + ly * size[2] + lz
            struct._special_blocks[idx] = nbt_data

        return struct

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

    @classmethod
    def _decode_varint_segments(cls, data: bytes) -> list:
        segments = []
        offset = 0
        while offset < len(data):
            result = 0
            shift = 0
            while True:
                if offset >= len(data):
                    break
                b = data[offset]
                offset += 1
                result |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
                if shift >= 35:
                    break
            if offset >= len(data):
                break
            key = data[offset]
            offset += 1
            seg_len = result
            if offset + seg_len > len(data):
                break
            encrypted = data[offset:offset + seg_len]
            offset += seg_len
            decrypted = bytes([b ^ key for b in encrypted])
            segments.append(decrypted)
        return segments

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        out = []
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                byte |= 0x80
            out.append(byte)
            if not value:
                break
        return bytes(out)
