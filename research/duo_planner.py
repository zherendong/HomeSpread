"""Compatibility entry point for the validated pure offline draft rules.

The rules graduated to ``ipsm.draft_rules`` for the offline draft interface.
They still have no device, network, file or GUI access and never grant writing.
"""
from ipsm.draft_rules import DraftError, analyze_layout, plan_swap, validate_swap

__all__ = ["DraftError", "analyze_layout", "plan_swap", "validate_swap"]
