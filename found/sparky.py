import logging
from uuid import uuid4

from immutables import Map

import found


log = logging.getLogger(__name__)


class SparkyException(Exception):
    pass


class PatternException(SparkyException):
    """Raised when the pattern can not be resolved by the query engine.

    .. warning:: It might be a bug. Try to re-order the pattern in the
                 query to make it work before reporting bug.

    """
    pass


PREFIX_DATA = b"\x00"
PREFIX_UUID = b"\x01"
PREFIX_POS = b"\x02"


class var:

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<var %r>" % self.name


def pattern_bind(pattern, binding):
    subject, predicate, object = pattern
    if isinstance(subject, var) and binding.get(subject.name) is not None:
        subject = binding[subject.name]
    if isinstance(predicate, var) and binding.get(predicate.name) is not None:
        predicate = binding[predicate.name]
    if isinstance(object, var) and binding.get(object.name) is not None:
        object = binding[object.name]
    return subject, predicate, object


class Sparky:

    __slots__ = ("_prefix",)

    var = var

    def __init__(self, prefix):
        self._prefix = prefix

    @found.transactional
    async def uuid(self, tr):
        uid = uuid4()
        key = found.pack((self._prefix, PREFIX_UUID, uid))
        value = await tr.get(key)
        if value is None:
            tr.set(key, b"")
            return uid
        raise SparkyException("Unlikely Error!")

    @found.transactional
    async def all(self, tr):
        start = found.pack((self._prefix, PREFIX_DATA))
        end = found.strinc(start)
        msg = "fetching everything between start=%r and end=%r"
        log.debug(msg, start, end)
        out = []
        items = await tr.range(start, end)
        for key, _ in items:  # value is always empty
            _, _, subject, predicate, object = found.unpack(key)
            out.append((subject, predicate, object))
        return out

    @found.transactional
    async def add(self, tr, *triples):
        for triple in triples:
            subject, predicate, object = triple
            # add in 'spo' aka. data
            key = found.pack((self._prefix, PREFIX_DATA, subject, predicate, object))
            tr.set(key, b"")
            # index in 'pos'
            key = found.pack((self._prefix, PREFIX_POS, predicate, object, subject))
            tr.set(key, b"")

    @found.transactional
    async def remove(self, tr, *triples):
        for triple in triples:
            subject, predicate, object = triple
            # remove from data
            key = found.pack((self._prefix, PREFIX_DATA, subject, predicate, object))
            tr.clear(key)
            # remove from index
            key = found.pack((self._prefix, PREFIX_POS, predicate, object, subject))
            tr.clear(key)

    @found.transactional
    async def _lookup_pos(self, tr, predicate, object):
        start = found.pack((self._prefix, PREFIX_POS, predicate, object))
        end = found.strinc(start)
        items = await tr.range(start, end)
        out = list()
        for key, _ in items:
            _, _, predicate, object, subject = found.unpack(key)
            out.append(subject)
        return out

    @found.transactional
    async def exists(self, tr, subject, predicate, object):
        key = found.pack((self._prefix, PREFIX_DATA, subject, predicate, object))
        value = await tr.get(key)
        return value is not None

    @found.transactional
    async def where(self, tr, pattern, *patterns):
        # seed bindings
        vars = tuple((isinstance(item, var) for item in pattern))
        if vars == (True, False, False):
            subject, predicate, object = pattern
            subjects = await self._lookup_pos(tr, predicate, object)
            name = subject.name
            bindings = [Map().set(name, subject) for subject in subjects]
        elif vars == (False, True, True):
            # TODO: extract to a method
            subject = pattern[0]
            start = found.pack((self._prefix, PREFIX_DATA, subject))
            end = found.strinc(start)
            items = await tr.range(start, end)
            bindings = []
            for key, _ in items:
                _, _, _, predicate, object = found.unpack(key)
                binding = Map()
                binding = binding.set(pattern[1].name, predicate)
                binding = binding.set(pattern[2].name, object)
                bindings.append(binding)
        else:
            raise PatternException()
        log.debug("seed bindings: %r", bindings)
        # contine matching other patterns, if any.
        for pattern in patterns:  # one
            log.debug("matching pattern: %r", pattern)
            next_bindings = []
            for binding in bindings:  # two
                pattern = pattern_bind(pattern, binding)
                log.debug("bound pattern: %r", pattern)
                vars = tuple((isinstance(item, var) for item in pattern))
                if vars == (False, False, False):
                    ok = await self.exists(tr, *pattern)
                    if ok:
                        # this binding is valid against this pattern,
                        # proceed with this binding and continue with
                        # the next pattern.
                        next_bindings.append(binding)
                elif vars == (False, False, True):
                    # TODO: extract to a method
                    subject, predicate, object = pattern
                    start = found.pack((self._prefix, PREFIX_DATA, subject, predicate))
                    end = found.strinc(start)
                    items = await tr.range(start, end)
                    bindings = []
                    for key, _ in items:
                        _, _, _, _, value = found.unpack(key)
                        binding = binding.set(object.name, value)
                        next_bindings.append(binding)
                elif vars == (True, False, False):
                    subject, predicate, object = pattern
                    subjects = await self._lookup_pos(tr, predicate, object)
                    name = subject.name
                    for subject in subjects:
                        new = binding.set(name, subject)
                        next_bindings.append(new)
                else:
                    raise PatternException()
            bindings = next_bindings
        return bindings
