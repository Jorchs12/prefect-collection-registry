import inspect
import json
import logging
from abc import ABC
from importlib.metadata import entry_points
from sys import argv
from types import ModuleType
from typing import Any, Dict, List, Type
from uuid import uuid4

from prefect.blocks.core import Block
from prefect.plugins import safe_load_entrypoints


def generate_block_metadata(block_subcls: Type[Block]) -> Dict[str, Any]:
    """
    Takes a block subclass and returns a JSON dict representation of
    its corresponding block type and block schema.
    """
    block_type_dict = block_subcls._to_block_type().dict(
        exclude={"id", "created", "updated", "is_protected"}, json_compatible=True
    )
    block_type_dict["block_schema"] = block_subcls._to_block_schema(
        block_type_id=uuid4()
    ).dict(
        exclude={"id", "created", "updated", "block_type_id", "block_type"},
        json_compatible=True,
    )

    return block_type_dict


def generate_block_metadata_for_module(module: ModuleType):
    block_subclasses = discover_block_subclasses(module)
    return {
        block_subcls.get_block_type_slug(): generate_block_metadata(block_subcls)
        for block_subcls in block_subclasses
    }


def discover_block_subclasses(module: ModuleType) -> List[Type[Block]]:
    return [
        cls
        for _, cls in inspect.getmembers(module)
        if Block.is_block_class(cls)
        and cls.__name__ != "Block"
        and ABC not in getattr(cls, "__bases__", [])
    ]


def generate_full_metadata(collection_slug: str):
    collections = safe_load_entrypoints(entry_points(group="prefect.collections"))
    output_dict = {}
    for ep_name, module in collections.items():
        if isinstance(module, Exception):
            logging.warning(f"Error loading collection entrypoint {ep_name} - skipping")
            continue
        discovered_collection_slug = module.__name__.split(".")[0].replace("_", "-")
        if collection_slug != discovered_collection_slug:
            continue

        output_dict["block_types"] = {
            **output_dict.get("block_types", {}),
            **generate_block_metadata_for_module(module),
        }
    return output_dict


def write_collection_metadata(
    collection_metadata: Dict[str, Any], collection_slug: str
):
    with open(f"{collection_slug}.json", "w") as f:
        json.dump(collection_metadata, f, indent=2)


if __name__ == "__main__":
    collection_slug = argv[1]
    collection_metadata = generate_full_metadata(collection_slug)
    write_collection_metadata(collection_metadata, collection_slug)
