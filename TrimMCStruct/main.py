"""
Operating the Minecraft structures.

本文件中的核心类（Block, MatrixStructure）及 NBT 转换函数最初来源于
原库 mcstructure (https://github.com/phoenixR-codes/mcstructure)，
作者 The-phoenixR，遵循 MIT 协议（见 LICENSES/LICENSE(mcstructure).md）。

后经 TriM-Organization 开发者（金羿/Eilles Wan, 诸葛亮与八卦阵/bgArray）改编与扩展。
当前项目遵循 Apache 2.0 协议（见 LICENSE.md）。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from itertools import repeat
import json
from typing import Any, BinaryIO, Callable, Optional, Tuple, Union, Dict, AnyStr, List

import numpy as np
from numpy.typing import NDArray
import nbtlib


Coordinate = Tuple[int, int, int]

# Compatibility versioning number for blocks in 1.19.
COMPABILITY_VERSION: nbtlib.Int = nbtlib.Int(17959425)


def nbtag_into_pyobj(tag_obj: nbtlib.Base) -> Any:
    """
    Turns an NBT tree into a python tree.
    """
    if isinstance(tag_obj, (nbtlib.Compound, dict)):
        res = {}
        for key, value in tag_obj.items():
            if isinstance(value, (nbtlib.Numeric, nbtlib.String)):
                value = nbtag_into_pyobj(value)
            res[key] = value
        return res

    elif isinstance(tag_obj, (nbtlib.List, list)):
        res = []
        for value in tag_obj:
            if isinstance(value, (nbtlib.Numeric, nbtlib.String)):
                value = nbtag_into_pyobj(value)
            res.append(value)
        return res

    elif isinstance(tag_obj, (nbtlib.Double, nbtlib.Float)):
        return float(tag_obj)

    elif isinstance(tag_obj, (nbtlib.Byte)):
        return bool(tag_obj)

    elif isinstance(tag_obj, nbtlib.NumericInteger):
        return int(tag_obj)

    elif isinstance(tag_obj, (nbtlib.String)):
        return str(tag_obj)

    return tag_obj


def pyobj_into_nbttag(
    obj: Any,
    sort_: Optional[Union[bool, Callable]] = False,
    sort_order: Optional[bool] = False,
) -> nbtlib.Base:
    """
    Turn a python tree into an NBT tree.
    """
    if isinstance(obj, (nbtlib.Compound, dict)):
        res = [
            (
                nbtlib.String(key),
                (
                    value
                    if isinstance(value, (nbtlib.Numeric, nbtlib.String))
                    else pyobj_into_nbttag(value)
                ),
            )
            for key, value in obj.items()
        ]

        return nbtlib.Compound(
            res
            if (sort_ is None) or (sort_ is False)
            else sorted(
                res,
                key=(sort_ if isinstance(sort_, Callable) else None),
                reverse=(sort_order if sort_order else False),
            )
        )

    elif isinstance(obj, (nbtlib.List, list, tuple)):
        res = [
            (
                value
                if isinstance(value, (nbtlib.Numeric, nbtlib.String))
                else pyobj_into_nbttag(value)
            )
            for value in obj
        ]
        return nbtlib.List(
            res
            if (sort_ is None) or (sort_ is False)
            else sorted(
                res,
                key=(sort_ if isinstance(sort_, Callable) else None),  # type: ignore
                reverse=(sort_order if sort_order else False),
            )
        )

    elif isinstance(obj, bool):
        return nbtlib.Byte(obj)

    elif isinstance(obj, int):
        return nbtlib.Int(obj)

    elif isinstance(obj, str):
        return nbtlib.String(obj)

    return obj


def is_valid_structure_name(name: str, *, with_prefix: bool = False) -> bool:
    """
    Validates the structure name.

    .. seealso: https://minecraft.wiki/w/Structure_Block

    Parameters
    ----------
    name
        The name of the structure.

    with_prefix
        Whether to take the prefix (e.g. ``mystructure:``)
        into account.
    """
    if with_prefix:
        name = name.replace(":", "", 1)

    return all((char.isalnum() and char in "-_") for char in name)


@dataclass(init=False)
class Block:
    """
    Attributes
    ----------
    base_name
        The name of the block.

    states
        The states of the block.

    Example
    -------
    .. code-block::

        Block("minecraft:wool", color = "red")
    """

    namespace: str
    base_name: str
    states: dict[str, Any]
    extra_data: dict[str, Any]

    def __init__(
        self,
        namespace: str,
        base_name: str,
        states: Dict[str, Union[int, str, bool]] = {},
        extra_data: Dict[str, Union[int, str, bool]] = {},
        compability_version: int = COMPABILITY_VERSION,
    ):
        """
        Parameters
        ----------
        namespace: str
            The namespace of the block (e.g. "minecraft").
        base_name: str
            The name of the block (e.g. "air").

        states
            The block states such as {'color': 'white'} or {"stone_type":1}.
            This varies by every block.

        extra_data
            [Optional] The additional data of the block.

        compability_version: int
            [Optional] The compability version of the block, now(1.19) is 17959425
        """
        self.namespace = namespace
        self.base_name = base_name
        self.states = states
        self.extra_data = extra_data
        self.compability_version = compability_version

    @classmethod
    def from_identifier(
        cls,
        identifier: str,
        compability_version: int = COMPABILITY_VERSION,
        **states: Union[int, str, bool],
    ):
        """
        Parameters
        ----------
        identifier: str
            The identifier of the block (e.g. "minecraft:wool").

        compability_version: int
            [Optional] The compability version of the block, now(1.19) is 17959425

        states:
            The block states such as "color" or "stone_type".
            This varies by every block.
        """

        if ":" in identifier:
            namespace, base_name = identifier.split(":", 1)
        else:
            namespace = "minecraft"
            base_name = identifier

        block = cls(
            namespace, base_name, states, compability_version=compability_version
        )

        return block

    def __str__(self) -> str:
        return self.stringify()

    def __dict__(self) -> dict:
        return self.dictionarify()

    def add_states(
        self,
        states: dict[str, Union[int, str, bool]],
    ) -> None:
        self.states.update(states)

    def add_extra_data(
        self,
        extra_data: dict[str, Union[int, str, bool]],
    ) -> None:
        if isinstance(extra_data, dict):
            self.extra_data.update(extra_data)

    def dictionarify(self, *, with_states: bool = True) -> Dict[str, Any]:
        result = {
            "name": self.identifier,
            "states": self.states if with_states else {},
            "version": self.compability_version,
        }

        return result

    def dictionarify_with_block_entity(
        self, *, with_states: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        result = {
            "name": self.identifier,
            "states": self.states if with_states else {},
            "version": self.compability_version,
        }

        return result, self.extra_data

    def stringify(
        self,
        *,
        with_namespace: bool = True,
        with_states: bool = True,
    ) -> str:
        result = ""
        if with_namespace:
            result += self.namespace + ":"
        result += self.get_name()
        if with_states:
            result += f" [{json.dumps(self.states)[1:-1]}]"
        return result

    def get_namespace_and_name(self) -> tuple[str, str]:
        """
        Returns the namespace and the name of the block.
        """
        return self.namespace, self.base_name

    def get_identifier(self) -> str:
        """
        Returns the identifier of the block.
        """
        return self.namespace + ":" + self.base_name

    def get_name(self) -> str:
        """
        Returns the name of the block.
        """
        return self.base_name

    def get_namespace(self) -> Optional[str]:
        """
        Returns the namespace of the block.
        """
        return self.namespace

    @property
    def identifier(self) -> str:
        """
        The identifier of the block.
        """
        return self.get_identifier()

    def __eq__(self, obj: Block) -> bool:
        if isinstance(obj, Block):
            if self.dictionarify() == obj.dictionarify():
                return True

        return False

    def __hash__(self) -> int:
        return hash((self.namespace, self.base_name, tuple(sorted(self.states.items())), tuple(sorted(self.extra_data.items()))))

    def copy(self) -> Block:
        return Block(
            namespace=self.namespace,
            base_name=self.base_name,
            states=self.states,
            extra_data=self.extra_data,
            compability_version=self.compability_version,
        )

    def clear_extra_data(self) -> Block:
        another_self = self.copy()
        another_self.extra_data = {}
        return another_self


class MatrixStructure:
    """
    Class representing a Minecraft structure that
    consists of blocks and entities.

    Attributes
    ----------
    size
        The size of the structure.
    """

    structure_indecis: NDArray[np.intc]

    def __init__(
        self,
        size: tuple[int, int, int],
        fill: Optional[Block] = None,
        compability_version: int = COMPABILITY_VERSION,
    ):
        """
        Parameters
        ----------
        size
            The size of the structure.

        fill
            Fill the structure with this block at
            creation of a new structure object.

            However, extra datas of blocks cannot be filled.

            If this is set to ``None`` the structure
            is filled with "Structure Void" blocks.

            "None" is used as default.
        """

        self.structure_indecis: NDArray[np.intc]

        self._size = size
        self._palette: List[Block] = []
        self._special_blocks: Dict[int, Dict] = {}

        if fill is None:
            self.structure_indecis = np.full(size, nbtlib.Int(-1), dtype=np.intc)

        else:
            self.structure_indecis = np.zeros(size, dtype=np.intc)
            self._palette.append(fill)

        self.compability_version = compability_version

    @property
    def size(self) -> tuple[int, int, int]:
        return self._size

    def __repr__(self) -> str:
        return repr(self._get_str_array())

    def __str__(self) -> str:
        return str(self._get_str_array())

    def _get_str_array(
        self, *, with_namespace: bool = False, with_states: bool = False
    ) -> NDArray[Any]:
        """
        Returns a numpy array where each entry is a
        readable string of the corresponding block.

        Parameters
        ----------
        with_namespace
            Adds the namespace to the string if present.

        with_states
            Adds the block states to the string if present.
        """
        arr = self.get_structure().copy()
        vec = np.vectorize(
            partial(
                Block.stringify, with_namespace=with_namespace, with_states=with_states
            )
        )
        return vec(arr)

    def _add_block_to_palette(self, block: Optional[Block]) -> int:
        """
        Adds a block to the palette.

        Parameters
        ----------
        block
            The block to add. If this is set to ``None``
            "Structure Void" will be used.

        Returns
        -------
        The position of the block in the palette. This is
        ``-1`` when ``None`` is used as ``block``.
        """
        if block is None:
            return -1

        same_block = block.clear_extra_data()
        if same_block in self._palette:
            return self._palette.index(same_block)

        self._palette.append(same_block)
        return len(self._palette) - 1

    def mirror(self, axis: str) -> MatrixStructure:
        """
        Flips the structure.

        Parameters
        ----------
        axis
            Turn the structure either the ``X`` or ``Z`` axis.
            Use ``"X"``, ``"x"``,``"Z"`` or ``"z"``.
        """
        if axis in "Xx":
            self.structure_indecis = self.structure_indecis[::-1, :, :]
        elif axis in "Zz":
            self.structure_indecis = self.structure_indecis[:, :, ::-1]
        elif axis in "Yy":
            self.structure_indecis = self.structure_indecis[:, ::-1, :]
        else:
            raise ValueError(f"invalid argument for 'rotation' ({axis!r})")
        return self

    def rotate(self, by: int) -> MatrixStructure:
        """
        Rotates the structure.

        Parameters
        ----------
        by
            Rotates the structure by ``90``, ``180``
            or ``270`` degrees.
        """
        if by == 90:
            self.structure_indecis = np.rot90(self.structure_indecis, k=1, axes=(0, 1))
        elif by == 180:
            self.structure_indecis = np.rot90(self.structure_indecis, k=2, axes=(0, 1))
        elif by == 270:
            self.structure_indecis = np.rot90(self.structure_indecis, k=3, axes=(0, 1))
        else:
            raise ValueError(f"invalid argument for 'by' ({by!r})")
        return self

    def get_block(self, coordinate: Coordinate) -> Optional[Block]:
        """
        Returns the block in a specific position.

        Parameters
        ----------
        coordinate
            The coordinte of the block.
        """
        x, y, z = coordinate
        block = self._palette[self.structure_indecis[x, y, z]].copy()
        block_index = x * self.size[2] * self.size[1] + y * self.size[2] + z
        if block_index in self._special_blocks.keys():
            extra_data = self._special_blocks[block_index]
            if isinstance(extra_data, dict):
                block.extra_data.update(extra_data)
        return block

    def get_structure(self) -> NDArray[Any]:
        """
        Returns the structure as a numpy array filled
        with the corresponding `Block` objects.
        """
        arr = np.full(
            self.structure_indecis.shape,
            Block(
                "minecraft",
                "structure_void",
                compability_version=self.compability_version,
            ),
            dtype=object,
        )
        for key, block in enumerate(self._palette):
            arr[self.structure_indecis == key] = block

        for index, exdata in self._special_blocks.items():
            arr[int(index / (self.size[2] * self.size[1]))][
                int(index % (self.size[2] * self.size[1]) / self.size[2])
            ][
                (index % (self.size[2] * self.size[1]) % self.size[2])
            ].extra_data = exdata

        return arr

    def set_block(
        self,
        coordinate: Coordinate,
        block: Optional[Block],
    ) -> MatrixStructure:
        """
        Puts a block into the structure.

        Parameters
        ----------
        coordinate
            Relative coordinates of the block's position.

        block
            The block to place. If this is set to ``None``
            "Structure Void" blocks will be used.
        """
        x, y, z = coordinate

        ident = self._add_block_to_palette(block)

        self.structure_indecis[x, y, z] = ident
        if block:
            if block.extra_data:
                self._special_blocks[
                    x * self.size[2] * self.size[1] + y * self.size[2] + z
                ] = block.extra_data
        return self

    def fill_blocks(
        self,
        from_coordinate: Coordinate,
        to_coordinate: Coordinate,
        block: Optional[Block],
    ) -> MatrixStructure:
        """
        Puts multiple blocks into the structure.

        Notes
        -----
        Both start and end points are filled.

        Parameters
        ----------
        from_coordinate
            Relative coordinates of the start corner.

        to_coordinate
            Relative coordinates of the end corner.

        block
            The block to place. If this is set to ``None``
            "STructure Void" blocks will be used to fill.
        """
        fx, fy, fz = from_coordinate
        tx, ty, tz = to_coordinate

        ident = self._add_block_to_palette(block)

        self.structure_indecis[fx : tx + 1, fy : ty + 1, fz : tz + 1] = np.array(
            [
                [
                    [ident for k in range(abs(fz - tz) + 1)]
                    for j in range(abs(fy - ty) + 1)
                ]
                for i in range(abs(fx - tx) + 1)
            ],
            dtype=np.intc,
        ).reshape([abs(i) + 1 for i in (fx - tx, fy - ty, fz - tz)])

        if block:
            if block.extra_data:
                self._special_blocks.update(
                    dict(
                        zip(
                            [
                                (x * self.size[2] * self.size[1] + y * self.size[2] + z)
                                for x in range(fx, tx + 1)
                                for y in range(fy, ty + 1)
                                for z in range(fz, tz + 1)
                            ],
                            [
                                block.extra_data
                                for i in range(
                                    (abs(fx - tx) + 1)
                                    * (abs(fy - ty) + 1)
                                    * (abs(fz - tz) + 1)
                                )
                            ],
                        )
                    )
                )
        return self
