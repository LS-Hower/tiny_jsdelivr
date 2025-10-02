# 2025-10-01  tiny_utils/network.py

from dataclasses import dataclass
from flask import make_response, Response
from http.client import responses
from typing import Optional

from tiny_utils.general import PurePosixPathThatMightBeDir


class RequestNotValidError(ValueError):
    """
    Errors that should be corrected by users.
    Other exceptions are considered internal server errors, which should be
    fixed by developer.
    """
    def __init__(self, status_code: int, message: str):
        if not (400 <= status_code < 500):
            raise ValueError(
                f"status_code must be in [400, 500), but got {status_code}"
            )
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reason = responses[status_code]

    def __str__(self) -> str:
        return "{:d} {:s}: {:s}".format(
            self.status_code, self.reason, self.message
        )


def make_response_altered(
        content: str | bytes,
        status_code: int,
        altered_mime_type: Optional[str] | tuple[Optional[str], Optional[str]]
        ) -> Response:
    """
    Make a flask.Response object.
    Basically same as flask.make_response, but with altered mime type.
    Type of `altered_mime_type` is compatible with return value of
    `mimetypes.guess_type()` and `mimetypes.guess_file_type()`.
    """
    resp = make_response(content, status_code)
    if altered_mime_type is None:
        pass
    elif isinstance(altered_mime_type, str):
        resp.headers['Content-Type'] = altered_mime_type
    elif isinstance(altered_mime_type, tuple):
        altered_content_type, altered_content_encoding = altered_mime_type
        resp.headers['Content-Type'] = altered_content_type
        resp.headers['Content-Encoding'] = altered_content_encoding
    else:
        raise TypeError(f"altered_mime_type must be str or tuple[str, str], "
                        f"but got {type(altered_mime_type)}")
    return resp


@dataclass
class PathInfo(object):
    package_name:      str
    version_spec_str:  str
    obj_absolute_path: Optional[PurePosixPathThatMightBeDir]

    @staticmethod
    def make(path: str) -> 'PathInfo':
        """
        example:
        '/lodash@>=1.0.0/lib/' -> (
            package_name:      'lodash',
            version_spec_str:  '>=1.0.0',
            absolute_path:     PurePosixPath('/lib') with .is_dir() = True
        )
        """
        assert path.startswith('/')

        # Find the path of directory or file.
        slash_ind = path.find('/', 1)
        if slash_ind == -1:
            obj_absolute_path = None
            slash_ind = None
        else:
            obj_absolute_path = PurePosixPathThatMightBeDir(path[slash_ind:])
            assert obj_absolute_path.is_absolute()

        # Find the package name and version specification part.
        # If there is no version specification part, use `'latest'`.
        head = path[1:slash_ind]
        match head.count('@'):
            case 0:
                # There is only package name. No version specification.
                package_name, version_spec_str = head, 'latest'
                if not package_name:
                    raise RequestNotValidError(
                        400, f"package_name is empty, path: '{path}'"
                    )
            case 1:
                # There is a version specification.
                package_name, version_spec_str = head.split('@')
                if not package_name:
                    raise RequestNotValidError(
                        400, f"package_name is empty, path: '{path}'"
                    )
                if not version_spec_str:
                    raise RequestNotValidError(
                        400, f"version_spec_str is empty, path: '{path}'"
                    )
            case _:
                # more than one `'@'`s.
                raise RequestNotValidError(
                    400,
                    f"too many '@'s in name and version part, path: '{path}'"
                )

        return PathInfo(package_name, version_spec_str, obj_absolute_path)
