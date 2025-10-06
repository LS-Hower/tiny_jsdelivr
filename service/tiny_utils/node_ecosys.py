# 2025-10-01  tiny_utils/node_ecosys.py

from typing import Optional, TypedDict

import nodesemver


class _DistObjectJson(TypedDict):
    tarball: str

class _VersionValueJson(TypedDict):
    dist: _DistObjectJson


# A type describing the registry json file, for type hinting.
# Written this way because `dist-tags` is not a valid Python identifier.
ValidRegistryJson = TypedDict('ValidRegistryJson', {
    'dist-tags': dict[str, str],
    'versions':  dict[str, _VersionValueJson],
})


def find_entry_file_from_package_json(package_json: dict) -> Optional[str]:
    try:
        res = package_json['jsdelivr']
        assert isinstance(res, str)
        return res
    except:
        pass

    try:
        res = package_json['exports']['.']['default']
        assert isinstance(res, str)
        return res
    except:
        pass

    try:
        res = package_json['exports']['.']
        assert isinstance(res, str)
        return res
    except:
        pass

    try:
        res = package_json['main']
        assert isinstance(res, str)
        return res
    except:
        pass

    return None


class NodeVersionRange(object):
    def __init__(self, range_str: str, loose: bool = False) -> None:
        self._range = nodesemver.Range(range_str, loose)
        self._raw_str = range_str

    def __contains__(self, version: str) -> bool:
        return nodesemver.satisfies(version, self._range)

    def __str__(self) -> str:
        return self._raw_str


def is_valid_version(version_str: str) -> bool:
    try:
        return bool(nodesemver.valid(version_str, False))
    except:
        return False


def semver_cmp(version1: str, version2: str, loose: bool = False) -> int:
    """
    `-1` if `version1` <  `version2`,
    `0`  if `version1` == `version2`,
    `1`  if `version1` >  `version2`.
    """
    return nodesemver.compare(version1, version2, loose)
