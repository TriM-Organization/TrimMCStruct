"""
.schem 文件格式插件 (Sponge Schematic)

支持读取和写入 Sponge 格式的 .schem 文件。
文件格式参考: https://github.com/SpongePowered/Schematic-Specification
支持 V1 (BlockData) 和 V2/V3 (Blocks) 格式。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import gzip
import math
import struct
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class SchemPlugin(IPlugin):
    """
    .schem 文件格式插件

    支持 Sponge Schematic 格式 (V1/V2/V3)。
    文件包含方块调色板、方块状态编码和可选的方块实体NBT。
    """

    @property
    def name(self) -> str:
        return "schem"

    @property
    def extensions(self) -> list[str]:
        return [".schem"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        if hasattr(file_obj, 'mode') and 'b' in getattr(file_obj, 'mode', ''):
            file_obj = gzip.GzipFile(fileobj=file_obj)
        nbt = nbtlib.File.from_fileobj(file_obj)
        root = nbt

        if "Schematic" in root:
            nbt = root["Schematic"]

        if "BlockData" in nbt:
            return cls._load_v1(nbt)
        elif "Blocks" in nbt:
            return cls._load_v2(nbt)
        else:
            raise ValueError("无法识别的 .schem 文件格式")

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        nbt_root = self._struct_to_nbt(struct)
        nbtlib.File(nbt_root).save(file_obj, gzipped=True)

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        nbt_root = self._struct_to_nbt(struct)
        nbtlib.File(nbt_root).save(path, gzipped=True)

    @classmethod
    def _load_v1(cls, nbt: nbtlib.Compound) -> MatrixStructure:
        """加载 Sponge Schematic V1 (BlockData)"""
        sx = int(nbt["Width"])
        sy = int(nbt["Height"])
        sz = int(nbt["Length"])
        size = (sx, sy, sz)

        struct_obj = MatrixStructure(size)
        struct_obj._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        palette = nbt["Palette"]
        block_data = nbt["BlockData"]

        for i, (key, val) in enumerate(palette.items()):
            block_name = str(key)
            block_id = int(val)
            if block_name and block_name != "air":
                block = Block("minecraft", block_name, compability_version=COMPABILITY_VERSION)
                struct_obj._palette.append(block)

        for i, block_idx in enumerate(block_data):
            if block_idx == 0:
                continue
            if block_idx >= len(struct_obj._palette):
                continue
            block = struct_obj._palette[block_idx].copy()
            x = i % sx
            y = (i // sx) % sy
            z = i // (sx * sy)
            struct_obj.set_block((x, y, z), block)

        for te in nbt.get("BlockEntities", []):
            x = int(te["x"])
            y = int(te["y"])
            z = int(te["z"])
            if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
                idx = x * sz * sy + y * sz + z
                struct_obj._special_blocks[idx] = dict(te)

        return struct_obj

    @classmethod
    def _load_v2(cls, nbt: nbtlib.Compound) -> MatrixStructure:
        """加载 Sponge Schematic V2 (Blocks)"""
        sx = int(nbt["Width"])
        sy = int(nbt["Height"])
        sz = int(nbt["Length"])
        size = (sx, sy, sz)

        struct_obj = MatrixStructure(size)
        struct_obj._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        blocks_nbt = nbt["Blocks"]
        palette_map = {}

        for key, val in blocks_nbt["Palette"].items():
            block_name = str(key)
            block_id = int(val)
            if block_name and block_name != "air":
                palette_map[block_id] = Block("minecraft", block_name, compability_version=COMPABILITY_VERSION)

        data = blocks_nbt["Data"]
        bits_per_block = max(2, math.ceil(math.log2(len(palette_map) + 1))) if palette_map else 2
        total_bits = bits_per_block * len(data)

        for i in range(len(data)):
            byte_val = int(data[i])
            for bit in range(8):
                if i * 8 + bit >= total_bits:
                    break
                idx = (byte_val >> bit) & 0xFF
                if idx == 0:
                    continue
                block = palette_map.get(idx)
                if block is None:
                    continue
                x = (i * 8 + bit) % sx
                y = ((i * 8 + bit) // sx) % sy
                z = (i * 8 + bit) // (sx * sy)
                if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
                    struct_obj.set_block((x, y, z), block)

        for te in blocks_nbt.get("BlockEntities", []):
            x = int(te["x"])
            y = int(te["y"])
            z = int(te["z"])
            if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
                idx = x * sz * sy + y * sz + z
                struct_obj._special_blocks[idx] = dict(te)

        return struct_obj

    def _struct_to_nbt(self, struct: MatrixStructure) -> nbtlib.Compound:
        sx, sy, sz = struct.size
        size = struct.size

        palette_list = []
        palette_map = {}

        for i, block in enumerate(struct._palette):
            if block.base_name == "air":
                continue
            palette_map[block] = i
            palette_list.append(block.base_name)

        block_data = bytearray()
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        continue
                    idx = palette_map.get(block, 0)
                    block_data.append(idx)

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

        palette = nbtlib.Compound({
            nbtlib.String(name): nbtlib.Int(i) for i, name in enumerate(palette_list)
        })

        nbt_root = nbtlib.Compound({
            "Version": nbtlib.Int(2),
            "DataVersion": nbtlib.Int(2586),
            "Width": nbtlib.Short(sx),
            "Height": nbtlib.Short(sy),
            "Length": nbtlib.Short(sz),
            "Offset": nbtlib.IntArray([0, 0, 0]),
            "PaletteMax": nbtlib.Int(len(palette_list)),
            "Palette": palette,
            "BlockData": nbtlib.ByteArray(block_data),
            "BlockEntities": block_entities,
        })
        return nbt_root
