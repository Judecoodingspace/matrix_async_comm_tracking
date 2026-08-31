"""Neutral import surface for passive Work 1 audit metadata primitives."""
try:
    from .mdmt_mia_work1_xml_governance import (
        PassiveAuditSequence,
        Work1AccessAudit,
        make_author_initialization_marker,
    )
except ImportError:  # isolated derivative copy under demo/utils
    from utils.work1_xml_governance import (  # type: ignore[import-not-found]
        PassiveAuditSequence,
        Work1AccessAudit,
        make_author_initialization_marker,
    )

__all__ = ("PassiveAuditSequence", "Work1AccessAudit", "make_author_initialization_marker")
