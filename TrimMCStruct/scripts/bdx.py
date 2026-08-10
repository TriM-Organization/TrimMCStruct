"""
.bdx 文件格式插件 (Bedrock Exchange Format)

支持读取 .bdx 文件，写入 .bdx 文件。
BDX 格式使用 brotli 压缩，内部为自定义操作码序列。

代码来源：BDX 格式的操作码定义和编解码逻辑参考了
Exchange Tool 源码 (package/MCStructureManage/StructureBDX/)，
由 TriM-Organization 开发者改编为插件式架构。
原项目地址: https://gitee.com/TriM-Organization/mcstructure
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import io
import re
import struct

import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class BDXPlugin(IPlugin):
    """
    .bdx 文件格式插件

    BDX 是 Bedrock 自定义格式，使用 brotli 压缩。
    支持命令方块数据的完整保留。
    """

    @property
    def name(self) -> str:
        return "bdx"

    @property
    def extensions(self) -> list[str]:
        return [".bdx"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        # brotli 是可选依赖，仅在处理 BDX 格式时需要，故在此处导入并做异常处理
        try:
            import brotli
        except ImportError:
            raise ImportError("请安装 brotli 库: pip install brotli")

        magic = file_obj.read(3)
        if magic != b"BD@":
            raise ValueError("不是有效的 BDX 文件")

        compressed = file_obj.read()
        try:
            decompressed = brotli.decompress(compressed)
        except Exception as e:
            raise ValueError(f"BDX 解压失败: {e}")

        if decompressed[0:4] != b"BDX\x00":
            raise ValueError("不是有效的 BDX 数据")

        return cls._parse_bdx(decompressed)

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        # brotli 是可选依赖，仅在处理 BDX 格式时需要，故在此处导入并做异常处理
        try:
            import brotli
        except ImportError:
            raise ImportError("请安装 brotli 库: pip install brotli")

        data = self._build_bdx(struct)
        compressed = brotli.compress(data)
        file_obj.write(b"BD@")
        file_obj.write(compressed)

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        with open(path, "wb") as f:
            self.dump(struct, f)

    @classmethod
    def _parse_bdx(cls, data: bytes) -> MatrixStructure:
        """解析 BDX 数据，返回 MatrixStructure"""
        if data[0:4] != b"BDX\x00":
            raise ValueError("无效的 BDX 数据头")

        pos = 4
        const_str = []
        operations = []

        while pos < len(data):
            op_code = data[pos]
            pos += 1

            if op_code == 0x00:
                str_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                s = data[pos:pos + str_len].decode("utf-8")
                pos += str_len
                const_str.append(s)

            elif op_code == 0x05:
                block_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                state_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                operations.append(("place_block_states1", block_id, state_id, x, y, z))

            elif op_code == 0x07:
                block_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                block_data = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                operations.append(("place_block", block_id, block_data, x, y, z))

            elif op_code == 0x0D:
                block_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                state_str_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                state_str = data[pos:pos + state_str_len].decode("utf-8")
                pos += state_str_len
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                operations.append(("place_block_states2", block_id, state_str, x, y, z))

            elif op_code == 0x1A:
                mode = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                cmd_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                cmd = data[pos:pos + cmd_len].decode("utf-8")
                pos += cmd_len
                ttl_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                ttl = data[pos:pos + ttl_len].decode("utf-8")
                pos += ttl_len
                flags = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                tick_delay = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                operations.append(("set_command_block", mode, x, y, z, cmd, ttl, flags, tick_delay))

            elif op_code == 0x1B:
                block_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                block_data = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                mode = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                cmd_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                cmd = data[pos:pos + cmd_len].decode("utf-8")
                pos += cmd_len
                ttl_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                ttl = data[pos:pos + ttl_len].decode("utf-8")
                pos += ttl_len
                flags = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                tick_delay = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                operations.append(("place_block_cmd", block_id, block_data, mode, x, y, z, cmd, ttl, flags, tick_delay))

            elif op_code == 0x20:
                runtime_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                operations.append(("place_runtime", runtime_id, x, y, z))

            elif op_code == 0x22:
                runtime_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                mode = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                cmd_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                cmd = data[pos:pos + cmd_len].decode("utf-8")
                pos += cmd_len
                ttl_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                ttl = data[pos:pos + ttl_len].decode("utf-8")
                pos += ttl_len
                flags = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                tick_delay = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                operations.append(("place_runtime_cmd", runtime_id, mode, x, y, z, cmd, ttl, flags, tick_delay))

            elif op_code == 0x24:
                mode = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                cmd_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                cmd = data[pos:pos + cmd_len].decode("utf-8")
                pos += cmd_len
                ttl_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                ttl = data[pos:pos + ttl_len].decode("utf-8")
                pos += ttl_len
                flags = struct.unpack_from("<B", data, pos)[0]
                pos += 1
                tick_delay = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                operations.append(("place_cmd_block", mode, x, y, z, cmd, ttl, flags, tick_delay))

            elif op_code == 0x29:
                block_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                state_id = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                x, y, z = struct.unpack_from("<HHH", data, pos)
                pos += 6
                nbt_len = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                nbt_data = data[pos:pos + nbt_len]
                pos += nbt_len
                operations.append(("place_nbt", block_id, state_id, x, y, z, nbt_data))

            elif op_code in (0x01, 0x02, 0x03, 0x04, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C):
                val = struct.unpack_from("<h", data, pos)[0]
                pos += 2
                if op_code == 0x01:
                    operations.append(("add_x", val))
                elif op_code == 0x02:
                    operations.append(("sub_x", val))
                elif op_code == 0x03:
                    operations.append(("add_y", val))
                elif op_code == 0x04:
                    operations.append(("sub_y", val))
                elif op_code == 0x06:
                    operations.append(("add_z", val))
                elif op_code == 0x08:
                    operations.append(("sub_z", val))
                elif op_code == 0x09:
                    operations.append(("add_x", val))
                elif op_code == 0x0A:
                    operations.append(("sub_x", val))
                elif op_code == 0x0B:
                    operations.append(("add_y", val))
                elif op_code == 0x0C:
                    operations.append(("sub_y", val))
                elif op_code == 0x0D:
                    operations.append(("add_z", val))

            elif op_code in (0x1C, 0x1D, 0x1E, 0x1F, 0x21, 0x23):
                val = struct.unpack_from("<i", data, pos)[0]
                pos += 4
                if op_code == 0x1C:
                    operations.append(("add_x32", val))
                elif op_code == 0x1D:
                    operations.append(("sub_x32", val))
                elif op_code == 0x1E:
                    operations.append(("add_y32", val))
                elif op_code == 0x1F:
                    operations.append(("sub_y32", val))
                elif op_code == 0x21:
                    operations.append(("add_z32", val))
                elif op_code == 0x23:
                    operations.append(("sub_z32", val))

            elif op_code == 0x27:
                pos += 1
                pass
            else:
                break

        if not operations:
            return MatrixStructure((0, 0, 0))

        min_x = min(op[3] for op in operations if len(op) > 3 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))
        min_y = min(op[4] for op in operations if len(op) > 4 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))
        min_z = min(op[5] for op in operations if len(op) > 5 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))

        max_x = max(op[3] for op in operations if len(op) > 3 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))
        max_y = max(op[4] for op in operations if len(op) > 4 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))
        max_z = max(op[5] for op in operations if len(op) > 5 and op[0] in ("place_block_states1", "place_block", "place_block_states2", "set_command_block", "place_block_cmd", "place_runtime", "place_runtime_cmd", "place_cmd_block", "place_nbt"))

        size = (max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1)
        struct_obj = MatrixStructure(size)
        struct_obj._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        command_block_ids = ["minecraft:command_block", "minecraft:repeating_command_block", "minecraft:chain_command_block"]
        runtime_id_map = cls._get_runtime_id_map()

        for op in operations:
            if op[0] in ("place_block_states1",):
                idx = op[1]
                state_idx = op[2]
                x, y, z = op[3], op[4], op[5]
                name = const_str[idx] if idx < len(const_str) else f"unknown_{idx}"
                states = cls._parse_bdx_states(const_str[state_idx] if state_idx < len(const_str) else "")
                block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)

            elif op[0] in ("place_block",):
                idx = op[1]
                data_val = op[2]
                x, y, z = op[3], op[4], op[5]
                name = const_str[idx] if idx < len(const_str) else f"unknown_{idx}"
                states = cls._data_value_to_states(name, data_val)
                block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)

            elif op[0] in ("place_block_states2",):
                idx = op[1]
                state_str = op[2]
                x, y, z = op[3], op[4], op[5]
                name = const_str[idx] if idx < len(const_str) else f"unknown_{idx}"
                states = cls._parse_bdx_states(state_str)
                block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)

            elif op[0] in ("set_command_block",):
                mode = op[1]
                x, y, z = op[2], op[3], op[4]
                cmd = op[5]
                ttl = op[6]
                flags = op[7]
                tick_delay = op[8]
                block = Block(command_block_ids[mode], {"conditional_bit": bool(flags & 1)}, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)
                nbt = {
                    "id": "CommandBlock",
                    "Command": cmd,
                    "CustomName": ttl,
                    "auto": 1 if not (flags & 2) else 0,
                    "TickDelay": tick_delay,
                    "conditionalMode": bool(flags & 1),
                    "TrackOutput": 1,
                    "ExecuteOnFirstTick": 1,
                    "Version": 38 if "execute" in cmd.lower() else 19,
                }
                idx = (x - min_x) * size[2] * size[1] + (y - min_y) * size[2] + (z - min_z)
                struct_obj._special_blocks[idx] = nbt

            elif op[0] in ("place_block_cmd",):
                idx = op[1]
                data_val = op[2]
                mode = op[3]
                x, y, z = op[4], op[5], op[6]
                cmd = op[7]
                ttl = op[8]
                flags = op[9]
                tick_delay = op[10]
                name = const_str[idx] if idx < len(const_str) else f"unknown_{idx}"
                states = cls._data_value_to_states(name, data_val)
                block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)
                cmd_block = Block(command_block_ids[mode], {"conditional_bit": bool(flags & 1)}, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), cmd_block)
                nbt = {
                    "id": "CommandBlock",
                    "Command": cmd,
                    "CustomName": ttl,
                    "auto": 1 if not (flags & 2) else 0,
                    "TickDelay": tick_delay,
                    "conditionalMode": bool(flags & 1),
                    "TrackOutput": 1,
                    "ExecuteOnFirstTick": 1,
                    "Version": 38 if "execute" in cmd.lower() else 19,
                }
                idx = (x - min_x) * size[2] * size[1] + (y - min_y) * size[2] + (z - min_z)
                struct_obj._special_blocks[idx] = nbt

            elif op[0] in ("place_runtime",):
                runtime_id = op[1]
                x, y, z = op[2], op[3], op[4]
                if runtime_id in runtime_id_map:
                    name, data = runtime_id_map[runtime_id]
                    states = cls._data_value_to_states(name, data)
                    block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                    struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)

            elif op[0] in ("place_runtime_cmd",):
                runtime_id = op[1]
                mode = op[2]
                x, y, z = op[3], op[4], op[5]
                cmd = op[6]
                ttl = op[7]
                flags = op[8]
                tick_delay = op[9]
                if runtime_id in runtime_id_map:
                    name, data = runtime_id_map[runtime_id]
                    states = cls._data_value_to_states(name, data)
                    block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                    struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)
                cmd_block = Block(command_block_ids[mode], {"conditional_bit": bool(flags & 1)}, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), cmd_block)
                nbt = {
                    "id": "CommandBlock",
                    "Command": cmd,
                    "CustomName": ttl,
                    "auto": 1 if not (flags & 2) else 0,
                    "TickDelay": tick_delay,
                    "conditionalMode": bool(flags & 1),
                    "TrackOutput": 1,
                    "ExecuteOnFirstTick": 1,
                    "Version": 38 if "execute" in cmd.lower() else 19,
                }
                idx = (x - min_x) * size[2] * size[1] + (y - min_y) * size[2] + (z - min_z)
                struct_obj._special_blocks[idx] = nbt

            elif op[0] in ("place_cmd_block",):
                mode = op[1]
                x, y, z = op[2], op[3], op[4]
                cmd = op[5]
                ttl = op[6]
                flags = op[7]
                tick_delay = op[8]
                block = Block(command_block_ids[mode], {"conditional_bit": bool(flags & 1)}, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)
                nbt = {
                    "id": "CommandBlock",
                    "Command": cmd,
                    "CustomName": ttl,
                    "auto": 1 if not (flags & 2) else 0,
                    "TickDelay": tick_delay,
                    "conditionalMode": bool(flags & 1),
                    "TrackOutput": 1,
                    "ExecuteOnFirstTick": 1,
                    "Version": 19,
                }
                idx = (x - min_x) * size[2] * size[1] + (y - min_y) * size[2] + (z - min_z)
                struct_obj._special_blocks[idx] = nbt

            elif op[0] in ("place_nbt",):
                idx = op[1]
                state_idx = op[2]
                x, y, z = op[3], op[4], op[5]
                nbt_data = op[6]
                name = const_str[idx] if idx < len(const_str) else f"unknown_{idx}"
                states = cls._parse_bdx_states(const_str[state_idx] if state_idx < len(const_str) else "")
                block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
                struct_obj.set_block((x - min_x, y - min_y, z - min_z), block)
                try:
                    nbt_obj = cls._parse_nbt_bytes(nbt_data)
                    if nbt_obj:
                        idx = (x - min_x) * size[2] * size[1] + (y - min_y) * size[2] + (z - min_z)
                        struct_obj._special_blocks[idx] = nbt_obj
                except Exception:
                    pass

        return struct_obj

    @classmethod
    def _build_bdx(cls, struct: MatrixStructure) -> bytes:
        """将 MatrixStructure 编码为 BDX 数据"""
        sx, sy, sz = struct.size
        pos = 4
        data = io.BytesIO()
        data.write(b"BDX\x00")

        const_str = []
        block_idx_map = {}

        for block in struct._palette:
            name = block.base_name
            state = block.states
            if name not in block_idx_map:
                block_idx_map[name] = len(const_str)
                const_str.append(name)
            idx = block_idx_map[name]
            if state:
                state_str = cls._states_to_bdx_str(state)
                if state_str not in block_idx_map:
                    block_idx_map[state_str] = len(const_str)
                    const_str.append(state_str)
                state_idx = block_idx_map[state_str]
            else:
                state_idx = 0

            for x in range(sx):
                for y in range(sy):
                    for z in range(sz):
                        b = struct.get_block((x, y, z))
                        if b is None or b.base_name == "air":
                            continue
                        bidx = struct._add_block_to_palette(b)
                        nbt_data = None
                        block_idx = x * sz * sy + y * sz + z
                        if block_idx in struct._special_blocks:
                            nbt_data = struct._special_blocks[block_idx]
                        if nbt_data:
                            data.write(struct.pack("<B", 0x29))
                            data.write(struct.pack("<H", idx))
                            data.write(struct.pack("<H", state_idx))
                            data.write(struct.pack("<HHH", x, y, z))
                            nbt_bytes = cls._nbt_to_bytes(nbt_data)
                            data.write(struct.pack("<I", len(nbt_bytes)))
                            data.write(nbt_bytes)
                        else:
                            data.write(struct.pack("<B", 0x05))
                            data.write(struct.pack("<H", idx))
                            data.write(struct.pack("<H", state_idx))
                            data.write(struct.pack("<HHH", x, y, z))

        for s in const_str:
            encoded = s.encode("utf-8")
            data.write(struct.pack("<B", 0x00))
            data.write(struct.pack("<H", len(encoded)))
            data.write(encoded)

        return data.getvalue()

    @staticmethod
    def _get_runtime_id_map() -> dict:
        return {
            0: ("air", 0), 1: ("stone", 0), 2: ("grass", 0), 3: ("dirt", 0),
            4: ("cobblestone", 0), 5: ("planks", 0), 14: ("gold_ore", 0),
            15: ("iron_ore", 0), 16: ("coal_ore", 0), 17: ("log", 0),
            18: ("leaves", 0), 48: ("chest", 0), 50: ("command_block", 0),
            54: ("redstone_wire", 0), 55: ("diamond_ore", 0), 56: ("diamond_block", 0),
            57: ("crafting_table", 0), 60: ("furnace", 0), 61: ("lit_furnace", 0),
            72: ("redstone_ore", 0), 73: ("lit_redstone_ore", 0),
            74: ("unlit_redstone_torch", 0), 75: ("redstone_torch", 0),
            119: ("command_block", 0), 143: ("melon", 0),
        }

    @staticmethod
    def _parse_bdx_states(state_str: str) -> dict:
        states = {}
        if not state_str:
            return states
        pattern = re.compile(r'"?(\w+)"?\s*=\s*"([^"]*)"|"?(\w+)"?\s*=\s*(true|false|\d+)')
        for m in pattern.finditer(state_str):
            if m.group(1):
                states[m.group(1)] = m.group(2)
            elif m.group(3):
                val = m.group(4)
                if val == "true":
                    states[m.group(3)] = True
                elif val == "false":
                    states[m.group(3)] = False
                else:
                    try:
                        states[m.group(3)] = int(val)
                    except ValueError:
                        states[m.group(3)] = val
        return states

    @staticmethod
    def _data_value_to_states(block_name: str, data_val: int) -> dict:
        states = {}
        if block_name in ("wool", "carpet"):
            states["color"] = str(data_val)
        elif block_name in ("log", "log2"):
            states["axis"] = str(data_val & 3)
        elif block_name == "stone_slab":
            states["type"] = str(data_val)
        elif block_name == "sandstone":
            states["type"] = str(data_val)
        elif block_name == "stone_brick":
            states["type"] = str(data_val)
        elif block_name == "redstone_wire":
            states["power"] = str(data_val)
        elif block_name == "lever":
            states["facing_direction"] = str(data_val & 7)
            states["attached_bit"] = bool(data_val & 8)
        elif block_name == "snow":
            states["layers"] = str(min(data_val, 8))
        elif block_name == "command_block":
            states["conditional_bit"] = bool(data_val & 1)
        return states

    @staticmethod
    def _states_to_bdx_str(states: dict) -> str:
        parts = []
        for k, v in sorted(states.items()):
            if isinstance(v, bool):
                parts.append(f'"{k}"={"true" if v else "false"}')
            elif isinstance(v, str):
                parts.append(f'"{k}"="{v}"')
            else:
                parts.append(f'"{k}"={v}')
        return "[" + ",".join(parts) + "]"

    @staticmethod
    def _parse_nbt_bytes(data: bytes) -> dict | None:
        try:
            buf = io.BytesIO(data)
            nbt_obj = nbtlib.load(buf, gzipped=False)
            return dict(nbt_obj.root)
        except Exception:
            return None

    @staticmethod
    def _nbt_to_bytes(nbt_data: dict) -> bytes:
        try:
            buf = io.BytesIO()
            nbtlib.File(nbtlib.Compound(nbt_data)).save(buf, gzipped=False)
            return buf.getvalue()
        except Exception:
            return b""
