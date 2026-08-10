"""
.schematic 文件格式插件 (MCEdit Schematic)

支持读取和写入 MCEdit 格式的 .schematic 文件。
文件格式参考: https://minecraft.wiki/w/Schematic_file_format

由 TriM-Organization 开发者实现，原库 mcstructure 中已有部分基础逻辑
（https://github.com/phoenixR-codes/mcstructure）。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, BinaryIO
import array
import gzip
import nbtlib

from TrimMCStruct.plugin import IPlugin
from TrimMCStruct.main import (
    Block,
    MatrixStructure,
    COMPABILITY_VERSION,
)


class SchematicPlugin(IPlugin):
    """
    .schematic 文件格式插件

    支持 MCEdit Schematic 格式（老版 .schematic）。
    文件包含宽(W)、高(H)、长(D)等信息，按 YZX 顺序存储方块。
    """

    @property
    def name(self) -> str:
        return "schematic"

    @property
    def extensions(self) -> list[str]:
        return [".schematic"]

    @classmethod
    def load(cls, file_obj: BinaryIO) -> MatrixStructure:
        if hasattr(file_obj, 'mode') and 'b' in getattr(file_obj, 'mode', ''):
            file_obj = gzip.GzipFile(fileobj=file_obj)
        nbt = nbtlib.File.from_fileobj(file_obj)
        root = nbt

        sx = int(root["Width"])
        sy = int(root["Height"])
        sz = int(root["Length"])
        size = (sx, sy, sz)

        struct = MatrixStructure(size)
        struct._palette.append(
            Block("minecraft", "air", compability_version=COMPABILITY_VERSION)
        )

        blocks_data = root["Blocks"]
        data_data = root.get("Data", None)

        for y in range(sy):
            for z in range(sz):
                for x in range(sx):
                    idx = y * sz * sx + z * sx + x
                    block_id = int(blocks_data[idx])
                    block_data_val = int(data_data[idx]) if data_data is not None else 0

                    if block_id == 0:
                        continue

                    block_name = cls._runtime_id_to_block(block_id)
                    if not block_name:
                        continue

                    states = cls._block_data_to_states(block_name, block_data_val)
                    block = Block(
                        "minecraft", block_name, states, compability_version=COMPABILITY_VERSION
                    )
                    struct.set_block((x, y, z), block)

        tile_entities = root.get("TileEntities", [])
        for te in tile_entities:
            pos = (int(te["x"]), int(te["y"]), int(te["z"]))
            block = struct.get_block(pos)
            if block is None:
                continue
            block_nbt = cls._tile_entity_to_nbt(te)
            if block_nbt:
                block_index = pos[0] * sz * sy + pos[1] * sz + pos[2]
                struct._special_blocks[block_index] = block_nbt

        return struct

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

    @staticmethod
    def _runtime_id_to_block(runtime_id: int) -> str:
        runtime_id_to_block = {
            1: "stone",
            2: "grass",
            3: "dirt",
            4: "cobblestone",
            5: "planks",
            6: "sapling",
            7: "bedrock",
            8: "flowing_water",
            9: "water",
            10: "flowing_lava",
            11: "lava",
            12: "sand",
            13: "gravel",
            14: "gold_ore",
            15: "iron_ore",
            16: "coal_ore",
            17: "log",
            18: "leaves",
            19: "sponge",
            20: "glass",
            21: "lapis_ore",
            22: "lapis_block",
            23: "dispenser",
            24: "sandstone",
            25: "noteblock",
            27: "bed",
            28: "golden_rail",
            29: "detector_rail",
            30: "sticky_piston",
            31: "cobweb",
            32: "tallgrass",
            33: "deadbush",
            34: "piston",
            35: "piston_head",
            36: "wool",
            37: "piston_extension",
            38: "yellow_flower",
            39: "red_flower",
            40: "brown_mushroom",
            41: "red_mushroom",
            42: "gold_block",
            43: "iron_block",
            44: "double_stone_slab",
            45: "stone_slab",
            46: "brick_block",
            47: "tnt",
            48: "bookshele",
            49: "moggrass",
            50: "fire",
            51: "mob_spawner",
            52: "oak_stairs",
            53: "chest",
            54: "redstone_wire",
            55: "diamond_ore",
            56: "diamond_block",
            57: "crafting_table",
            58: "wheat",
            59: "farmland",
            60: "furnace",
            61: "lit_furnace",
            62: "standing_sign",
            63: "wooden_door",
            64: "ladder",
            65: "rail",
            66: "stone_stairs",
            67: "wall_sign",
            68: "lever",
            69: "stone_pressure_plate",
            70: "iron_door",
            71: "wooden_pressure_plate",
            72: "redstone_ore",
            73: "lit_redstone_ore",
            74: "unlit_redstone_torch",
            75: "redstone_torch",
            76: "stone_button",
            77: "snow_layer",
            78: "ice",
            79: "snow",
            80: "cactus",
            81: "clay",
            82: "sugar_cane",
            83: "fence_gate",
            84: "brick_tnt",
            85: "stone_brick",
            86: "redstone_lamp",
            87: "lit_redstone_lamp",
            88: "dropper",
            89: "standing_banner",
            90: "wall_banner",
            91: "daylight_detector",
            92: "redstone_block",
            93: "quartz_ore",
            94: "hopper",
            95: "quartz_block",
            96: "quartz_stairs",
            97: "activator_rail",
            98: "dropper",
            99: "carpet",
            100: "hard_clay",
            101: "coal_block",
            102: "packed_ice",
            103: "double_stone_slab2",
            104: "stone_slab2",
            105: "iron_bars",
            106: "glass_pane",
            107: "meloun_block",
            108: "pumpkin",
            109: "lit_pumpkin",
            110: "netherrack",
            111: "soul_sand",
            112: "glowstone",
            113: "nether_portal",
            114: "lit_redstone_torch",
            115: "stone_stairs",
            116: "spruce_stairs",
            117: "birch_stairs",
            118: "jungle_stairs",
            119: "command_block",
            120: "beacon",
            121: "cobblestone_wall",
            122: "flower_pot",
            123: "carrots",
            124: "potatoes",
            125: "wooden_button",
            126: "skull",
            127: "anvil",
            128: "trapped_chest",
            129: "light_weighted_pressure_plate",
            130: "heavy_weighted_pressure_plate",
            131: "unnormal_command_block",
            132: "daylight_detector_inverted",
            133: "redstone_double_slab",
            134: "stone_double_slab",
            135: "coal_block",
            136: "packed_ice",
            137: "moving_piston",
            140: "spruce_door",
            141: "birch_door",
            142: "jungle_door",
            143: "acacia_door",
            144: "dark_oak_door",
            145: "gravel",
            146: "gold_ore",
            147: "iron_ore",
            148: "coal_ore",
            149: "log",
            150: "log2",
            151: "leaves",
            152: "leaves2",
            153: "sponge",
            154: "glass",
            155: "lapis_ore",
            156: "lapis_block",
            157: "sandstone",
            158: "noteblock",
            159: "golden_rail",
            160: "detector_rail",
            161: "sticky_piston",
            162: "cobweb",
            163: "tallgrass",
            164: "deadbush",
            165: "piston",
            166: "piston_head",
            167: "wool",
            168: "piston_extension",
            169: "yellow_flower",
            170: "red_flower",
            171: "brown_mushroom",
            172: "red_mushroom",
            173: "gold_block",
            174: "iron_block",
            175: "stone_slab",
            176: "brick_block",
            177: "tnt",
            178: "bookshelf",
            179: "moongrass",
            180: "fire",
            181: "mob_spawner",
            182: "oak_stairs",
            183: "chest",
            184: "redstone_wire",
            185: "diamond_ore",
            186: "diamond_block",
            187: "crafting_table",
            188: "wheat",
            189: "farmland",
            190: "furnace",
            191: "lit_furnace",
            192: "standing_sign",
            193: "wooden_door",
            194: "ladder",
            195: "rail",
            196: "stone_stairs",
            197: "wall_sign",
            198: "lever",
            199: "stone_pressure_plate",
            200: "iron_door",
            201: "wooden_pressure_plate",
            202: "redstone_ore",
            203: "lit_redstone_ore",
            204: "unlit_redstone_torch",
            205: "redstone_torch",
            206: "stone_button",
            207: "snow_layer",
            208: "ice",
            209: "snow",
            210: "cactus",
            211: "clay",
            212: "sugar_cane",
            213: "fence_gate",
            214: "brick_tnt",
            215: "stone_brick",
            216: "redstone_lamp",
            217: "lit_redstone_lamp",
            218: "dropper",
            219: "standing_banner",
            220: "wall_banner",
            221: "daylight_detector",
            222: "redstone_block",
            223: "quartz_ore",
            224: "hopper",
            225: "quartz_block",
            226: "quartz_stairs",
            227: "activator_rail",
            228: "dropper",
            229: "carpet",
            230: "hard_clay",
            231: "coal_block",
            232: "packed_ice",
            233: "double_stone_slab2",
            234: "stone_slab2",
            235: "iron_bars",
            236: "glass_pane",
            237: "meloun_block",
            238: "pumpkin",
            239: "lit_pumpkin",
            240: "netherrack",
            241: "soul_sand",
            242: "glowstone",
            243: "nether_portal",
            244: "lit_redstone_torch",
            245: "stone_stairs",
            246: "spruce_stairs",
            247: "birch_stairs",
            248: "jungle_stairs",
            249: "command_block",
            250: "beacon",
            251: "cobblestone_wall",
            252: "flower_pot",
            253: "carrots",
            254: "potatoes",
            255: "wooden_button",
            256: "skull",
            257: "anvil",
            258: "trapped_chest",
            259: "light_weighted_pressure_plate",
            260: "heavy_weighted_pressure_plate",
            261: "unnormal_command_block",
            262: "daylight_detector_inverted",
            263: "redstone_double_slab",
            264: "stone_double_slab",
            265: "quartz_double_slab",
            266: "comparator",
            267: "item_frame",
            268: "flower_pot",
            269: "carrot",
            270: "potato",
            271: "wooden_button",
            272: "skull",
            273: "anvil",
            274: "trapped_chest",
            275: "light_weighted_pressure_plate",
            276: "heavy_weighted_pressure_plate",
            277: "unnormal_command_block",
            278: "daylight_detector_inverted",
            279: "redstone_double_slab",
            280: "stone_double_slab",
            281: "quartz_double_slab",
            282: "comparator",
            283: "beetroot",
            284: "stonecutter",
            285: "glowstone",
            286: "nether_portal",
            287: "lit_redstone_torch",
            288: "stone_stairs",
            289: "spruce_stairs",
            290: "birch_stairs",
            291: "jungle_stairs",
            292: "command_block",
            293: "beacon",
            294: "cobblestone_wall",
            295: "flower_pot",
            296: "carrots",
            297: "potatoes",
            298: "wooden_button",
            299: "skull",
            300: "anvil",
            301: "trapped_chest",
            302: "light_weighted_pressure_plate",
            303: "heavy_weighted_pressure_plate",
            304: "unnormal_command_block",
            305: "daylight_detector_inverted",
            306: "redstone_double_slab",
            307: "stone_double_slab",
            308: "quartz_double_slab",
            309: "comparator",
            310: "beetroot",
            311: "stonecutter",
            312: "grindstone",
            313: "blast_furnace",
            314: "smoker",
            315: "lit_smoker",
            316: "stonecutter_block",
            317: "melon",
            318: "pumpkin",
            319: "lit_pumpkin",
            320: "netherrack",
            321: "soul_sand",
            322: "glowstone",
            323: "nether_portal",
            324: "lit_redstone_torch",
            325: "stone_stairs",
            326: "spruce_stairs",
            327: "birch_stairs",
            328: "jungle_stairs",
            329: "command_block",
            330: "beacon",
            331: "cobblestone_wall",
            332: "flower_pot",
            333: "carrots",
            334: "potatoes",
            335: "wooden_button",
            336: "skull",
            337: "anvil",
            338: "trapped_chest",
            339: "light_weighted_pressure_plate",
            340: "heavy_weighted_pressure_plate",
            341: "unnormal_command_block",
            342: "daylight_detector_inverted",
            343: "redstone_double_slab",
            344: "stone_double_slab",
            345: "quartz_double_slab",
            346: "comparator",
            347: "beetroot",
            348: "stonecutter",
            349: "grindstone",
            350: "blast_furnace",
            351: "smoker",
            352: "lit_smoker",
            353: "stonecutter_block",
            354: "melon",
            355: "pumpkin",
            356: "lit_pumpkin",
            357: "netherrack",
            358: "soul_sand",
            359: "glowstone",
            360: "nether_portal",
            361: "lit_redstone_torch",
            362: "stone_stairs",
            363: "spruce_stairs",
            364: "birch_stairs",
            365: "jungle_stairs",
            366: "command_block",
            367: "beacon",
            368: "cobblestone_wall",
            369: "flower_pot",
            370: "carrots",
            371: "potatoes",
            372: "wooden_button",
            373: "skull",
            374: "anvil",
            375: "trapped_chest",
            376: "light_weighted_pressure_plate",
            377: "heavy_weighted_pressure_plate",
            378: "unnormal_command_block",
            379: "daylight_detector_inverted",
            380: "redstone_double_slab",
            381: "stone_double_slab",
            382: "quartz_double_slab",
            383: "comparator",
            384: "beetroot",
            385: "stonecutter",
            386: "grindstone",
            387: "blast_furnace",
            388: "smoker",
            389: "lit_smoker",
            390: "stonecutter_block",
        }
        return runtime_id_to_block.get(runtime_id, f"unknown_{runtime_id}")

    @staticmethod
    def _block_data_to_states(block_name: str, data_val: int) -> dict:
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
        elif block_name in ("leaves", "leaves2"):
            states["persistent"] = bool(data_val & 1)
            states["distance"] = str(data_val & 7)
        elif block_name == "redstone_wire":
            states["power"] = str(data_val)
        elif block_name == "tallgrass":
            states["variant"] = str(data_val)
        elif block_name == "double_stone_slab":
            states["type"] = str(data_val)
        elif block_name == "stone_pressure_plate":
            states["power"] = str(data_val)
        elif block_name == "lever":
            states["facing_direction"] = str(data_val & 7)
            states["attached_bit"] = bool(data_val & 8)
        elif block_name == "stone_button":
            states["facing_direction"] = str(data_val & 3)
            states["powered"] = bool(data_val & 4)
        elif block_name == "snow":
            states["layers"] = str(min(data_val, 8))
        elif block_name == "iron_bars":
            states["power"] = str(data_val)
        elif block_name in ("skull",):
            states["skull_type"] = str(data_val)
        elif block_name == "cactus":
            states["age"] = str(data_val)
        elif block_name == "repeater":
            states["facing_direction"] = str(data_val & 3)
            states["delay"] = str((data_val >> 2) & 3 + 1)
            states["locked"] = bool(data_val & 8)
        elif block_name == "command_block":
            pass
        return states

    @staticmethod
    def _tile_entity_to_nbt(te: Any) -> dict | None:
        block_name = te.get("id", "")
        if block_name == "CommandBlock":
            return {
                "id": "CommandBlock",
                "Command": te.get("Command", ""),
                "CustomName": te.get("CustomName", ""),
                "auto": te.get("auto", 1),
                "TickDelay": te.get("TickDelay", 0),
                "conditionalMode": te.get("conditionalMode", 0),
                "TrackOutput": te.get("TrackOutput", 1),
                "ExecuteOnFirstTick": te.get("ExecuteOnFirstTick", 1),
                "Version": te.get("Version", 19),
            }
        elif block_name in ("Chest", "Container", "TrapChest"):
            return {
                "id": "Chest",
                "Items": te.get("Items", []),
            }
        elif block_name == "Sign":
            return {
                "id": "Sign",
                "Text1": te.get("Text1", ""),
                "Text2": te.get("Text2", ""),
                "Text3": te.get("Text3", ""),
                "Text4": te.get("Text4", ""),
                "x": te.get("x", 0),
                "y": te.get("y", 0),
                "z": te.get("z", 0),
            }
        elif block_name == "Furnace":
            return {
                "id": "Furnace",
                "Items": te.get("Items", []),
                "BurnTime": te.get("BurnTime", 0),
                "CookTime": te.get("CookTime", 0),
                "CookTotalTime": te.get("CookTotalTime", 0),
            }
        elif block_name == "EnchantTable":
            return {"id": "EnchantTable"}
        elif block_name == "SpawnEntity":
            return {"id": "SpawnEntity", "Name": te.get("Name", ""), "Data": te.get("Data", "")}
        return None

    def _struct_to_nbt(self, struct: MatrixStructure) -> nbtlib.Compound:
        sx, sy, sz = struct.size
        volume = sx * sy * sz

        blocks_array = array.array("b", [0]) * volume
        data_array = array.array("b", [0]) * volume

        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    block = struct.get_block((x, y, z))
                    if block is None:
                        continue
                    runtime_id = self._block_to_runtime_id(block.base_name)
                    if runtime_id == 0:
                        continue
                    idx = y * sz * sx + z * sx + x
                    blocks_array[idx] = runtime_id
                    data_array[idx] = self._block_to_data_value(block)

        nbt_root = nbtlib.Compound({
            "Width": nbtlib.Short(sx),
            "Height": nbtlib.Short(sy),
            "Length": nbtlib.Short(sz),
            "Materials": nbtlib.String("Alpha"),
            "Blocks": nbtlib.ByteArray(blocks_array),
            "Data": nbtlib.ByteArray(data_array),
            "Entities": nbtlib.List([]),
            "TileEntities": nbtlib.List([]),
        })
        return nbt_root

    @staticmethod
    def _block_to_runtime_id(block_name: str) -> int:
        block_to_runtime_id = {
            "stone": 1, "grass": 2, "dirt": 3, "cobblestone": 4, "planks": 5,
            "sapling": 6, "bedrock": 7, "flowing_water": 8, "water": 9,
            "flowing_lava": 10, "lava": 11, "sand": 12, "gravel": 13,
            "gold_ore": 14, "iron_ore": 15, "coal_ore": 16, "log": 17,
            "leaves": 18, "sponge": 19, "glass": 20, "lapis_ore": 21,
            "lapis_block": 22, "dispenser": 23, "sandstone": 24, "noteblock": 25,
            "golden_rail": 28, "detector_rail": 29, "sticky_piston": 30,
            "cobweb": 31, "tallgrass": 32, "deadbush": 33, "piston": 34,
            "wool": 35, "yellow_flower": 38, "red_flower": 39,
            "brown_mushroom": 40, "red_mushroom": 41, "gold_block": 42,
            "iron_block": 43, "brick_block": 46, "tnt": 47, "bookshele": 48,
            "moggrass": 49, "fire": 50, "mob_spawner": 51, "oak_stairs": 52,
            "chest": 53, "redstone_wire": 54, "diamond_ore": 55,
            "diamond_block": 56, "crafting_table": 57, "wheat": 58,
            "farmland": 59, "furnace": 60, "lit_furnace": 61,
            "standing_sign": 62, "wooden_door": 63, "ladder": 64,
            "rail": 65, "stone_stairs": 66, "wall_sign": 67, "lever": 68,
            "stone_pressure_plate": 69, "iron_door": 70,
            "wooden_pressure_plate": 71, "redstone_ore": 72,
            "lit_redstone_ore": 73, "unlit_redstone_torch": 74,
            "redstone_torch": 75, "stone_button": 76, "snow_layer": 77,
            "ice": 78, "snow": 79, "cactus": 80, "clay": 81,
            "sugar_cane": 82, "fence_gate": 83, "brick_tnt": 84,
            "stone_brick": 85, "redstone_lamp": 86, "lit_redstone_lamp": 87,
            "dropper": 88, "standing_banner": 89, "wall_banner": 90,
            "daylight_detector": 91, "redstone_block": 92, "quartz_ore": 93,
            "hopper": 94, "quartz_block": 95, "quartz_stairs": 96,
            "activator_rail": 97, "carpet": 99, "hard_clay": 100,
            "coal_block": 101, "packed_ice": 102,
            "iron_bars": 105, "glass_pane": 106, "melon_block": 107,
            "pumpkin": 108, "lit_pumpkin": 109, "netherrack": 110,
            "soul_sand": 111, "glowstone": 112, "nether_portal": 113,
            "lit_redstone_torch": 114, "spruce_stairs": 116,
            "birch_stairs": 117, "jungle_stairs": 118,
            "command_block": 119, "beacon": 120,
            "cobblestone_wall": 121, "flower_pot": 122, "carrots": 123,
            "potatoes": 124, "wooden_button": 125, "skull": 126,
            "anvil": 127, "trapped_chest": 128,
            "light_weighted_pressure_plate": 129,
            "heavy_weighted_pressure_plate": 130,
            "unnormal_command_block": 131,
            "daylight_detector_inverted": 132,
            "redstone_double_slab": 133,
            "stone_double_slab": 134,
            "quartz_double_slab": 135,
            "comparator": 136,
            "item_frame": 137,
            "grindstone": 138,
            "blast_furnace": 139,
            "smoker": 140,
            "lit_smoker": 141,
            "stonecutter_block": 142,
            "melon": 143,
            "grindstone": 144,
            "blast_furnace": 145,
            "smoker": 146,
            "lit_smoker": 147,
            "stonecutter": 148,
        }
        return block_to_runtime_id.get(block_name, 0)

    @staticmethod
    def _block_to_data_value(block: Block) -> int:
        states = block.states
        if not states:
            return 0
        if "color" in states:
            try:
                return int(states["color"])
            except (ValueError, TypeError):
                return 0
        if "axis" in states:
            try:
                return int(states["axis"])
            except (ValueError, TypeError):
                return 0
        if "type" in states:
            try:
                return int(states["type"])
            except (ValueError, TypeError):
                return 0
        if "facing_direction" in states:
            try:
                return int(states["facing_direction"])
            except (ValueError, TypeError):
                return 0
        if "layers" in states:
            try:
                return int(states["layers"])
            except (ValueError, TypeError):
                return 0
        if "power" in states:
            try:
                return int(states["power"])
            except (ValueError, TypeError):
                return 0
        if "delay" in states:
            try:
                return int(states["delay"])
            except (ValueError, TypeError):
                return 0
        return 0
