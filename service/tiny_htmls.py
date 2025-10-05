# 2025-09-29  tiny_htmls.py

from functools import cmp_to_key

from tiny_utils.network import PathInfo
from tiny_utils.node_ecosys import ValidRegistryJson, semver_cmp
from tiny_utils.general import report_counted_things, reverse_cmp


_ELEMENT_A_TEMPLATE = '''
<a href="{href:s}">{text:s}</a>
'''


def _element_a(href: str, text: str) -> str:
    return _ELEMENT_A_TEMPLATE.format(href=href, text=text)


_UNORDERED_LIST_TEMPLATE = '''
<ul>{li_s:s}</ul>
{total:s}<br/>
'''


def _unordered_list(items: list[str]) -> str:
    """
    List HTML strings in an unordered list `<ul>`...`</ul>`.
    `<li>` and `</li>` are added automatically.
    Report how many items there are.
    """
    if not items:
        return '(Empty list)'
    return _UNORDERED_LIST_TEMPLATE.format(
        li_s='\n'.join(f"<li>{item}</li>" for item in items),
        total=report_counted_things(len(items), 'item')
    )


_TABLE_WITH_HEAD_TEMPLATE = '''
<table>
  <thead><tr>{th_s:s}</tr></thead>
  <tbody>{tr_s:s}</tbody>
</table>
{total:s}<br/>
'''


def _table_with_head(titles: list[str], rows: list[list[str]]) -> str:
    """
    List HTML strings in a table with a head row.
    Elements like `<th>`, `</th>`, `<tr>`, `</tr>`, `<td>`, `</td>`
    are added automatically.
    """
    if not rows:
        return '(Empty table)'

    return _TABLE_WITH_HEAD_TEMPLATE.format(
        th_s='\n'.join(
            f"<th scope=\"col\">{title}</th>"
            for title in titles
        ),
        tr_s='\n'.join(
            f"<tr>{'\n'.join(f"<td>{item}</td>" for item in row)}</tr>"
            for row in rows
        ),
        total=report_counted_things(len(rows), 'row')
    )


def _vers_tags_table(
        versions: list[str],
        tag_to_ver: dict[str, str],
        path_info: PathInfo
        ) -> str:
    """
    A more specific version of `_table_with_head`.
    List all of the `versions`.
    If a version is tagged, show the tag.
    """
    # Deduplicate versions.
    versions = list(set(versions))
    # Sort versions by rules of semantic versioning.
    versions.sort(key=cmp_to_key(reverse_cmp(semver_cmp)))
    # Make a reversed mapping, from version to tags.
    # Note: There might be multiple tags for the same version.
    ver_to_tags = {v: [] for v in tag_to_ver.values()}
    for t, v in tag_to_ver.items():
        ver_to_tags[v].append(t)
    return _table_with_head(
        ['version', 'dist-tag'],
        [
            [
                _element_a(
                    "/{:s}@{:s}{}".format(
                        path_info.package_name, ver,
                        path_info.obj_absolute_path or ''
                    ),
                    ver
                ),
                '; '.join(tag for tag in ver_to_tags.get(ver, []))
            ]
            for ver in versions
        ]
    )


_VERSIONS_TABLES_HIGHLIGHTING_TAGS_TEMPLATE = '''
{highlight_title:s}<br/>
{versions_with_dist_tags:s}
<hr>
full list:<br/>
{full_list:s}
'''


def _versions_tables_highlighting_tags(
        versions: list[str],
        tag_to_ver: dict[str, str],
        path_info: PathInfo
        ) -> str:
    """
    Show the tagged versions in a table, and a full list of all versions.
    """
    versions_having_dist_tags = set(tag_to_ver.values())
    if all(ver in versions_having_dist_tags for ver in versions):
        highlight_title = "(all version(s) have dist-tag(s))"
        versions_with_dist_tags = ""
    else:
        highlight_title = "version(s) with dist-tag(s):"
        versions_with_dist_tags = _vers_tags_table(
            [ver for ver in versions if ver in tag_to_ver.values()],
            tag_to_ver,
            path_info
        )
    return _VERSIONS_TABLES_HIGHLIGHTING_TAGS_TEMPLATE.format(
        highlight_title=highlight_title,
        versions_with_dist_tags=versions_with_dist_tags,
        full_list=_vers_tags_table(
            versions,
            tag_to_ver,
            path_info
        )
    )


_DIR_PAGE_TEMPLATE = '''
<!DOCTYPE HTML>
<html>
<head>
<meta charset="utf-8">
<title>{title:s}</title>
</head>
<body>
<h1>{title:s}</h1>
<hr>
{links:s}
<hr>
</body>
</html>
'''


def dir_page(local_name: str, path: str, files: list[str]) -> str:
    """Show a directory's contents."""
    title = local_name + ' :: ' + path
    return _DIR_PAGE_TEMPLATE.format(
        title=title,
        links=_unordered_list(
            [_element_a(file, file) for file in files]
        )
    )


_VERSIONS_PAGE_TEMPLATE = '''
<!DOCTYPE HTML>
<html>
<head>
<meta charset="utf-8">
<title>All valid version(s) for package "{package:s}"
with requirement(s) "{requirement:s}"</title>
</head>
<body>
<h1>All valid version(s) for package "{package:s}"
with requirement(s) "{requirement:s}"</h1>
<hr>
{links:s}
<hr>
</body>
</html>
'''


def versions_page(
        versions: list[str],
        registry_json: ValidRegistryJson,
        path_info: PathInfo
        ) -> str:
    """
    List versions.
    Used when a set (may be only 1) of version(s) is found to be valid.
    """
    return _VERSIONS_PAGE_TEMPLATE.format(
        package=path_info.package_name,
        requirement=path_info.version_spec_str,
        links=_versions_tables_highlighting_tags(
            versions,
            registry_json['dist-tags'],
            path_info
        )
    )


_ALL_VERSIONS_PAGE_TEMPLATE = '''
<!DOCTYPE HTML>
<html>
<head>
<meta charset="utf-8">
<title>No version for package "{package:s}"
with requirement(s) "{requirement:s}" is found</title>
</head>
<body>
<h1>No version for package "{package:s}"
with requirement(s) "{requirement:s}" is found.</h1>
Showing all versions for package "{package:s}".
<hr>
{vers:s}
<hr>
</body>
</html>
'''


def all_versions_page(
        registry_json: ValidRegistryJson, path_info: PathInfo
        ) -> str:
    """
    List all versions of the package.
    Used when no version is found to be valid.
    """
    return _ALL_VERSIONS_PAGE_TEMPLATE.format(
        package=path_info.package_name,
        requirement=path_info.version_spec_str,
        vers=_versions_tables_highlighting_tags(
            [ver for ver in registry_json['versions'].keys()],
            registry_json['dist-tags'],
            path_info
        )
    )


_HOME_PAGE_TEMPLATE = '''
<!DOCTYPE HTML>
<html>
<head>
<meta charset="utf-8">
<title>BYR Archive</title>
</head>
<body>
<h1>BYR Archive</h1>
This service is similar to jsDelivr. It extracts files from the npm registry website.
<hr>
<h2>Usage</h2>

Use package <code>react</code> as example:

<ul>
    <li><a href="/react@all"><code>/react@all</code></a> - Show all versions.</li>
    <li><a href="/react@dist-tags"><code>/react@dist-tags</code></a> - Show all distribution tags.</li>
    <li><a href="/react@>=5.0.0 <18.0.0 || 0.14.3"><code>/react@>=5.0.0 <18.0.0 || 0.14.3</code></a> - Show all versions that satisfy the specified version range.</li>
    <li><a href="/react@19.2.0"><code>/react@19.2.0</code></a> - Show content of the specified version.</li>
    <li><a href="/react@next"><code>/react@next</code></a> - Show content corresponding to the specified distribution tag (the tag is "<code>next</code>" here).</li>
    <li><a href="/react"><code>/react</code></a> - Show content corresponding to the distribution tag "<code>latest</code>".</li>
</ul>

</body>
</html>
'''


def home_page() -> str:
    return _HOME_PAGE_TEMPLATE
