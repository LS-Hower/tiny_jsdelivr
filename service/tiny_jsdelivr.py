# 2025-09-21  tiny_jsdelivr.py

import heapq
import json
import logging
import mimetypes
import os
import tarfile
from dataclasses import dataclass
from functools import cmp_to_key

import requests
from flask import Flask, request, Response

import tiny_htmls
from tiny_utils.network import PathInfo, RequestNotValidError
from tiny_utils.network import make_response_altered
from tiny_utils.node_ecosys import ValidRegistryJson
from tiny_utils.node_ecosys import is_valid_version, NodeVersionRange
from tiny_utils.node_ecosys import find_entry_file_from_package_json
from tiny_utils.general import get_entry_size, size_text


app = Flask(__name__)


NPM_REGISTRY_URL_BEGIN = os.getenv(
    'REGISTRY', 'https://registry.npmjs.org'
).rstrip('/')
CONTENT_TYPE_UTF_8_TEXT = 'text/plain'
CONTENT_TYPE_UTF_8_HTML = 'text/html'
CONTENT_TYPE_IMAGE_ICO = 'image/icon'
CACHE_FOLDER = 'tiny_jsdelivr_cache'
CACHE_FOLDER_SIZE_THRESHOLD = (2 ** 20) * 1  # 1 MB


def report_cache_folder_size(logger: logging.Logger) -> None:
    """Show a warning if the cache folder is too large."""

    ls = [
        (
            get_entry_size(os.path.join(CACHE_FOLDER, entry)),
            entry + '/' \
                if os.path.isdir(os.path.join(CACHE_FOLDER, entry)) \
                else entry
        )
        for entry in os.listdir(CACHE_FOLDER)
    ]

    folder_size = sum(size for size, _ in ls)

    if folder_size < CACHE_FOLDER_SIZE_THRESHOLD:
        return

    def compare_size_entry(lhs: tuple[int, str], rhs: tuple[int, str]) -> int:
        """Compare by size (reversed), then by entry name."""
        size1, entry1 = lhs
        size2, entry2 = rhs

        assert entry1 != entry2, f"Unexpected duplicate entry: {entry1}"

        if size1 < size2:
            return 1
        elif size1 > size2:
            return -1

        if entry1 < entry2:
            return -1
        elif entry1 > entry2:
            return 1

        assert False, f"Unexpected duplicate entry: {entry1}"

    to_report = heapq.nsmallest(10, ls, key=cmp_to_key(compare_size_entry))

    msg = "Cache folder size is too large: {:s}.\n".format(
        size_text(folder_size)
    )

    msg += 'Large cache entries:\n'

    msg += '\n'.join(
        "- {:>12s}: {:s}".format(size_text(size), entry)
        for size, entry in to_report
    )

    return logger.warning(msg)


@dataclass
class FeasibleVersionsList(object):
    versions:                 list[str]
    version_is_designated:    bool

    @staticmethod
    def make(
            version_spec_str: str,
            registry_json: ValidRegistryJson
            ) -> 'FeasibleVersionsList':
        """
        Check all versions in `registry_json['versions']`.
        Return versions satisfying `version_spec_str`.
        """
        if version_spec_str == 'dist-tags':
            # A string `'dist-tags'`.
            # Show all versions with their dist-tags.
            return FeasibleVersionsList(
                [ ver for ver in registry_json['dist-tags'].values() ],
                False
            )

        if version_spec_str == 'all':
            # A string `'all'`.
            # Show all versions.
            return FeasibleVersionsList(
                [ ver for ver in registry_json['versions'].keys() ],
                False
            )

        if is_valid_version(version_spec_str):
            # An exact version. Show content of it.
            if version_spec_str not in registry_json['versions']:
                return FeasibleVersionsList([], False)
            return FeasibleVersionsList([version_spec_str], True)

        try:
            # A version range.
            # Show all versions that satisfy the range.
            ver_range = NodeVersionRange(version_spec_str)
            return FeasibleVersionsList(
                [
                    ver
                    for ver in registry_json['versions'].keys()
                    if ver in ver_range
                ],
                False
            )
        except:
            pass

        try:
            # A exact `dist-tag`. Show content of the corresponding version.
            if version_spec_str not in registry_json['dist-tags']:
                return FeasibleVersionsList([], False)
            return FeasibleVersionsList(
                [registry_json['dist-tags'][version_spec_str]], True
            )
        except:
            pass

        return FeasibleVersionsList([], False)




@app.route('/')
def home_page() -> Response:
    return make_response_altered(
        tiny_htmls.home_page(), 200, CONTENT_TYPE_UTF_8_HTML
    )

@app.route('/<path:thepath>')
def delivr(thepath: str) -> Response:
    """
    Handle jsDelivr request.
    Also handle exceptions.
    """
    assert f"/{thepath}" == request.path

    try:
        return handle_path(request.path)
    except RequestNotValidError as e:
        return make_response_altered(
            f"Request Not Valid:\n{e}", e.status_code, CONTENT_TYPE_UTF_8_TEXT
        )
    except Exception as e:
        raise e


def handle_path(abs_path: str) -> Response:
    """
    Handle jsDelivr request.
    """
    if abs_path == '/favicon.ico':
        # The icon. My Chrome browser really wanted this, so I drew it.
        if not os.path.exists('favicon.ico'):
            raise RuntimeWarning("favicon.ico not found")
        with open('favicon.ico', 'rb') as f:
            return make_response_altered(f.read(), 200, CONTENT_TYPE_IMAGE_ICO)

    # Parse path, getting package name, version requirement,
    # and file (directory) name.
    path_info = PathInfo.make(abs_path)

    # Download json from registry website.
    registry_json = get_registry_json(path_info.package_name)

    # Get versions that satisfy the requirement.
    feasible_vers = FeasibleVersionsList.make(
        path_info.version_spec_str, registry_json
    )

    if len(feasible_vers.versions) == 0:
        # No version satisfies the requirement.
        # Then show all versions to user.
        return make_response_altered(
            tiny_htmls.all_versions_page(registry_json, path_info),
            400, CONTENT_TYPE_UTF_8_HTML
        )

    if not feasible_vers.version_is_designated:
        # A set of version(s) satisfies the requirement.
        # Length of the set may be 1. Consider a user entered a version range
        # and there happens to be only one version that meets this requirement.
        # This situation is also included in this branch.
        # Then list all feasible versions.
        return make_response_altered(
            tiny_htmls.versions_page(
                feasible_vers.versions,
                registry_json,
                path_info,
            ),
            200, CONTENT_TYPE_UTF_8_HTML
        )

    # User entered an exact version or a dist-tag.
    # So the version is designated explicitly.
    assert len(feasible_vers.versions) == 1
    exact_version = feasible_vers.versions[0]

    local_name = "{:s}-{:s}".format(path_info.package_name, exact_version)
    download_and_unpack_tarball(registry_json, exact_version, local_name)

    # Show directory or file.
    return give_file_or_dir(path_info, local_name)


def get_registry_json(package_name: str) -> ValidRegistryJson:
    """
    Download the json, which holds meta data of the package,
    from registry website.
    """
    registry_json_url = "{:s}/{:s}".format(
        NPM_REGISTRY_URL_BEGIN, package_name
    )

    # Not cached.
    r = requests.get(registry_json_url)
    if r.status_code == 404:
        raise RequestNotValidError(404, f"package {package_name} not found")
    r.raise_for_status()
    registry_json: ValidRegistryJson = r.json()

    return registry_json


def download_and_unpack_tarball(
        registry_json: ValidRegistryJson, exact_version: str, local_name: str
        ) -> None:
    """
    Download the tarball and save to disk, then untar it.
    If already exists, just skip.
    """

    flag_new_dir_or_file_cached = False

    tarball_path = f"./{CACHE_FOLDER}/{local_name}.tgz"
    if not os.path.exists(tarball_path):
        # Download & save.
        tarball_url = \
            registry_json['versions'][exact_version]['dist']['tarball']
        r = requests.get(tarball_url)
        r.raise_for_status()
        with open(tarball_path, 'wb') as f:
            f.write(r.content)
        flag_new_dir_or_file_cached = True

    tarball_unpacked_dir_path = f"./{CACHE_FOLDER}/{local_name}"
    if not os.path.exists(tarball_unpacked_dir_path):
        # Decompress.
        tar = tarfile.open(tarball_path)
        tar.extractall(tarball_unpacked_dir_path)
        flag_new_dir_or_file_cached = True
        tar.close()

    if flag_new_dir_or_file_cached:
        report_cache_folder_size(app.logger)


def give_file_or_dir(path_info: PathInfo, local_name: str) -> Response:
    """Return the file content or directory listing."""
    if not path_info.obj_absolute_path:
        # Entry file.
        return give_entry_file(path_info, local_name)
    elif path_info.obj_absolute_path.is_dir():
        # Directory.
        # Find all files in the directory, and list them.
        return give_directory(path_info, local_name)
    else:
        # Designated file.
        return give_file(path_info, local_name)


def give_entry_file(path_info: PathInfo, local_name: str) -> Response:
    """Find the entry file of the package, then return its content."""
    package_json_path = "./{:s}/{:s}/package/package.json".format(
        CACHE_FOLDER, local_name
    )
    # If `package.json` does not exist
    if not os.path.exists(package_json_path):
        raise RequestNotValidError(
            404,
            "Couldn't find the `package.json` in {:s}.".format(
                path_info.package_name
            )
        )
    with open(package_json_path, 'r', encoding='utf-8') as f:
        package_json = json.load(f)
    path_from_package = find_entry_file_from_package_json(package_json)
    if not path_from_package:
        raise RequestNotValidError(
            404, 'Error: No entry file path found in package.json'
        )

    path_from_script = "./{:s}/{:s}/package/{:s}".format(
        CACHE_FOLDER, local_name, path_from_package
    )
    # If the entry file does not exist
    if not os.path.exists(path_from_script):
        raise RequestNotValidError(
            404,
            "Couldn't find the entry file {:s} in {:s}.".format(
                path_from_script, path_info.package_name
            )
        )

    with open(path_from_script, 'rb') as f:
        content = f.read()
    return make_response_altered(
        content,
        200,
        mimetypes.guess_file_type(path_from_script)
    )


def give_directory(path_info: PathInfo, local_name: str) -> Response:
    """
    Find the designated directory in the package, then list all files in it.
    """
    path_from_script = "./{:s}/{:s}/package{}".format(
        CACHE_FOLDER, local_name, path_info.obj_absolute_path
    )
    # If the directory does not exist
    if not os.path.exists(path_from_script):
        raise RequestNotValidError(
            404,
            "Couldn't find the directory {:s} in {:s}.".format(
                path_from_script, path_info.package_name
            )
        )
    files = os.listdir(path_from_script)

    return make_response_altered(
        tiny_htmls.dir_page(
            local_name, str(path_info.obj_absolute_path), files
        ),
        200, CONTENT_TYPE_UTF_8_HTML
    )


def give_file(path_info: PathInfo, local_name: str) -> Response:
    """Find the designated file in the package, then return its content."""
    path_from_script = "./{:s}/{:s}/package{}".format(
        CACHE_FOLDER, local_name, path_info.obj_absolute_path
    )
    # If the file does not exist
    if not os.path.exists(path_from_script):
        raise RequestNotValidError(
            404,
            "Couldn't find the requested file {:s} in {:s}.".format(
                path_from_script, path_info.package_name
            )
        )
    with open(path_from_script, 'rb') as f:
        content = f.read()

    return make_response_altered(
        content,
        200,
        mimetypes.guess_file_type(path_from_script)
    )



def main() -> None:
    report_cache_folder_size(app.logger)
    # `use_reloader` set to `False`
    # in order to avoid the previous line being executed twice.
    app.run(host='0.0.0.0', port=2357, debug=True, use_reloader=False)


if __name__ == '__main__':
    main()
