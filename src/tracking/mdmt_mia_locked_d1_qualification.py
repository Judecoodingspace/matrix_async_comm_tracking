"""Executable mechanical qualification dispatch; never launches formal qualification by default."""
from __future__ import annotations
from typing import Callable
from tracking.mdmt_mia_locked_d1_package import LockedD1Error

CHECK_IDS = ("authority_binding","frozen_runtime_fingerprints","rendering","package_layout","manifest_digest_graph","cache_key_and_miss","reference_role","y00_parity","attempt_immutability","type_i","type_ii","mixed_authority","validity_blindness","analyzer_guard","minimal_trace","debug_suppression","dedup_path","storage_manifest","storage_threshold","disk_full")

def dry_list(): return [{"CHECK_ID": x, "STATUS": "PLANNED", "EVIDENCE": "synthetic/unit primitive", "FAILURE_CLASS": None} for x in CHECK_IDS]
def run_checks(dispatch: dict[str, Callable[[], object]], *, authorized: bool=False):
    if not authorized: raise LockedD1Error("FORMAL_QUALIFICATION_REQUIRES_SEPARATE_AUTHORIZATION")
    rows=[]
    for check in CHECK_IDS:
        try: rows.append({"CHECK_ID":check,"STATUS":"PASS","EVIDENCE":dispatch[check](),"FAILURE_CLASS":None})
        except Exception as exc: rows.append({"CHECK_ID":check,"STATUS":"FAIL","EVIDENCE":str(exc),"FAILURE_CLASS":"MECHANICS"})
    return {"overall":"QUALIFICATION_MECHANICS_PASS" if all(x["STATUS"]=="PASS" for x in rows) else "QUALIFICATION_MECHANICS_FAIL","checks":rows}
