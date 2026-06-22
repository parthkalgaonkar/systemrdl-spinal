import os
import sys
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self
import pprint
import lark
import lark.exceptions


class Unpacked(int):
    pass


class Packed(int):
    pass


@dataclass
class Term:
    name: str
    unpacked: list[Unpacked]
    packed: Packed | None
    children: dict[str, Self] = field(default_factory=dict)


@lark.v_args(inline=True)
class HwifReportTransformer(lark.Transformer):
    def number(self, token):
        return int(token.value)

    def unpacked_range(self, right):
        return Unpacked(right + 1)

    def packed_range(self, left, right):
        assert left >= right, "Packed dimensions must be descending"
        return Packed(left - right + 1)

    def last_term(self, term, packed=None):
        return Term(term.name, term.unpacked, packed)

    def term(self, name_token, *unpacked):
        return Term(name_token.value, list(unpacked), None)

    @lark.v_args(inline=False)
    def line(self, children):
        for parent, child in zip(children[:-1], children[1:]):
            parent.children[child.name] = child
        return children[0]

    @lark.v_args(inline=False)
    def file(self, children):
        root = dict()

        def recursive_add(root, term):
            if term.name not in root:
                root[term.name] = term
                return
            for child in term.children.values():
                recursive_add(root[term.name].children, child)

        for child in children:
            recursive_add(root, child)
        return root


def get_parser():
    grammar = """
        file: (line _NEWLINE)+
        line: (term ".")* last_term
        last_term: term packed_range?
        term: CNAME unpacked_range*
        unpacked_range: "[" "0" ":" number "]"
        packed_range: "[" number ":" number "]"
        number: INT
        _NEWLINE: NEWLINE


        %import common.INT
        %import common.CNAME
        %import common.NEWLINE
        """
    return lark.Lark(grammar, start="file", propagate_positions=True)


def handle_error(file, err):
    meta = err.obj.meta
    line = meta.line
    column = meta.column
    orig_exc = err.orig_exc
    raise ValueError(f"Error in {file}: {line} {column}: {orig_exc!s}")


def parse(rpt_file: os.PathLike | io.TextIOBase) -> dict[str, Term]:
    try:
        with open(rpt_file, "r") as f:
            text = f.read()
        fname = rpt_file
    except TypeError:
        # rpt_file is already opened file
        text = rpt_file.read()
        fname = rpt_file.name
    parser = get_parser()
    transformer = HwifReportTransformer()
    tree = parser.parse(text)

    try:
        structures = transformer.transform(tree)
        err = None
    except lark.exceptions.VisitError as e:
        structures = None
        err = e

    if err is not None:
        handle_error(fname, err)

    return structures


def main():
    structures = parse(sys.argv[1])
    pprint.pprint(structures)


if __name__ == "__main__":
    main()
