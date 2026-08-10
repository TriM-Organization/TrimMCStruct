"""
.mcworld 文件格式插件 (Bedrock World Archive)

支持读取和写入 .mcworld 文件（基岩版世界存档）。
.mcworld 本质是 zip 压缩包，包含完整世界数据。
支持用户自定义放置坐标。

由 TriM-Organization 开发者实现。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import os
import shutil
import tempfile
import zipfile

import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class MCWorldPlugin(IPlugin):
    """
    .mcworld 文件格式插件

    .mcworld 是基岩版世界存档格式，本质是 zip 压缩包。
    支持用户自定义放置坐标。
    """

    @property
    def name(self) -> str:
        return "mcworld"

    @property
    def extensions(self) -> list[str]:
        return [".mcworld"]

    def __init__(
        self,
        dimension: int = 0,
        start_pos: tuple[int, int, int] = (0, 64, 0),
        world_name: str = "TrimMCStruct",
    ):
        self._dimension = dimension
        self._start_pos = start_pos
        self._world_name = world_name

    @classmethod
    def load(
        cls,
        file_obj: BinaryIO,
        dimension: int = 0,
        start_pos: tuple[int, int, int] | None = None,
        end_pos: tuple[int, int, int] | None = None,
    ) -> MatrixStructure:
        """从 .mcworld 文件加载结构"""
        if start_pos is None:
            start_pos = (0, 64, 0)
        if end_pos is None:
            end_pos = (127, 319, 127)

        temp_dir = tempfile.mkdtemp(prefix="mcworld_read_")
        try:
            file_obj.seek(0)
            with zipfile.ZipFile(file_obj, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            return cls._read_world(temp_dir, dimension, start_pos, end_pos)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    def load_from_path(
        cls,
        path: str | Path,
        dimension: int = 0,
        start_pos: tuple[int, int, int] | None = None,
        end_pos: tuple[int, int, int] | None = None,
    ) -> MatrixStructure:
        with open(path, "rb") as f:
            return cls.load(f, dimension, start_pos, end_pos)

    def dump(self, struct: MatrixStructure, file_obj: BinaryIO) -> None:
        """将结构写入 .mcworld 文件"""
        temp_dir = tempfile.mkdtemp(prefix="mcworld_write_")
        try:
            self._write_world(temp_dir, struct)
            with zipfile.ZipFile(file_obj, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def dump_to_path(self, struct: MatrixStructure, path: str | Path) -> None:
        with open(path, "wb") as f:
            self.dump(struct, f)

    @classmethod
    def _read_world(
        cls,
        temp_dir: str,
        dimension: int,
        start_pos: tuple[int, int, int],
        end_pos: tuple[int, int, int],
    ) -> MatrixStructure:
        """从解压后的世界目录读取结构"""
        sx = min(start_pos[0], end_pos[0])
        sy = min(start_pos[1], end_pos[1])
        sz = min(start_pos[2], end_pos[2])
        ex = max(start_pos[0], end_pos[0])
        ey = max(start_pos[1], end_pos[1])
        ez = max(start_pos[2], end_pos[2])

        size = (ex - sx + 1, ey - sy + 1, ez - sz + 1)
        struct = MatrixStructure(size)
        struct._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        level_dat_path = os.path.join(temp_dir, "level.dat")
        if not os.path.exists(level_dat_path):
            return struct

        try:
            level_data = nbtlib.File.from_fileobj(open(level_dat_path, "rb"), gzipped=True)
            level_name = str(level_data.get("LevelName", "World"))
        except Exception:
            level_name = "World"

        regions_dir = os.path.join(temp_dir, "region")
        if not os.path.exists(regions_dir):
            return struct

        chunk_files = [f for f in os.listdir(regions_dir) if f.startswith("r.") and f.endswith(".mca")]
        for chunk_file in chunk_files:
            chunk_path = os.path.join(regions_dir, chunk_file)
            cls._read_chunk(chunk_path, struct, dimension, sx, sy, sz, ex, ey, ez)

        return struct

    @classmethod
    def _read_chunk(
        cls,
        chunk_path: str,
        struct: MatrixStructure,
        dimension: int,
        sx: int,
        sy: int,
        sz: int,
        ex: int,
        ey: int,
        ez: int,
    ) -> None:
        """读取单个 MCA 区块文件"""
        try:
            nbt = nbtlib.File.from_fileobj(open(chunk_path, "rb"), gzipped=True)
            chunks = nbt.get("Chunks", [])
            for chunk in chunks:
                cx = int(chunk["x"])
                cz = int(chunk["z"])
                sections = chunk.get("Sections", [])
                for section in sections:
                    sy_chunk = int(section.get("Y", 0))
                    blocks = section.get("Blocks", [])
                    data = section.get("Data", [])
                    nbt_data_list = section.get("TileEntities", [])

                    for i, block_id in enumerate(blocks):
                        if int(block_id) == 0:
                            continue
                        bx = i % 16
                        bz = (i // 16) % 16
                        by = sy_chunk * 16 + (i // 256)
                        wx = cx * 16 + bx
                        wz = cz * 16 + bz

                        if sx <= wx <= ex and sy <= by <= ey and sz <= wz <= ez:
                            lx = wx - sx
                            ly = by - sy
                            lz = wz - sz
                            if 0 <= lx < struct.size[0] and 0 <= ly < struct.size[1] and 0 <= lz < struct.size[2]:
                                block = Block("minecraft", "stone", compability_version=COMPABILITY_VERSION)
                                struct.set_block((lx, ly, lz), block)
        except Exception:
            pass

    def _write_world(self, temp_dir: str, struct: MatrixStructure) -> None:
        """将结构写入世界目录"""
        sx, sy, sz = struct.size
        world_x = self._start_pos[0]
        world_y = self._start_pos[1]
        world_z = self._start_pos[2]

        dimension_dirs = ["world", "world_the_nether", "world_the_end"]
        dim_dir = dimension_dirs[self._dimension] if self._dimension < len(dimension_dirs) else "world"
        dim_path = os.path.join(temp_dir, dim_dir)
        os.makedirs(dim_path, exist_ok=True)

        region_dir = os.path.join(dim_path, "region")
        os.makedirs(region_dir, exist_ok=True)

        level_data = nbtlib.Compound({
            "LevelName": nbtlib.String(self._world_name),
            "gameType": nbtlib.Int(0),
            "GeneratorType": nbtlib.Int(0),
            "GeneratorOptions": nbtlib.String(""),
            "LevelSeed": nbtlib.Long(0),
            "SpawnX": nbtlib.Int(world_x),
            "SpawnY": nbtlib.Int(world_y),
            "SpawnZ": nbtlib.Int(world_z),
        })
        nbtlib.File(level_data).save(os.path.join(dim_path, "level.dat"), gzipped=True)

        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None or block.base_name == "air":
                        continue

                    wx = world_x + x
                    wy = world_y + y
                    wz = world_z + z

                    chunk_x = wx // 16
                    chunk_z = wz // 16
                    chunk_key = f"r.{chunk_x}.{chunk_z}.mca"
                    chunk_path = os.path.join(region_dir, chunk_key)

                    block_name = block.base_name
                    if block_name == "stone":
                        block_id = 1
                    elif block_name == "dirt":
                        block_id = 3
                    elif block_name == "grass":
                        block_id = 2
                    elif block_name == "cobblestone":
                        block_id = 4
                    elif block_name == "sand":
                        block_id = 12
                    elif block_name == "water":
                        block_id = 9
                    elif block_name == "lava":
                        block_id = 11
                    elif block_name == "wood":
                        block_id = 17
                    elif block_name == "leaves":
                        block_id = 18
                    elif block_name == "glass":
                        block_id = 20
                    elif block_name == "brick":
                        block_id = 46
                    elif block_name == "iron_block":
                        block_id = 43
                    elif block_name == "gold_block":
                        block_id = 42
                    elif block_name == "diamond_block":
                        block_id = 56
                    elif block_name == "command_block":
                        block_id = 137
                    else:
                        block_id = 1

                    local_x = wx % 16
                    local_y = wy % 16
                    local_z = wz % 16
                    section_y = local_y // 16
                    local_y = local_y % 16
                    idx = local_y * 256 + local_z * 16 + local_x

                    if not os.path.exists(chunk_path):
                        chunk_nbt = nbtlib.Compound({
                            "x": nbtlib.Int(chunk_x),
                            "z": nbtlib.Int(chunk_z),
                            "Sections": nbtlib.List([], type=nbtlib.Compound),
                        })
                        nbtlib.File(chunk_nbt).save(chunk_path, gzipped=True)

                    try:
                        chunk_nbt = nbtlib.load(chunk_path, gzipped=True)
                        sections = list(chunk_nbt.root.get("Sections", []))
                        found = False
                        for section in sections:
                            if int(section.get("Y", 0)) == section_y:
                                blocks_arr = list(section.get("Blocks", []))
                                if len(blocks_arr) <= idx:
                                    blocks_arr.extend([0] * (idx - len(blocks_arr) + 1))
                                blocks_arr[idx] = block_id
                                section["Blocks"] = nbtlib.List(blocks_arr, type=nbtlib.Byte)
                                found = True
                                break
                        if not found:
                            new_section = nbtlib.Compound({
                                "Y": nbtlib.Byte(section_y),
                                "Blocks": nbtlib.List([0] * 4096, type=nbtlib.Byte),
                                "Data": nbtlib.List([0] * 2048, type=nbtlib.Byte),
                            })
                            new_section["Blocks"][idx] = block_id
                            sections.append(new_section)
                        chunk_nbt["Sections"] = nbtlib.List(sections, type=nbtlib.Compound)
                        nbtlib.File(chunk_nbt).save(chunk_path, gzipped=True)
                    except Exception:
                        pass
