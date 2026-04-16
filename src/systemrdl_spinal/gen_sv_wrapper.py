import os
from pathlib import Path
from typing import Protocol, Any
import functools
import textwrap
from argparse import ArgumentParser, FileType
from .hwif_report_parser import Term, parse
from .utils import Config, to_camel


class TermVisitor(Protocol):
    def handle_term(self, term: Term, path: list[str | int]) -> None: ...
    def cleanup(self, root: Term) -> Any: ...

    def setup(self, root: Term) -> None:
        if root.name == "hwif_in":
            self.direction = "input"
        else:
            self.direction = "output"

    def visit_term(self, term: Term, path: list[str | int], indices: tuple):
        num_unpacked = len(term.unpacked)
        used_indices = len(indices)
        if used_indices < num_unpacked:
            for i in range(term.unpacked[used_indices]):
                self.visit_term(term, path, (*indices, i))
            return

        if term.children:
            for k, v in term.children.items():
                self.visit_term(v, path + list(indices) + [k], ())
            return

        self.handle_term(term, path + list(indices))

    def walk(self, root: Term):
        self.setup(root)
        self.visit_term(root, [root.name], ())
        return self.cleanup(root)


class DebugTermVisitor(TermVisitor):
    def handle_term(self, term: Term, path: list[str | int]) -> None:
        print(f"{path} - [{term.packed}]")


def _flat_name(path: list[str | int]):
    return "_".join(map(str, path))


def _struct_name(path: list[str | int]):
    name = ""
    for element in path:
        if isinstance(element, int):
            name += f"[{element}]"
        elif name == "":
            name += element
        else:
            name += f".{element}"
    return name


class PortDeclaration(TermVisitor):
    def setup(self, root):
        TermVisitor.setup(self, root)
        self.lines: list[str] = []

    def handle_term(self, term: Term, path: list[str | int]) -> None:
        name = _flat_name(path)
        packed = ""
        if term.packed is not None:
            packed = f"[{term.packed-1}:0] "
        line = f"{self.direction} logic {packed}{name},\n"
        self.lines.append(line)

    def cleanup(self, _root: Term) -> list[str]:
        return "".join(self.lines)


class StructAssignment(TermVisitor):
    def setup(self, root):
        TermVisitor.setup(self, root)
        self.lines: list[str] = []

    def handle_term(self, _: Term, path: list[str | int]) -> None:
        flat_name = _flat_name(path)
        struct_name = _struct_name(path)
        if self.direction == "input":
            self.lines.append(f"{struct_name} = {flat_name};")
        else:
            self.lines.append(f"{flat_name} = {struct_name};")

    def cleanup(self, _root: Term) -> list[str]:
        return "\n".join(self.lines)


indent = functools.partial(textwrap.indent, prefix="    ")


def generate(structures: dict[str, Term], config: Config):
    portlist_visitor = PortDeclaration()
    assignment_visitor = StructAssignment()

    # creating these variables just to avoid smart-indentation problems
    bopen, bclose = "()"

    # Will keep the clock and reset as the last ports.
    # This avoids having to deal with the last comma in the port list
    clock_reset = textwrap.dedent(
            """
            input logic clk,
            input logic rst
            """).strip()
    cpuif_lines = textwrap.dedent(
            f"""
            input logic s_cpuif_req,
            input logic s_cpuif_req_is_wr,
            input logic [{config.addr_width-1}:0] s_cpuif_addr,
            input logic [{config.data_width-1}:0] s_cpuif_wr_data,
            input logic [{config.data_width-1}:0] s_cpuif_wr_biten,
            output logic s_cpuif_req_stall_wr,
            output logic s_cpuif_req_stall_rd,
            output logic s_cpuif_rd_ack,
            output logic s_cpuif_rd_err,
            output logic [{config.data_width-1}:0] s_cpuif_rd_data,
            output logic s_cpuif_wr_ack,
            output logic s_cpuif_wr_err,
            """).strip()

    struct_decls = textwrap.dedent(
            f"""
            {config.module_name}_pkg::{config.module_name}__in_t hwif_in;
            {config.module_name}_pkg::{config.module_name}__out_t hwif_out;
            """).strip()

    core_instantiation = textwrap.dedent(
            f"""
            {config.module_name} I_{config.module_name} {bopen}
                .clk (clk),
                .{config.reset_style} (rst),
                .s_cpuif_req (s_cpuif_req),
                .s_cpuif_req_is_wr (s_cpuif_req_is_wr),
                .s_cpuif_addr (s_cpuif_addr),
                .s_cpuif_wr_data (s_cpuif_wr_data),
                .s_cpuif_wr_biten (s_cpuif_wr_biten),
                .s_cpuif_req_stall_wr (s_cpuif_req_stall_wr),
                .s_cpuif_req_stall_rd (s_cpuif_req_stall_rd),
                .s_cpuif_rd_ack (s_cpuif_rd_ack),
                .s_cpuif_rd_err (s_cpuif_rd_err),
                .s_cpuif_rd_data (s_cpuif_rd_data),
                .s_cpuif_wr_ack (s_cpuif_wr_ack),
                .s_cpuif_wr_err (s_cpuif_wr_err),
                .hwif_in (hwif_in),
                .hwif_out (hwif_out)
            {bclose};
            """).strip()

    struct_ports = "\n".join(
            map(lambda x: portlist_visitor.walk(x), structures.values())
            )
    struct_assignment = "\n".join(
            map(lambda x: assignment_visitor.walk(x), structures.values())
            )

    port_list = indent(
            cpuif_lines + "\n\n" + struct_ports + "\n" + clock_reset
            )
    always_comb = "\n".join([
            "always_comb begin",
            indent(struct_assignment),
            "end",
            ""
            ])
    module_internals = indent(
            struct_decls + "\n" + always_comb + "\n" + core_instantiation
            )
    shim_name = to_camel(config.module_name)

    full_module = "\n".join([
            f"module {shim_name} {bopen}",
            port_list,
            f"{bclose};",
            "",
            module_internals,
            "endmodule"
            ])

    os.makedirs(config.output, exist_ok=True)
    with open(Path(config.output) / f"{shim_name}.sv", "w") as f:
        f.write(full_module)


def get_parser():
    parser = ArgumentParser("systemrdl_spinal.gen_sv_wrapper")
    parser.add_argument(
            "hwif_report",
            type=FileType('r'),
            help="HWIF report generated by peakrdl-regblock",
            )
    parser.add_argument(
            "-o",
            dest="output",
            metavar="OUTPUT",
            help="Output path",
            required=True,
            )
    parser.add_argument(
            "--reset-style",
            default="rst",
            help="Style of reset used",
            choices=["rst", "rst_n", "arst", "arst_n"],
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
