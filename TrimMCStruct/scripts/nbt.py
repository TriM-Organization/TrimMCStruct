"""
.nbt 文件格式插件 (Minecraft NBT Structure)

支持读取和写入基岩版 .nbt 结构文件。
.nbt 是 .mcstructure 的原始 NBT 格式，字节序为大端。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
    pyobj_into_nbttag,
)


class NBTPlugin(IPlugin):
    """
    .nbt 文件格式插件

    支持 Minecraft 基岩版 NBT 结构文件格式。
    与 .mcstructure 类似，但使用大端字节序。
    """

    @property
    def name(self) -> str:
        return "nbt"

    @property
    def extensions(self) -> list[str]:
        return [".nbt"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        nbt = nbtlib.File.from_fileobj(file_obj, byteorder="big")
        root = nbt

        size = (int(root["size"][0]), int(root["size"][1]), int(root["size"][2]))
        struct = MatrixStructure(size)

        structure = root["structure"]
        block_indices = list(structure["block_indices"][0])

        palette = structure["palette"]["default"]["block_palette"]
        for block_data in palette:
            name = str(block_data["name"])
            states = {k: v for k, v in block_data["states"].items()}
            block = Block("minecraft", name, states, compability_version=COMPABILITY_VERSION)
            struct._palette.append(block)

        block_position_data = structure["palette"]["default"]["block_position_data"]
        for idx_str, nbt_data in block_position_data.items():
            idx = int(idx_str)
            if isinstance(nbt_data, dict):
                struct._special_blocks[idx] = nbt_data

        return struct

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        nbt_file = self._nbtfilize(struct)
        nbt_file.write(file_obj, byteorder="big")

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        nbt_file = self._nbtfilize(struct)
        nbt_file.save(path, byteorder="big")

    def _nbtfilize(self, struct: MatrixStructure) -> nbtlib.File:
        """将结构转换为 NBT 文件"""
        sx, sy, sz = struct.size
        size = struct.size

        block_indices = []
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        block_indices.append(-1)
                    else:
                        try:
                            block_indices.append(struct._palette.index(block))
                        except ValueError:
                            block_indices.append(-1)

        nbt_file = nbtlib.File(
            nbtlib.Compound({
                "format_version": nbtlib.Int(1),
                "size": nbtlib.List([nbtlib.Int(sx), nbtlib.Int(sy), nbtlib.Int(sz)]),
                "structure_world_origin": nbtlib.List([nbtlib.Int(0), nbtlib.Int(0), nbtlib.Int(0)]),
                "structure": nbtlib.Compound({
                    "block_indices": nbtlib.List([
                        nbtlib.List([nbtlib.Int(i) for i in block_indices]),
                        nbtlib.List([nbtlib.Int(-1) for _ in block_indices]),
                    ]),
                    "entities": nbtlib.List([]),
                    "palette": nbtlib.Compound({
                        "default": nbtlib.Compound({
                            "block_palette": nbtlib.List([
                                pyobj_into_nbttag(block.dictionarify())
                                for block in struct._palette
                            ]),
                            "block_position_data": pyobj_into_nbttag(struct._special_blocks),
                        })
                    }),
                }),
            })
        )
        return nbt_file
