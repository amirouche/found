#
# __init__.py
#
# This source file is part of the FoundationDB open source project
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018 Amirouche Boubekki <amirouche@hypermove.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from found._fdb import lib
from found.base import open as open_impl
from found.base import transactional as transactional_impl
from found.base import strinc  # noqa
from found.base import Database  # noqa
from found.base import FoundError  # noqa
from found.base import FoundException  # noqa
from found.base import StreamingMode  # noqa

from fdb.tuple import pack  # noqa
from fdb.tuple import unpack  # noqa
from fdb.subspace_impl import Subspace  # noqa


__VERSION__ = (0, 3, 0)
VERSION = "v" + ".".join([str(x) for x in __VERSION__])


def open(*args, **kwargs):
    raise RuntimeError('You must call api_version() before using any fdb methods')


def transactional(*args, **kwargs):
    raise RuntimeError('You must call api_version() before using fdb.transactional')


def api_version(version):
    header_version = 510

    current_module = globals()

    try:
        _api_version = current_module['_api_version']
    except KeyError:
        pass
    else:
        raise RuntimeError('FDB API already loaded at version %d' % _api_version)

    if version > header_version:
        raise RuntimeError('Latest known FDB API version is %d' % header_version)

    code = lib.fdb_select_api_version_impl(version, header_version)
    if code == 2203:
        max_supported_ver = lib.fdb_get_max_api_version()
        if header_version > max_supported_ver:
            msg = "This version of the FoundationDB Python binding is not supported by "
            msg += "the installed FoundationDB C library. The binding requires a library "
            msg += "that supports API version %d, but the installed library supports a "
            msg += "maximum version of %d."
            msg = msg % (header_version, max_supported_ver)
            raise RuntimeError(msg)
        else:
            msg = "API version %d is not supported by the installed FoundationDB C library."
            msg = msg % version
            raise RuntimeError(msg)
    elif code != 0:
        raise RuntimeError("FoundationDB API error ({})".format(code))

    current_module['open'] = open_impl
    current_module['transactional'] = transactional_impl

    # set fdb._version in fdb because we rely on it
    # because found use fdb.tuple
    import fdb
    fdb._version = version

    current_module['_api_version'] = version
