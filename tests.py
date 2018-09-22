import asyncio
import logging
import pytest
from uuid import uuid4

import daiquiri
from fdb.tuple import SingleFloat

import found
from found import base


daiquiri.setup(logging.DEBUG, outputs=("stderr",))


found.api_version(510)


def test_pack_unpack():
    value = (
        (uuid4(), None, SingleFloat(3.1415), b"x42", 1, -1, 3.1415, -3.1415, ("abc",)),
        ("d", "e", "f"),
        2.718281828459045,
    )  # noqa
    assert found.unpack(found.pack(value)) == value


async def open():
    # XXX: hack around the fact that the loop is cached in found
    loop = asyncio.get_event_loop()
    base._loop = loop

    db = await found.open()
    # clean database
    tr = db._create_transaction()
    tr.clear_range(b"", b"\xff")
    await tr.commit()

    return db


@pytest.mark.asyncio
async def test_get():
    # preapre
    db = await open()
    tr = db._create_transaction()

    #
    out = await tr.get(b"test")
    assert out is None
    tr.set(b"test", b"test")
    out = await tr.get(b"test")
    assert out == b"test"


@pytest.mark.asyncio
async def test_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    for number in range(10):
        tr.set(found.pack((number,)), found.pack((str(number),)))
    await tr.commit()

    tr = db._create_transaction()
    out = await tr.get_range(found.pack((1,)), found.pack((8,)))
    await tr.commit()

    # check
    assert out
    for (key, value), index in zip(out, range(10)[1:-1]):
        assert found.unpack(key)[0] == index
        assert found.unpack(value)[0] == str(index)


@pytest.mark.asyncio
async def test_strinc_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    prefix_zero = b"\x00"
    tr.set(prefix_zero + b"\x01", found.pack((1,)))
    tr.set(prefix_zero + b"\x02", found.pack((2,)))
    tr.set(prefix_zero + b"\x03", found.pack((3,)))
    prefix_one = b"\x01"
    tr.set(prefix_one + b"\x42", found.pack((42,)))
    await tr.commit()

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(None, None)
    await tr.commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(prefix_zero, found.strinc(prefix_zero))
    await tr.commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_read_version():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    out = await tr.read_version()
    await tr.commit()

    # check
    assert out


@pytest.mark.asyncio
async def test_startswith():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    prefix_zero = b"\x00"
    tr.set(prefix_zero + b"\x01", found.pack((1,)))
    tr.set(prefix_zero + b"\x02", found.pack((2,)))
    tr.set(prefix_zero + b"\x03", found.pack((3,)))
    prefix_one = b"\x01"
    tr.set(prefix_one + b"\x42", found.pack((42,)))
    await tr.commit()

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(None, None)
    await tr.commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = await tr.get_range_startswith(prefix_zero)
    await tr.commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_transactional():
    @found.transactional
    async def deep(tr):
        out = await tr.get(b"\x00")
        return out

    @found.transactional
    async def txn(tr):
        tr.set(b"\x00", b"\x00")
        out = await deep(tr)
        return out

    # check
    db = await open()
    out = await txn(db)

    # check
    assert out == b"\x00"


# Sparky tests


@pytest.mark.asyncio
async def test_sparky_empty():
    db = await open()
    from found.sparky import Sparky

    sparky = Sparky(b"test-sparky")
    tuples = await sparky.all(db)
    assert tuples == []


@pytest.mark.asyncio
async def test_sparky_one_tuple():
    db = await open()
    from found.sparky import Sparky

    sparky = Sparky(b"test-sparky")
    expected = (2, 3, 4)
    await sparky.add(db, expected)
    tuples = await sparky.all(db)
    assert tuples == [expected]


@pytest.mark.asyncio
async def test_sparky_many_tuples():
    db = await open()
    from found.sparky import Sparky

    sparky = Sparky(b"test-sparky")
    expected = [(1, 2, 3), (1, 9, 8), (1, 3, 3)]
    expected.sort()  # XXX: sparky keeps ordering
    await sparky.add(db, *expected)
    tuples = await sparky.all(db)
    assert tuples == expected


@pytest.mark.asyncio
async def test_sparky_where_one_pattern():
    db = await open()
    from found.sparky import Sparky
    from found.sparky import var

    sparky = Sparky(b"test-sparky")
    data = [
        ("uid1", "title", "sparky"),
        ("uid1", "description", "rdf / sparql for humans"),
        ("uid2", "title", "hyperdev.fr"),
        ("uid2", "descrption", "forward and beyond!"),
    ]
    await sparky.add(db, *data)
    out = await sparky.where(db, ("uid1", var("key"), var("value")))
    out = [dict(x.items()) for x in out]
    assert out == [
        {"key": "description", "value": "rdf / sparql for humans"},
        {"key": "title", "value": "sparky"},
    ]


@pytest.mark.asyncio
async def test_sparky_where_several_pattern():
    db = await open()
    from found.sparky import Sparky
    from found.sparky import var

    sparky = Sparky(b"test-sparky")
    data = [
        ("uid1", "title", "sparky"),
        ("uid1", "description", "rdf / sparql for humans"),
        ("uid3", "blog", "uid1"),
        ("uid3", "title", "sparky query language"),
        ("uid2", "title", "hyperdev.fr"),
        ("uid2", "descrption", "forward and beyond!"),
    ]
    await sparky.add(db, *data)
    patterns = [
        (var("blog"), "title", "sparky"),
        (var("post"), "blog", var("blog")),
        (var("post"), "title", var("title")),
    ]
    out = await sparky.where(db, *patterns)
    out = [dict(x.items()) for x in out]
    assert out == [{"blog": "uid1", "post": "uid3", "title": "sparky query language"}]


@pytest.mark.asyncio
async def test_sparky_stuff():
    db = await open()
    from found.sparky import Sparky
    from found.sparky import var

    sparky = Sparky(b"test-sparky")
    tuples = [
        # abki
        ("74c69c2adfef4648b286b720c69a334b", "is a", "user"),
        ("74c69c2adfef4648b286b720c69a334b", "name", "abki"),
        # amz31
        ("f1e18a79a9564018b2cccef24911e931", "is a", "user"),
        ("f1e18a79a9564018b2cccef24911e931", "name", "amz31"),
        # abki says poor man social network
        ("78ad80d0cb7e4975acb1f222c960901d", "created-at", 1536859544),
        ("78ad80d0cb7e4975acb1f222c960901d", "expression", "poor man social network"),
        (
            "78ad80d0cb7e4975acb1f222c960901d",
            "html",
            "<p>poor man social network</p>\n",
        ),
        ("78ad80d0cb7e4975acb1f222c960901d", "modified-at", 1536859544),
        (
            "78ad80d0cb7e4975acb1f222c960901d",
            "actor",
            "74c69c2adfef4648b286b720c69a334b",
        ),
        # amz31 follow abki
        (
            "d563fd7cdbd84c449d36f1e6cf5893a3",
            "followee",
            "74c69c2adfef4648b286b720c69a334b",
        ),  # noqa
        (
            "d563fd7cdbd84c449d36f1e6cf5893a3",
            "follower",
            "f1e18a79a9564018b2cccef24911e931",
        ),  # noqa
        # abki says socialite for the win
        ("fe066559ce894d9caf2bca63c42d98a8", "created-at", 1536859522),
        ("fe066559ce894d9caf2bca63c42d98a8", "expression", "socialite for the win!"),
        ("fe066559ce894d9caf2bca63c42d98a8", "html", "<p>socialite for the win!</p>\n"),
        ("fe066559ce894d9caf2bca63c42d98a8", "modified-at", 1536859522),
        (
            "fe066559ce894d9caf2bca63c42d98a8",
            "actor",
            "74c69c2adfef4648b286b720c69a334b",
        ),
    ]
    await sparky.add(db, *tuples)
    everything = await sparky.all(db)
    assert len(everything) == len(tuples)

    user = "f1e18a79a9564018b2cccef24911e931"
    patterns = (
        (var("follow"), "follower", user),
        (var("follow"), "followee", var("followee")),
        (var("expression"), "actor", var("followee")),
        (var("expression"), "html", var("html")),
        (var("expression"), "modified-at", var("modified-at")),
        (var("followee"), "name", var("name")),
    )
    out = await sparky.where(db, *patterns)
    out.sort(key=lambda x: x["modified-at"], reverse=True)
    assert len(out) == 2
    assert [b["expression"] for b in out] == [
        "78ad80d0cb7e4975acb1f222c960901d",
        "fe066559ce894d9caf2bca63c42d98a8",
    ]  # noqa
