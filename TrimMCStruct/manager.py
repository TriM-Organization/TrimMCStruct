"""
结构管理器 - 插件式格式转换核心

插件加载、格式自动检测和结构转换由 TriM-Organization 开发者设计实现。
原库 mcstructure (https://github.com/phoenixR-codes/mcstructure) 的核心类
（Block, MatrixStructure）保留在 main.py 中。
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Type
import importlib
import os

from TrimMCStruct.main import MatrixStructure
from TrimMCStruct.plugin import IPlugin


class StructManager:
    """
    结构管理器，负责插件加载、格式检测和结构转换。

    使用示例:
    ```python
    from TrimMCStruct import StructManager, Block

    manager = StructManager()

    # 加载结构（自动检测格式）
    struct = manager.load("input.mcstructure")

    # 编辑结构
    struct.set_block((1, 1, 1), Block.from_identifier("minecraft:diamond_block"))

    # 导出为指定格式
    manager.save(struct, "output.schematic")
    ```
    """

    def __init__(self, scripts_dir: Optional[str] = None):
        """
        初始化结构管理器。

        Parameters
        ----------
        scripts_dir
            插件脚本目录路径。如果不指定，将自动使用
            当前包的 scripts/ 目录。
        """
        self._plugins: dict[str, IPlugin] = {}
        self._extension_map: dict[str, IPlugin] = {}

        if scripts_dir is None:
            scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")

        self._discover_plugins(scripts_dir)

    def _discover_plugins(self, scripts_dir: str) -> None:
        """
        扫描并加载所有插件。

        插件必须是 IPlugin 的实现类，且位于 scripts/ 目录下。
        """
        scripts_path = Path(scripts_dir)
        if not scripts_path.exists():
            raise FileNotFoundError(f"插件目录不存在: {scripts_dir}")

        for py_file in sorted(scripts_path.glob("*.py")):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue

            module_name = f"TrimMCStruct.scripts.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    if attr_name.startswith("_"):
                        continue
                    attr = getattr(module, attr_name)
                    try:
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, IPlugin)
                            and attr is not IPlugin
                        ):
                            plugin_instance = attr()
                            self._register_plugin(plugin_instance)
                    except TypeError:
                        pass

            except Exception as e:
                print(f"警告: 无法加载插件 {py_file.name}: {e}")

    def _register_plugin(self, plugin: IPlugin) -> None:
        """注册插件到管理器"""
        self._plugins[plugin.name] = plugin
        for ext in plugin.extensions:
            self._extension_map[ext.lower()] = plugin

    @property
    def available_formats(self) -> dict[str, list[str]]:
        """
        获取所有已注册的格式及其扩展名。

        Returns
        -------
        dict
            格式名称 -> 扩展名列表
        """
        result = {}
        for name, plugin in self._plugins.items():
            result[name] = plugin.extensions
        return result

    def _detect_format(self, path: str | Path) -> IPlugin:
        """
        根据文件扩展名检测对应的插件。

        Parameters
        ----------
        path
            文件路径

        Returns
        -------
        IPlugin
            对应的插件实例

        Raises
        ------
        ValueError
            如果无法识别文件格式
        """
        path_obj = Path(path)
        ext = path_obj.suffix.lower()

        if ext not in self._extension_map:
            available = ", ".join(
                sorted(set(ext for plugin in self._plugins.values() for ext in plugin.extensions))
            )
            raise ValueError(
                f"无法识别的文件格式: {ext}\n"
                f"支持的格式: {available}"
            )

        return self._extension_map[ext]

    def load(self, path: str | Path) -> MatrixStructure:
        """
        加载结构文件（自动检测格式）。

        Parameters
        ----------
        path
            输入文件路径

        Returns
        -------
        MatrixStructure
            解析后的结构对象
        """
        plugin = self._detect_format(path)
        return plugin.load_from_path(path)

    def save(self, struct: MatrixStructure, path: str | Path) -> None:
        """
        保存结构文件（自动检测格式）。

        Parameters
        ----------
        struct
            要保存的结构对象
        path
            输出文件路径
        """
        plugin = self._detect_format(path)
        plugin.dump_to_path(struct, path)

    def convert(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> MatrixStructure:
        """
        转换文件格式（加载后直接导出）。

        Parameters
        ----------
        input_path
            输入文件路径
        output_path
            输出文件路径

        Returns
        -------
        MatrixStructure
            转换后的结构对象
        """
        struct = self.load(input_path)
        self.save(struct, output_path)
        return struct

    def list_plugins(self) -> None:
        """打印所有已注册的插件信息"""
        print("已注册的格式插件:")
        for name, plugin in self._plugins.items():
            extensions = ", ".join(plugin.extensions)
            print(f"  - {name}: {extensions}")
