import os
from pathlib import Path
import textwrap
import functools
from dataclasses import dataclass
from argparse import ArgumentParser, FileType
from typing import Self
from .hwif_report_parser import Term, parse
from .utils import Config, to_camel


bopen, bclose = "{}"

indent = functools.partial(textwrap.indent, prefix="  ")


@dataclass
class BundleCaseClass:
    name: str
    inner_classes: list[Self]
    members: dict[str, str]
    toplevel: bool

    def declaration(self):
        inner_classes = indent("\n\n".join(map(
                lambda x: x.declaration(),
                self.inner_classes
                )))
        members = indent("\n".join(map(
                lambda item: f"val {item[0]} = {item[1]}",
                self.members.items()
                )))

        retval = [
                f"case class {self.data_type()}() extends Bundle {bopen}",
                members,
                bclose
                ]
        if self.inner_classes:
            retval.insert(1, inner_classes)
        return "\n".join(retval)

    def data_type(self):
        name = f"{self.name}_bundle"
        if self.toplevel:
            return to_camel(name)
        else:
            return name


class TermVisitor:
    def walk(self, root: Term):
        _name, _dtype, case_class = self.visit_term(root)
        case_class.toplevel = True
        return case_class.declaration()

    def visit_term(self, term: Term) -> tuple[
            str,
            str,
            BundleCaseClass | None
            ]:
        if term.children:
            children = list(map(
                    lambda x: self.visit_term(x),
                    term.children.values()
                    ))
            inner_classes = list(filter(
                    lambda x: x is not None,
                    map(
                        lambda x: x[2],
                        children
                        )
                    ))
            members = dict(map(
                    lambda x: (x[0], x[1]),
                    children
                    ))
            case_class = BundleCaseClass(
                    name=term.name,
                    inner_classes=inner_classes,
                    members=members,
                    toplevel=False,
                    )
            data_type = f"{case_class.data_type()}()"
        else:
            case_class = None
            # Base case is no children
            if term.packed is None:
                data_type = "Bool()"
            else:
                data_type = f"Bits({term.packed} bits)"

        assert len(term.unpacked) <= 5, "SpinalHDL allows max 5 dimensions"

        if term.unpacked:
            unpacked_flat = ", ".join(map(str, term.unpacked))
            vec_type = f"Vec.fill({unpacked_flat})({data_type})"
        else:
            vec_type = data_type

        return term.name, vec_type, case_class


def generate(structures: dict[str, Term], config: Config):
    visitor = TermVisitor()
    package_decl = textwrap.dedent(
            f"""
            package {config.package_name}

            import spinal.core._
            import systemrdl_spinal._
            """).lstrip()
    classes = "\n\n".join(map(lambda x: visitor.walk(x), structures.values()))

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
                  val cpuif = PeakrdlCpuIf(
                    {config.addr_width}, {config.data_width}
                  )
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
