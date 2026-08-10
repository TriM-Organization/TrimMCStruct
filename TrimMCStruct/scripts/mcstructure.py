"""
.mcstructure 文件格式插件

本文件中的 .mcstructure 读写逻辑最初来源于
原库 mcstructure (https://github.com/phoenixR-codes/mcstructure)，
作者 The-phoenixR，遵循 MIT 协议。
后经 TriM-Organization 开发者改编为插件式架构。
"""

from __future__ import annotations
from functools import partial
from itertools import repeat
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np
from numpy.typing import NDArray
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
    Coordinate,
    pyobj_into_nbttag,
)


class McStructurePlugin(IPlugin):
    """
    .mcstructure 文件格式插件
    
    支持《我的世界》基岩版结构文件的读写。
    文件格式参考: https://wiki.bedrock.dev/nbt/mcstructure.html
    """

    @property
    def name(self) -> str:
        return "mcstructure"

    @property
    def extensions(self) -> list[str]:
        return [".mcstructure"]

    def __init__(
        self,
        compability_version: int = COMPABILITY_VERSION,
    ):
        self._compability_version = compability_version

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        """
        从二进制流加载 .mcstructure 文件。

        Parameters
        ----------
        file_obj
            二进制文件对象

        Returns
        -------
        MatrixStructure
            解析后的结构对象
        """
        nbt = nbtlib.File.from_fileobj(file_obj, byteorder="little")
        size: tuple[int, int, int] = (
            int(nbt["size"][0]),
            int(nbt["size"][1]),
            int(nbt["size"][2]),
        )

        struct = MatrixStructure(size)

        struct.structure_indecis = np.array(
            nbt["structure"]["block_indices"][0],
            dtype=np.intc,
        ).reshape(size)

        struct._palette.extend(
            [
                Block.from_identifier(
                    block["name"],
                    **{k: v for k, v in block["states"].items()},
                    compability_version=int(block["version"]),
                )
                for block in nbt["structure"]["palette"]["default"]["block_palette"]
            ]
        )

        for block_index, block_extra_data in nbt["structure"]["palette"]["default"][
            "block_position_data"
        ].items():
            struct._special_blocks[int(block_index)] = block_extra_data

        return struct

    @classmethod
    def load_from_path(cls, path: str | Path) -> MatrixStructure:
        """
        从文件路径加载 .mcstructure 文件。

        Parameters
        ----------
        path
            文件路径

        Returns
        -------
        MatrixStructure
            解析后的结构对象
        """
        with open(path, "rb") as f:
            return cls.load(f)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        """
        将结构写入二进制流。

        Parameters
        ----------
        struct
            要导出的结构对象
        file_obj
            二进制文件对象
        """
        nbt_file = self._nbtfilize(struct)
        nbt_file.write(file_obj, byteorder="little")

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        """
        将结构写入文件路径。

        Parameters
        ----------
        struct
            要导出的结构对象
        path
            输出文件路径
        """
        nbt_file = self._nbtfilize(struct)
        nbt_file.save(path, byteorder="little", gzipped=False)

    def _nbtfilize(self, struct: MatrixStructure) -> nbtlib.File:
        """将 MatrixStructure 转换为 NBT 格式"""
        return nbtlib.File(
            dict(
                format_version=nbtlib.Int(1),
                size=pyobj_into_nbttag(struct.size),
                structure=nbtlib.Compound(
                    block_indices=nbtlib.List(
                        [
                            pyobj_into_nbttag(struct.structure_indecis.flatten()),
                            nbtlib.List(
                                list(
                                    repeat(nbtlib.Int(-1), struct.structure_indecis.size),
                                ),
                            ),
                        ],
                    ),
                    entities=nbtlib.List([]),
                    palette=nbtlib.Compound(
                        default=nbtlib.Compound(
                            block_palette=nbtlib.List(
                                [
                                    pyobj_into_nbttag(block.dictionarify())
                                    for block in struct._palette
                                ],
                            ),
                            block_position_data=pyobj_into_nbttag(
                                struct._special_blocks, sort_=lambda a: a[0]
                            ),
                        )
                    ),
                ),
                structure_world_origin=pyobj_into_nbttag((0, 0, 0)),
            ),
            gzipped=False,
            byteorder="little",
        )
