import io
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


def to_camel(string: str):
    return "".join(map(
            lambda x: x.title(),
            string.split("_")
            ))


@dataclass
class Config:
    output: str
    module_name: str
    hwif_report: io.TextIOBase
    addr_width: int
    data_width: int
    reset_style: str = "rst"
    package_name: Optional[str] = None

    @classmethod
    def from_cli_args(cls, cli_args):
        module_name = Path(
                cli_args.hwif_report.name
                ).stem.removesuffix("_hwif")
        return cls(module_name=module_name, **vars(cli_args))
