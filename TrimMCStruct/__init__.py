"""
TrimMCStruct - 插件式 Minecraft 结构编辑库

版权所有 © 2023 全体 TriMCStruct 开发者
Copyright © 2023 all the developers of TriMCStruct

开源相关声明请见 ../LICENSE.md
Terms & Conditions: ../LICENSE.md
"""

__version__ = "0.4.0"
__author__ = (
    ("phoenixR", "phoenixR"),
    ("金羿", "Eilles Wan"),
    ("诸葛亮与八卦阵", "bgArray"),
)
__all__ = [
    "Block",
    "MatrixStructure",
    "is_valid_structure_name",
    "nbtag_into_pyobj",
    "pyobj_into_nbttag",
    "StructManager",
]

from .main import (
    Block,
    MatrixStructure,
    is_valid_structure_name,
    nbtag_into_pyobj,
    pyobj_into_nbttag,
)
from .manager import StructManager
