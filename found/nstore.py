#
# Copyright (C) 2015-2019  Amirouche Boubekki <amirouche.boubekki@gmail.com>
#
# https://github.com/amirouche/found/
#
import logging
import itertools
from math import factorial

import found
from found.base import BaseFound
from found.base import FoundException

from immutables import Map


log = logging.getLogger(__name__)


def pk(*args):
    print(*args)
    return args[-1]


# Compute the minimal set of indices required to bind any n-pattern in
# one hop.
#
# Based on https://stackoverflow.com/a/55148433/140837


def bc(n, k):
    """Binomial coefficient"""
    return factorial(n) // factorial(k) // factorial(n - k) if k < n else 0


def stringify(iterable):
    return "".join(str(x) for x in iterable)


def combinations(tab):
    out = []
    for i in range(1, len(tab) + 1):
        out.extend(stringify(x) for x in itertools.combinations(tab, i))
    assert len(out) == 2 ** len(tab) - 1
    return out


def ok(solutions, tab):
    """Check that SOLUTIONS of TAB is a correct solution"""
    cx = combinations(tab)

    for combination in cx:
        pcx = ["".join(x) for x in itertools.permutations(combination)]
        # check for existing solution
        for solution in solutions:
            if any(solution.startswith(p) for p in pcx):
                # yeah, there is an existing solution
                break
        else:
            raise Exception("failed with combination={}".format(combination))
    else:
        return True
    return False


def _compute_indices(n):
    tab = list(range(n))
    cx = list(itertools.combinations(tab, n // 2))
    for c in cx:
        L = [(i, i in c) for i in tab]
        A = []
        B = []
        while True:
            for i in range(len(L) - 1):
                if (not L[i][1]) and L[i + 1][1]:
                    A.append(L[i + 1][0])
                    B.append(L[i][0])
                    L.remove((L[i + 1][0], True))
                    L.remove((L[i][0], False))
                    break
            else:
                break
        l = [i for (i, _) in L]  # noqa
        yield tuple(A + l + B)


def compute_indices(n):
    return list(_compute_indices(n))


# helpers


def take(iterator, count):
    for _ in range(count):
        out = next(iterator)
        yield out


def drop(iterator, count):
    for _ in range(count):
        next(iterator)
    yield from iterator


class NStoreException(FoundException):
    pass


class NotFound(NStoreException):
    pass


class Variable(BaseFound):

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<var %r>" % self.name


# XXX: use 'var' only in 'select' and 'where' queries
# please!
var = Variable


def stringify(list):
    return "".join(str(x) for x in list)


def is_permutation_prefix(combination, index):
    index = stringify(index)
    out = any(
        index.startswith(stringify(x)) for x in itertools.permutations(combination)
    )
    return out


class NStore(BaseFound):
    def __init__(self, name, prefix, items):
        self.name = name
        self._prefix = prefix
        self._items = items
        self._indices = compute_indices(len(items))

    @found.transactional
    async def add(self, tr, *items):
        """Add ITEMS to the associated database"""
        assert len(items) == len(self._items), "invalid item count"
        for subspace, index in enumerate(self._indices):
            permutation = list(items[i] for i in index)
            key = self._prefix + [subspace] + permutation
            tr.set(found.pack(tuple(key)), b"")

    @found.transactional
    async def remove(self, tr, *items):
        """Remove ITEMS from the associated database"""
        assert len(items) == len(self._items), "invalid item count"
        for subspace, index in enumerate(self._indices):
            permutation = list(items[i] for i in index)
            key = self._prefix + [subspace] + permutation
            tr.clear(found.pack(tuple(key)))

    async def ask(self, tr, *items):
        """Return True if ITEMS is found in the associated database"""
        assert len(items) == len(self._items), "invalid item count"
        subspace = 0
        key = self._prefix + [subspace] + list(items)
        out = await tr.get(found.pack(tuple(key)))
        out = out is not None
        return out

    async def select(self, tr, *pattern, seed=Map()):  # seed is immutable
        """Yields bindings that match PATTERN"""
        assert len(pattern) == len(self._items), "invalid item count"
        variable = tuple(isinstance(x, Variable) for x in pattern)
        # find the first index suitable for the query
        combination = tuple(x for x in range(len(self._items)) if not variable[x])
        for subspace, index in enumerate(self._indices):
            if is_permutation_prefix(combination, index):
                break
        else:
            raise NStoreException("oops!")
        # `index` variable holds the permutation suitable for the
        # query. `subspace` is the "prefix" of that index.
        prefix = list(pattern[i] for i in index if not isinstance(pattern[i], Variable))
        prefix = self._prefix + [subspace] + prefix
        start = found.pack(tuple(prefix))
        end = found.strinc(start)
        kvs = await tr.get_range(start, end)
        for key, _ in kvs:
            items = found.unpack(key)[len(self._prefix) + 1 :]
            # re-order the items
            items = tuple(items[index.index(i)] for i in range(len(self._items)))
            bindings = seed
            for i, item in enumerate(pattern):
                if isinstance(item, Variable):
                    bindings = bindings.set(item.name, items[i])
            yield bindings

    async def where(self, tr, iterator, *pattern):
        assert len(pattern) == len(self._items), "invalid item count"

        async for bindings in iterator:
            # bind PATTERN against BINDINGS
            bound = []
            for item in pattern:
                # if ITEM is variable try to bind
                if isinstance(item, Variable):
                    try:
                        value = bindings[item.name]
                    except KeyError:
                        # no bindings
                        bound.append(item)
                    else:
                        # pick the value in bindings
                        bound.append(value)
                else:
                    # otherwise keep item as is
                    bound.append(item)
            # hey!
            out = self.select(tr, *bound, seed=bindings)
            async for binding in out:
                yield binding
