#!/usr/bin/env python3

import sys
import random
import argparse
import pickle

from termcolor import colored
from time import sleep


class VM:

    DISPLAY_SPACING = 10
    INST_SZ = 128

    def __init__(self, size, speed=None, verbose=False, dmp_fmt=None):
        self.size = size
        self.pc = 0
        self.mem = [0] * self.size
        self.speed = speed
        self.is_halted = False

        # Sizeof system reserved registers at end of memory
        self.sys_len = 1

        # display
        self.debug = False
        self.verbose = verbose
        self.dmp_fmt = dmp_fmt

    #
    # Debugging utilities
    #

    def fmt(self, r):
        i, r = r
        a, b, c = self.decode()

        if self.dmp_fmt is not None:
            if i not in self.dmp_fmt:
                return ''
        if i == self.pc or i == a or i == b or i == c:
            s = str(r).ljust(self.DISPLAY_SPACING - 3)
        else:
            s = str(r).ljust(self.DISPLAY_SPACING)

        if i == self.pc:
            s = colored("PC:%s" % s, 'green')
        elif i == a:
            s = colored("A: %s" % s, 'red')
        elif i == b:
            s = colored("B: %s" % s, 'yellow')
        elif i == c:
            s = colored("C: %s" % s, 'cyan')

        return s

    def dump(self):
        if self.verbose:
            print("".join(map(self.fmt, enumerate(self.mem))))

    def dump_init(self):
        if self.verbose:
            print("".join("%-*d" % (
                self.DISPLAY_SPACING, i
            ) for i in range(self.size) if (
                    self.dmp_fmt is not None and i in self.dmp_fmt
                )
            ))

    #
    # Program loader utilities
    #

    def prog_parse_from_file(self, f_name):
        with open(f_name, 'rb') as f:
            x = pickle.load(f)
        return x

    def random_load(self):
        self.mem = [random.randrange(0, vm.size**3) for _ in range(self.size)]

    def load(self, prog):
        assert type(prog) == dict, "Program format invalid."
        assert '.text' in prog.keys(), (
                "Program does not contain .text section."
        )

        prog_size = len(prog['.text']) + self.sys_len
        if '.data' in prog.keys():
            data_len = sum(map(len, prog['.data']))
            prog_size += data_len
        if 'stack' in prog.keys():
            prog_size += prog['stack']
        assert prog_size <= self.size, (
                "Not enough memory to load this program "
                "(at least %s words required)." % prog_size
        )

        # LOAD .text to memory.
        for i, d in enumerate(prog['.text']):
            self.mem[i] = d

        if '.data' in prog.keys():
            for data in prog['.data']:
                assert isinstance(data, bytes), (
                        "Format error in .data section (should be bytes)"
                )
            for i, d in enumerate(b''.join(prog['.data'])):
                self.mem[self.size - data_len - self.sys_len + i] = d

    #
    # Implementation
    #

    def decode(self):
        b, c = divmod(self.mem[self.pc], self.INST_SZ)
        a, b = divmod(b, self.INST_SZ)
        if self.debug:
            print('Decoding instruction: %r' % dict(a=a, b=b, c=c))
        return a, b, c

    def subleq(self):
        a, b, c = self.decode()
        assert -self.size < a < self.size and -self.size < b < self.size, (
            "Segmentation fault."
        )

        aa = self.mem[a]
        bb = self.mem[b]

        self.mem[a] = aa - bb
        self.pc = (c if self.mem[a] <= 0 else self.pc + 1) % self.size

        if self.debug:
            print(dict(aa=aa, bb=bb, sub=aa-bb, nxt=self.pc))

    def tick(self):
        self.subleq()

        # Syscall write
        # Display the last memory word as ascii value ( % 127)
        # if value > 0
        if self.mem[-1] > 0:
            print('%s' % chr(self.mem[-1] % 127), end='')
            sys.stdout.flush()

        if self.pc == 0 and self.mem[0] == 0:
            self.is_halted = True

        if self.speed:
            sleep(self.speed)

    def run(self):
        while not self.is_halted:
            self.dump()
            self.tick()


def parse_dump_fmt(s):
    if s is None:
        return None
    for x in s:
        assert x in '0123456789,', "Bad format string."
    return [int(x) for x in s.split(',')]


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
            description='OISC VM implementation using subleq instructions.')
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('file', metavar='FILE', nargs='?', default=None,
                     help='Bytecode to load (compiled with asm.py)')
    grp.add_argument('--seed', '-S', metavar='SEED', default=None,
                     help='Seed for loading random program')
    parser.add_argument('--memsz', '-m', metavar='SIZE', default=16, type=int,
                        help='Change the virtual memory size (default is 16)')
    parser.add_argument(
            '--speed', '-s', type=float, default=0,
            help='VM speed (this goes into a sleep, so 0 => fast'
    )
    parser.add_argument(
            '--verbose', '-v', action='store_const', default=False,
            required='-d' in sys.argv or '--dump-fmt' in sys.argv,
            const=True, help='Enable verbose messages')
    parser.add_argument(
            '--dump-fmt', '-d', type=str, default=None,
            help='List of registers to dump when -v is present\n'
            'exemple: 13,14,15'
    )
    args = parser.parse_args()

    dmp_fmt = None
    try:
        dmp_fmt = parse_dump_fmt(args.dump_fmt)
    except AssertionError as e:
        print(e)
        exit()

    vm = VM(args.memsz, speed=args.speed,
            verbose=args.verbose, dmp_fmt=dmp_fmt)

    # Load a program (either from file or random)
    if args.file is not None:
        prog = vm.prog_parse_from_file(args.file)
        try:
            vm.load(prog)
        except AssertionError as e:
            print(e)
            exit()
    else:
        random.seed(args.seed)
        vm.random_load()

    # Init display and run.
    vm.dump_init()
    try:
        vm.run()
        print('Halted.')
    except AssertionError as e:
        print(e)
