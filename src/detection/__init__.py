"""Detection postprocess and consistency helpers for Jetson split experiments."""

__all__ = [
    "DetectionSet",
    "compare_detection_sets",
    "postprocess_raw_output",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .postprocess_v1 import (
        DetectionSet,
        compare_detection_sets,
        postprocess_raw_output,
    )

    values = {
        "DetectionSet": DetectionSet,
        "compare_detection_sets": compare_detection_sets,
        "postprocess_raw_output": postprocess_raw_output,
    }
    return values[name]
