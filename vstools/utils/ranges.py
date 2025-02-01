from __future__ import annotations

from typing import Any, Protocol, Sequence, TypeVar, Union, overload

import vapoursynth as vs

from stgpytools import CustomValueError, flatten, interleave_arr, ranges_product

from ..functions import check_ref_clip
from ..types import FrameRangeN, FrameRangesN

__all__ = [
    'replace_ranges',

    'remap_frames',

    'replace_every',

    'ranges_product',

    'interleave_arr',
]


_gc_func_gigacope = []


_VideoFrameT_contra = TypeVar("_VideoFrameT_contra", vs.VideoFrame, list[vs.VideoFrame], contravariant=True)


class RangesCallBack(Protocol):
    def __call__(self, n: int) -> bool:
        ...

class RangesCallBackF(Protocol[_VideoFrameT_contra]):
    def __call__(self, f: _VideoFrameT_contra) -> bool:
        ...


class RangesCallBackNF(Protocol[_VideoFrameT_contra]):
    def __call__(self, n: int, f: _VideoFrameT_contra) -> bool:
        ...


RangesCallBackT = Union[
    RangesCallBack,
    RangesCallBackF[vs.VideoFrame],
    RangesCallBackNF[vs.VideoFrame],
    RangesCallBackF[list[vs.VideoFrame]],
    RangesCallBackNF[list[vs.VideoFrame]],
]


@overload
def replace_ranges(
    clip_a: vs.VideoNode, clip_b: vs.VideoNode, ranges: FrameRangeN | FrameRangesN,
    /, *,
    exclusive: bool = False, mismatch: bool = False,
) -> vs.VideoNode:
    """
    Replaces frames in a clip with pre-calculated indices.
    Frame ranges are inclusive. This behaviour can be changed by setting `exclusive=True`.

    Examples with clips ``black`` and ``white`` of equal length:
        * ``replace_ranges(black, white, [(0, 1)])``: replace frames 0 and 1 with ``white``
        * ``replace_ranges(black, white, [(None, None)])``: replace the entire clip with ``white``
        * ``replace_ranges(black, white, [(0, None)])``: same as previous
        * ``replace_ranges(black, white, [(200, None)])``: replace 200 until the end with ``white``
        * ``replace_ranges(black, white, [(200, -1)])``: replace 200 until the end with ``white``,
                                                         leaving 1 frame of ``black``

    Optional Dependencies:
        * `vs-zip <https://github.com/dnjulek/vapoursynth-zip>`_ (highly recommended!)

    :param clip_a:      Original clip.
    :param clip_b:      Replacement clip.
    :param ranges:      Ranges to replace clip_a (original clip) with clip_b (replacement clip).
                        Integer values in the list indicate single frames,
                        Tuple values indicate inclusive ranges.
                        Negative integer values will be wrapped around based on clip_b's length.
                        None values are context dependent:
                            * None provided as sole value to ranges: no-op
                            * Single None value in list: Last frame in clip_b
                            * None as first value of tuple: 0
                            * None as second value of tuple: Last frame in clip_b
    :param exclusive:   Use exclusive ranges (Default: False).
    :param mismatch:    Accept format or resolution mismatch between clips.

    :return:            Clip with ranges from clip_a replaced with clip_b.
    """


@overload
def replace_ranges(
    clip_a: vs.VideoNode, clip_b: vs.VideoNode, ranges: RangesCallBack,
    /, *,
    mismatch: bool = False,
) -> vs.VideoNode:
    """
    Replaces frames in a clip on-the-fly with a callback.

    :param clip_a:      Original clip.
    :param clip_b:      Replacement clip.
    :param ranges:      Callbacks must return true to replace a with b.
    :param mismatch:    Accept format or resolution mismatch between clips.

    :return:            Clip with ranges from clip_a replaced with clip_b.
    """


@overload
def replace_ranges(
    clip_a: vs.VideoNode, clip_b: vs.VideoNode,
    ranges: RangesCallBackF[vs.VideoFrame] | RangesCallBackNF[vs.VideoFrame],
    /, *,
    mismatch: bool = False,
    prop_src: vs.VideoNode
) -> vs.VideoNode:
    """
    Replaces frames in a clip on-the-fly with a callback.

    :param clip_a:      Original clip.
    :param clip_b:      Replacement clip.
    :param ranges:      Callbacks must return true to replace a with b.
    :param mismatch:    Accept format or resolution mismatch between clips.
    :param prop_src:    Source clip to use for frame properties in the callback (parameter "f").

    :return:            Clip with ranges from clip_a replaced with clip_b.
    """


@overload
def replace_ranges(
    clip_a: vs.VideoNode, clip_b: vs.VideoNode,
    ranges: RangesCallBackF[list[vs.VideoFrame]] | RangesCallBackNF[list[vs.VideoFrame]],
    /, *,
    mismatch: bool = False,
    prop_src: list[vs.VideoNode]
) -> vs.VideoNode:
    """
    Replaces frames in a clip on-the-fly with a callback.

    :param clip_a:      Original clip.
    :param clip_b:      Replacement clip.
    :param ranges:      Callbacks must return true to replace a with b.
    :param mismatch:    Accept format or resolution mismatch between clips.
    :param prop_src:    Source clip(s) to use for frame properties in the callback (parameter "f").

    :return:            Clip with ranges from clip_a replaced with clip_b.
    """


@overload
def replace_ranges(
    clip_a: vs.VideoNode, *clip_b: tuple[vs.VideoNode, FrameRangeN | FrameRangesN | RangesCallBack],
    exclusive: bool = False, mismatch: bool = False
) -> vs.VideoNode:
    """
    Replaces frames in a clip with pre-calculated indices or on-the-fly with a callback.
    Frame ranges are inclusive. This behaviour can be changed by setting `exclusive=True`.

    :param clip_a:      Original clip.
    :param *clip_b:     Tuple of replacements clips and frame ranges/callbacks
    :param ranges:      Callbacks must return true to replace a with b.
    :param mismatch:    Accept format or resolution mismatch between clips.

    :return:            Clip with ranges from clip_a replaced with clip_b.
    """


def replace_ranges(
    clip_a: vs.VideoNode, *args: Any,
    exclusive: bool = False, mismatch: bool = False,
    prop_src: vs.VideoNode | list[vs.VideoNode] | None = None
) -> vs.VideoNode:
    if len(args) == 0:
        return clip_a

    if not isinstance(clip_b := args[0], vs.VideoNode):
        rclips: tuple[tuple[vs.VideoNode, FrameRangeN | FrameRangesN | RangesCallBack], ...] = args

        for c, r in rclips:
            if callable(r):
                clip_a = replace_ranges(clip_a, c, r, mismatch=mismatch)
            else:
                clip_a = replace_ranges(clip_a, c, r, exclusive=exclusive, mismatch=mismatch)

        return clip_a

    from ..functions import invert_ranges, normalize_ranges

    ranges: FrameRangeN | FrameRangesN | RangesCallBackT | None = args[1]

    if ranges != 0 and not ranges or clip_a is clip_b:
        return clip_a

    if not mismatch:
        check_ref_clip(clip_a, clip_b)

    if callable(ranges):
        from inspect import Signature

        signature = Signature.from_callable(ranges, eval_str=True)

        params = set(signature.parameters.keys())

        base_clip = clip_a.std.BlankClip(
            keep=True, varformat=(clip_a.format != clip_b.format),
            varsize=(clip_a.width, clip_a.height) != (clip_b.width, clip_b.height)
        )

        callback = ranges

        if 'f' in params and not prop_src:
            raise CustomValueError(
                'To use frame properties in the callback (parameter "f"), '
                'you must specify one or more source clips via `prop_src`!',
                replace_ranges
            )

        if 'f' in params and 'n' in params:
            def _func(n: int, f: vs.VideoFrame) -> vs.VideoNode:
                return clip_b if callback(n, f) else clip_a  # type: ignore
        elif 'f' in params:
            def _func(n: int, f: vs.VideoFrame) -> vs.VideoNode:
                return clip_b if callback(f) else clip_a  # type: ignore
        elif 'n' in params:
            def _func(n: int) -> vs.VideoNode:  # type: ignore
                return clip_b if callback(n) else clip_a  # type: ignore
        else:
            raise CustomValueError('Callback must have signature ((n, f) | (n) | (f)) -> bool!', func=replace_ranges)

        _func.__callback = callback  # type: ignore
        _gc_func_gigacope.append(_func)

        return base_clip.std.FrameEval(_func, prop_src if 'f' in params else None, [clip_a, clip_b])

    shift = 1 - exclusive
    b_ranges = normalize_ranges(clip_b, ranges)

    if hasattr(vs.core, 'vszip'):
        return vs.core.vszip.RFS(
            clip_a, clip_b,
            [y for (s, e) in b_ranges
             for y in range(
                 s, e + (not exclusive if s != e else 1) + (1 if e == clip_b.num_frames - 1 and exclusive else 0)
             )
            ],
            mismatch=mismatch
        )

    a_ranges = invert_ranges(clip_a, clip_b, b_ranges)

    a_trims = [clip_a[max(0, start - exclusive):end + shift + exclusive] for start, end in a_ranges]
    b_trims = [clip_b[start:end + shift] for start, end in b_ranges]

    if a_ranges:
        main, other = (a_trims, b_trims) if (a_ranges[0][0] == 0) else (b_trims, a_trims)
    else:
        main, other = (b_trims, a_trims) if (b_ranges[0][0] == 0) else (a_trims, b_trims)

    return vs.core.std.Splice(list(interleave_arr(main, other, 1)), mismatch)


def remap_frames(clip: vs.VideoNode, ranges: Sequence[int | tuple[int, int]]) -> vs.VideoNode:
    frame_map = list(flatten(  # type: ignore
        f if isinstance(f, int) else range(f[0], f[1] + 1) for f in ranges
    ))

    base = clip.std.BlankClip(length=len(frame_map))

    return base.std.FrameEval(lambda n: clip[frame_map[n]], None, clip)


def replace_every(
    clipa: vs.VideoNode, clipb: vs.VideoNode, cycle: int, offsets: Sequence[int], modify_duration: bool = True
) -> vs.VideoNode:
    offsets_a = [x * 2 for x in range(cycle) if x not in offsets]
    offsets_b = [x * 2 + 1 for x in offsets]
    offsets = sorted(offsets_a + offsets_b)

    interleaved = vs.core.std.Interleave([clipa, clipb])

    return interleaved.std.SelectEvery(cycle * 2, offsets, modify_duration)
