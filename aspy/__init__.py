# This is a namespace package
from pkgutil import extend_path  # pragma: no cover
__path__ = extend_path(__path__, __name__)  # pragma: no cover
