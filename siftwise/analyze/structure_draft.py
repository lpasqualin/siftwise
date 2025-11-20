def _results_to_mapping(results: List[Result], label_to_node: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Convert analyzer Results into rows for Mapping.csv.

    IMPORTANT:
    - We *must* carry over is_residual and action so downstream
      (refine-residuals, execute) see the same decisions the analyzer made.
    """
    rows: List[Dict[str, str]] = []
    for r in results:
        node_id = label_to_node.get(r.label, "n_root")

        rows.append(
            {
                "SourcePath": str(r.path),
                "NodeID": node_id,
                "Label": r.label or "",
                "Confidence": f"{r.confidence:.2f}",
                "Why": r.why,
                # NEW: propagate decisions
                "IsResidual": "True" if getattr(r, "is_residual", False) else "False",
                "Action": getattr(r, "action", "Move") or "Move",
            }
        )
    return rows
