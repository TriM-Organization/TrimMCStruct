"""
插件基类接口

插件式架构由 TriM-Organization 开发者设计实现，
用于支持多种 Minecraft 结构文件格式的统一读写。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO


class IPlugin(ABC):
    """所有文件格式插件的基类接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称，如 'mcstructure'"""
        ...

    @property
    @abstractmethod
    def extensions(self) -> list[str]:
        """支持的文件扩展名，如 ['.mcstructure']"""
        ...

    @abstractmethod
    def load(self, file_obj: BinaryIO) -> MatrixStructure:
        """从二进制流加载结构"""
        ...

    @abstractmethod
    def load_from_path(self, path: str | Path) -> MatrixStructure:
        """从文件路径加载结构"""
        ...

    @abstractmethod
    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        """将结构写入二进制流"""
        ...

    @abstractmethod
    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        """将结构写入文件路径"""
        ...
