import inspect

from stgpytools import SPath

__all__: list[str] = [
    'get_calling_package'
]


def get_calling_package(depth: int = 2) -> str:
    """
    Get the name of the package from which this function is called.

    If the name is "__main__", use the caller's filename instead.

    :param depth:       The number of frames to go back in the call stack. Default is 2.

    :return:            The name of the calling package or file.
    """

    stack = inspect.stack()

    if len(stack) <= depth:
        return 'unknown'

    frame_info = stack[depth]
    module = inspect.getmodule(frame_info.frame)

    if not module:
        return 'unknown'

    if module.__name__ == '__main__':
        return SPath(frame_info.filename).name

    return module.__name__.split('.')[0]
