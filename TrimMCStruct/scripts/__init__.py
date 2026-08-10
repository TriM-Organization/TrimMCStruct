"""
TrimMCStruct 插件式 Minecraft 结构编辑库

插件脚本包：包含各文件格式的读写插件。
核心类（Block, MatrixStructure）来自原库 mcstructure
（https://github.com/phoenixR-codes/mcstructure，MIT 协议）。
插件架构和新增格式由 TriM-Organization 开发者实现。

使用流程:
1. 导入结构或使用 StructManager 加载文件
2. 编辑结构（set_block, fill_blocks, mirror, rotate 等）
3. 导出为支持的任意格式
"""

from TrimMCStruct.manager import StructManager
from TrimMCStruct.main import Block, MatrixStructure
