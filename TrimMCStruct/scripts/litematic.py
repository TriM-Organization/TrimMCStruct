"""
.litematic 文件格式插件 (Litematica Projection)

支持读取和写入 Litematica 投影文件格式。
Litematic 是 Litematica 模组的结构存档格式，使用 gzip 压缩的 NBT。
支持基岩版坐标转换。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import gzip
import math
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class LitematicPlugin(IPlugin):
    """
    .litematic 文件格式插件

    支持 Litematica 投影文件格式。
    文件包含区域信息、方块调色板和方块状态数据。
    """

    @property
    def name(self) -> str:
        return "litematic"

    @property
    def extensions(self) -> list[str]:
        return [".litematic"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        if hasattr(file_obj, 'mode') and 'b' in getattr(file_obj, 'mode', ''):
            file_obj = gzip.GzipFile(fileobj=file_obj)
        nbt = nbtlib.File.from_fileobj(file_obj, byteorder="big")
        root = nbt

        if "Regions" not in root:
            raise ValueError("不是有效的 .litematic 文件")

        regions = root["Regions"]
        if not regions:
            return MatrixStructure((0, 0, 0))

        region_names = list(regions.keys())
        region_name = region_names[0]
        region = regions[region_name]

        pos1 = (int(region["Position"]["x"]), int(region["Position"]["y"]), int(region["Position"]["z"]))
        size = (int(region["Size"]["x"]), int(region["Size"]["y"]), int(region["Size"]["z"]))

        if size[0] < 0:
            pos1 = (pos1[0] + size[0], pos1[1], pos1[2])
            size = (-size[0], size[1], size[2])
        if size[1] < 0:
            pos1 = (pos1[0], pos1[1] + size[1], pos1[2])
            size = (size[0], -size[1], size[2])
        if size[2] < 0:
            pos1 = (pos1[0], pos1[1], pos1[2] + size[2])
            size = (size[0], size[1], -size[2])

        sx, sy, sz = size
        struct = MatrixStructure(size)
        struct._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        palette = region["BlockStatePalette"]
        for i, block_data in enumerate(palette):
            block_name = str(block_data["Name"])
            props = {}
            if "Properties" in block_data:
                for k, v in block_data["Properties"].items():
                    val = str(v)
                    if val == "true":
                        props[k] = True
                    elif val == "false":
                        props[k] = False
                    else:
                        try:
                            props[k] = int(val)
                        except ValueError:
                            props[k] = val
            block = Block("minecraft", block_name, props, compability_version=COMPABILITY_VERSION)
            struct._palette.append(block)

        block_states = region["BlockStates"]
        bits_per_block = max(2, math.ceil(math.log2(len(palette)))) if palette else 2
        total_bits = bits_per_block * len(block_states)

        for i in range(len(block_states)):
            byte_val = int(block_states[i])
            for bit in range(8):
                if i * 8 + bit >= total_bits:
                    break
                idx = (byte_val >> bit) & 0xFF
                if idx == 0:
                    continue
                if idx >= len(struct._palette):
                    continue
                block = struct._palette[idx].copy()
                lx = (i * 8 + bit) % sx
                ly = ((i * 8 + bit) // sx) % sy
                lz = (i * 8 + bit) // (sx * sy)
                if 0 <= lx < sx and 0 <= ly < sy and 0 <= lz < sz:
                    struct.set_block((lx, ly, lz), block)

        tile_entities = region.get("TileEntities", [])
        for te in tile_entities:
            x = int(te["x"]) - pos1[0]
            y = int(te["y"]) - pos1[1]
            z = int(te["z"]) - pos1[2]
            if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
                idx = x * sz * sy + y * sz + z
                struct._special_blocks[idx] = dict(te)

        return struct

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        nbt_root = self._struct_to_nbt(struct)
        nbtlib.File(nbt_root).save(file_obj, gzipped=True, byteorder="big")

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        nbt_root = self._struct_to_nbt(struct)
        nbtlib.File(nbt_root).save(path, gzipped=True, byteorder="big")

    def _struct_to_nbt(self, struct: MatrixStructure) -> nbtlib.Compound:
        sx, sy, sz = struct.size
        size = struct.size

        palette_list = []
        palette_map = {}

        for i, block in enumerate(struct._palette):
            if block.base_name == "air":
                continue
            palette_map[block] = i
            props = {}
            if block.states:
                for k, v in block.states.items():
                    if isinstance(v, bool):
                        props[k] = "true" if v else "false"
                    else:
                        props[k] = str(v)
            entry = nbtlib.Compound({
                "Name": nbtlib.String(block.identifier),
            })
            if props:
                entry["Properties"] = nbtlib.Compound({
                    k: nbtlib.String(v) for k, v in props.items()
                })
            palette_list.append(entry)

        block_states = bytearray()
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        continue
                    idx = palette_map.get(block, 0)
                    block_states.append(idx)

        bits_per_block = max(2, math.ceil(math.log2(len(palette_list) + 1))) if palette_list else 2
        total_bits = bits_per_block * len(block_states)
        longs_needed = (total_bits + 63) // 64

        long_array = [0] * longs_needed
        MASK64 = 0xFFFFFFFFFFFFFFFF

        for i, palette_id in enumerate(block_states):
            bit_start = i * bits_per_block
            long_idx = bit_start // 64
            bit_offset = bit_start % 64
            mask = (1 << bits_per_block) - 1
            value = palette_id & mask
            remaining = 64 - bit_offset
            if remaining >= bits_per_block:
                long_array[long_idx] = (long_array[long_idx] | (value << bit_offset)) & MASK64
            else:
                long_array[long_idx] = (long_array[long_idx] | (value << bit_offset)) & MASK64
                long_array[long_idx + 1] = (long_array[long_idx + 1] | (value >> remaining)) & MASK64

        signed_long_array = []
        for v in long_array:
            if v >= 0x8000000000000000:
                v -= 0x10000000000000000
            signed_long_array.append(v)

        block_states_nbt = nbtlib.LongArray(signed_long_array)

        block_entities = nbtlib.List([])
        for idx, nbt_data in struct._special_blocks.items():
            x = idx % sx
            y = (idx // sx) % sy
            z = idx // (sx * sy)
            if isinstance(nbt_data, dict):
                block_entities.append(nbtlib.Compound({
                    "x": nbtlib.Int(x),
                    "y": nbtlib.Int(y),
                    "z": nbtlib.Int(z),
                    **{k: nbtlib.String(str(v)) if isinstance(v, str) else nbtlib.Int(int(v)) for k, v in nbt_data.items() if k != "id"}
                }))

        region_nbt = nbtlib.Compound({
            "Position": nbtlib.Compound({
                "x": nbtlib.Int(0),
                "y": nbtlib.Int(0),
                "z": nbtlib.Int(0),
            }),
            "Size": nbtlib.Compound({
                "x": nbtlib.Int(sx),
                "y": nbtlib.Int(sy),
                "z": nbtlib.Int(sz),
            }),
            "BlockStatePalette": nbtlib.List(palette_list),
            "BlockStates": block_states_nbt,
            "TileEntities": block_entities,
            "Entities": nbtlib.List([]),
        })

        metadata_nbt = nbtlib.Compound({
            "Name": nbtlib.String("TrimMCStruct"),
            "Author": nbtlib.String("TrimMCStruct"),
            "Description": nbtlib.String("Converted by TrimMCStruct"),
            "RegionCount": nbtlib.Int(1),
            "TotalVolume": nbtlib.Int(sx * sy * sz),
            "TotalBlocks": nbtlib.Int(sum(1 for b in block_states if b != 0)),
            "TimeCreated": nbtlib.Long(0),
            "TimeModified": nbtlib.Long(0),
            "EnclosingSize": nbtlib.Compound({
                "x": nbtlib.Int(sx),
                "y": nbtlib.Int(sy),
                "z": nbtlib.Int(sz),
            }),
        })

        nbt_root = nbtlib.Compound({
            "Version": nbtlib.Int(1),
            "MinecraftDataVersion": nbtlib.Int(2586),
            "Metadata": metadata_nbt,
            "Regions": nbtlib.Compound({
                "TrimMCStruct": region_nbt,
            }),
        })
        return nbt_root
