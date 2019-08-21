import asyncio
import logging
import pytest
from uuid import uuid4

import daiquiri
from fdb.tuple import SingleFloat

import found
from found import base


daiquiri.setup(logging.DEBUG, outputs=("stderr",))


found.api_version(600)


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
async def test_nstore_empty():
    db = await open()
    from found.nstore import NStore

    nstore = NStore("test-name", [42], ("subject", "predicate", "object"))


@pytest.mark.asyncio
async def test_simple_single_item_db_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")
    out = []
    async for item in triplestore.select(db, var("subject"), "title", "hyper.dev"):
        out.append(item)
    out = out[0]["subject"]
    assert out == expected


@pytest.mark.asyncio
async def test_ask_rm_and_ask():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")
    out = await triplestore.ask(db, expected, "title", "hyper.dev")
    assert out
    await triplestore.remove(db, expected, "title", "hyper.dev")
    out = await triplestore.ask(db, expected, "title", "hyper.dev")
    assert not out


@pytest.mark.asyncio
async def test_simple_multiple_items_db_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")
    await triplestore.add(db, uuid4(), "title", "blog.dolead.com")
    await triplestore.add(db, uuid4(), "title", "julien.danjou.info")
    out = []
    async for item in triplestore.select(db, var("subject"), "title", "hyper.dev"):
        out.append(item)
    out = out[0]["subject"]
    assert out == expected


@pytest.mark.asyncio
async def test_complex():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")
    dolead = uuid4()
    await triplestore.add(db, dolead, "title", "blog.dolead.com")
    await triplestore.add(db, dolead, "keyword", "corporate")
    julien = uuid4()
    await triplestore.add(db, julien, "title", "julien.danjou.info")
    await triplestore.add(db, julien, "keyword", "python")
    await triplestore.add(db, julien, "keyword", "hacker")

    seed = triplestore.select(db, var("identifier"), "keyword", "hacker")
    out = []
    async for item in triplestore.where(
        db, seed, var("identifier"), "title", var("blog")
    ):
        out.append(item)
    out = sorted([x["blog"] for x in out])
    assert out == ["hyper.dev", "julien.danjou.info"]


@pytest.mark.asyncio
async def test_seed_subject_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    dolead = uuid4()
    await triplestore.add(db, dolead, "title", "blog.dolead.com")
    await triplestore.add(db, dolead, "keyword", "corporate")

    julien = uuid4()
    await triplestore.add(db, julien, "title", "julien.danjou.info")
    await triplestore.add(db, julien, "keyword", "python")
    await triplestore.add(db, julien, "keyword", "hacker")

    out = []
    async for item in triplestore.select(db, var("subject"), "keyword", "corporate"):
        out.append(item)
    out = out[0]["subject"]

    assert out == dolead


@pytest.mark.asyncio
async def test_seed_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    dolead = uuid4()
    await triplestore.add(db, dolead, "title", "blog.dolead.com")
    await triplestore.add(db, dolead, "keyword", "corporate")

    julien = uuid4()
    await triplestore.add(db, julien, "title", "julien.danjou.info")
    await triplestore.add(db, julien, "keyword", "python")
    await triplestore.add(db, julien, "keyword", "hacker")

    out = []
    async for item in triplestore.select(db, dolead, var("key"), var("value")):
        out.append(item)
    out = [dict(x) for x in out]

    expected = [
        {"key": "keyword", "value": "corporate"},
        {"key": "title", "value": "blog.dolead.com"},
    ]
    assert out == expected


@pytest.mark.asyncio
async def test_seed_object_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    dolead = uuid4()
    await triplestore.add(db, dolead, "title", "blog.dolead.com")
    await triplestore.add(db, dolead, "keyword", "corporate")

    julien = uuid4()
    await triplestore.add(db, julien, "title", "julien.danjou.info")
    await triplestore.add(db, julien, "keyword", "python")
    await triplestore.add(db, julien, "keyword", "hacker")

    out = []
    async for item in triplestore.select(db, hyperdev, "title", var("title")):
        out.append(item)

    out = out[0]["title"]
    assert out == "hyper.dev"


@pytest.mark.asyncio
async def test_subject_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    # prepare
    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")
    post1 = uuid4()
    await triplestore.add(db, post1, "blog", hyperdev)
    await triplestore.add(db, post1, "title", "hoply is awesome")
    post2 = uuid4()
    await triplestore.add(db, post2, "blog", hyperdev)
    await triplestore.add(db, post2, "title", "hoply triple store")

    # exec, fetch all blog title from hyper.dev
    query = triplestore.select(db, var("blog"), "title", "hyper.dev")
    query = triplestore.where(db, query, var("post"), "blog", var("blog"))
    out = []
    async for item in triplestore.where(db, query, var("post"), "title", var("title")):
        out.append(item)
    out = sorted([x["title"] for x in out])
    assert out == ["hoply is awesome", "hoply triple store"]
