import os
from pathlib import Path
import textwrap
import functools
import itertools
from dataclasses import dataclass, replace
from argparse import ArgumentParser, FileType
from typing import Self, Protocol
from .hwif_report_parser import Term, parse
from .utils import Config, to_camel


bopen, bclose = "{}"

indent = functools.partial(textwrap.indent, prefix="  ")


class DataType(Protocol):
    def declaration(self) -> str: ...
    def instance(self) -> str: ...
    def dimensions(self) -> tuple[int, ...]: ...

    def instantiation(self) -> str:
        if not self.dimensions():
            return self.instance()
        dimensions = ", ".join(map(str, self.dimensions()))
        return f"Vec.fill({dimensions})({self.instance()})"


@dataclass
class VecType:
    vec_dimensions: tuple[int, ...]

    def dimensions(self):
        return self.vec_dimensions


@dataclass
class SpinalBits(VecType, DataType):
    width: int

    def declaration(self):
        raise ValueError("Primitive has no declaration")

    def instance(self):
        return f"Bits({self.width} bits)"


@dataclass
class SpinalBool(VecType, DataType):
    def declaration(self):
        raise ValueError("Primitive has no declaration")

    def instance(self):
        return f"Bool()"


@dataclass
class BundleCaseClass(VecType, DataType):
    name: str
    members: dict[str, DataType]

    def declaration(self):
        retval = [f"case class {self.name}() extends Bundle {bopen}"]
        for member_name, member_type in self.members.items():
            retval.append(f"  val {member_name} = {member_type.instantiation()}")
        retval.append(bclose)
        return "\n".join(retval)

    def instance(self):
        return f"{self.name}()"


class TermVisitor:
    def walk(self, root: Term):
        self.stack: list[str] = list()
        self.class_types = []
        self.visit(root)
        return self.class_types

    def visit(self, term: Term) -> DataType:
        assert len(term.unpacked) <= 5, "SpinalHDL allows max 5 dimensions"
        self.stack.append(term.name)
        retval = self.visit_term(term)
        self.stack.pop()
        if not self.stack:
            retval.name = to_camel(retval.name)
        return retval

    def visit_term(self, term: Term) -> DataType:
        newtype_name = "__".join(self.stack) + "_bundle"
        if term.children:
            children = dict(map(
                lambda item: (item[0], self.visit(item[1])),
                term.children.items(),
                ))
            retval = BundleCaseClass(
                    name=newtype_name,
                    members=children,
                    vec_dimensions=term.unpacked
                    )
            self.class_types.append(retval)
            return retval
        elif term.packed is not None:
            return SpinalBits(
                    width=int(term.packed),
                    vec_dimensions=term.unpacked,
                    )
        else:
            return SpinalBool(vec_dimensions=term.unpacked)


def generate(structures: dict[str, Term], config: Config):
    visitor = TermVisitor()
    package_decl = textwrap.dedent(
            f"""
            package {config.package_name}

            import spinal.core._
            import systemrdl_spinal._
            """).lstrip()
    classes = "\n\n".join(map(
            lambda c: c.declaration(),
            functools.reduce(
                lambda a, b: a + b,
                map(lambda x: visitor.walk(x), structures.values())
                )
            ))

    component_name = to_camel(config.module_name)
    component_decl = textwrap.dedent(
            f"""
            class {component_name} extends PeakrdlRegblockShim(
              HwifInBundle(),
              HwifOutBundle(),
              {config.addr_width},
              {config.data_width}
            )
            """).strip()

    companion_object = textwrap.dedent(
            f"""
            object {component_name} extends App {bopen}
              class {component_name}Top extends Component {bopen}
                val io = new Bundle {bopen}
                  val cpuif = slave(PeakrdlCpuIf({config.addr_width}, {config.data_width}))
                  val hwif_in = in (HwifInBundle())
                  val hwif_out = out (HwifOutBundle())
                {bclose}

                val regblock = new {component_name}()
                regblock.io.s_cpuif <> io.cpuif
                regblock.io.hwif_in := io.hwif_in
                io.hwif_out := regblock.io.hwif_out
              {bclose}

              val config = SpinalConfig(
                withTimescale = false,
                targetDirectory = "gen",
                oneFilePerComponent = true,
                genLineComments = true
              )

              config.generateSystemVerilog(new {component_name}Top())
            {bclose}
            """)

    text = "\n\n".join([
            package_decl,
            classes,
            component_decl,
            companion_object,
            ])
    os.makedirs(config.output, exist_ok=True)
    with open(Path(config.output) / f"{component_name}.scala", "w") as f:
        f.write(text)


def get_parser():
    parser = ArgumentParser("systemrdl_spinal.gen_scala_wrapper")
    parser.add_argument(
            "hwif_report",
            type=FileType('r'),
            help="HWIF report generated by peakrdl-regblock",
            )
    parser.add_argument(
            "package_name",
            help="Name of scala package for file",
            )
    parser.add_argument(
            "-o",
            dest="output",
            metavar="OUTPUT",
            help="Output path",
            required=True,
            )
    parser.add_argument(
            "--addr-width",
            type=int,
            help="Address width of cpu interface",
            default=32,
            )
    parser.add_argument(
            "--data-width",
            type=int,
            help="Data width for cpu interface",
            default=32,
            )
    return parser


def main(args=None):
    cli_args = get_parser().parse_args(args)
    config = Config.from_cli_args(cli_args)
    structures = parse(config.hwif_report)
    generate(structures, config)


if __name__ == "__main__":
    main()
