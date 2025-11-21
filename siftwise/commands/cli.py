import argparse


def main():
    p = argparse.ArgumentParser(prog="sift", description="Siftwise CLI - Intelligent File Organization")
    sub = p.add_subparsers(dest="cmd", required=True)

    # DRAFT
    p_draft = sub.add_parser("draft-structure", help="Propose a folder tree + mapping with residual detection")
    p_draft.add_argument("--root", required=True, help="Incoming root to scan")
    p_draft.add_argument("--dest-root", required=True, help="Destination root (artifacts go to <dest-root>/.sift)")
    p_draft.add_argument("--outdir", help="(ignored) use --dest-root; artifacts go to <dest-root>/.sift")
    p_draft.add_argument("--use-rules", action="store_true", help="Apply custom rules from rules.yaml")
    p_draft.add_argument("--explain", action="store_true", help="Include detailed explanations")

    # REVIEW
    p_review = sub.add_parser("review-structure", help="Show/edit the tree plan")
    p_review.add_argument("--dest-root", required=True, help="Destination root where <dest-root>/.sift lives")
    p_review.add_argument("--open-yaml", action="store_true", help="Open YAML editor")

    # EXECUTE
    p_exec = sub.add_parser("execute", help="Execute moves from approved plan")
    p_exec.add_argument("--dest-root", required=True, help="Destination root where <dest-root>/.sift lives")
    p_exec.add_argument("--plan", help="Override plan path (defaults to <dest-root>/.sift/TreePlan.json)")
    p_exec.add_argument("--mapping", help="Override mapping path (defaults to <dest-root>/.sift/Mapping.csv)")
    p_exec.add_argument("--what-if", action="store_true", help="Dry-run only")

    # REFINE-RESIDUALS (Phase 2)
    p_refine = sub.add_parser(
        "refine-residuals",
        help="Re-analyze flagged residual files to improve classification (files stay in place until confident)"
    )
    p_refine.add_argument(
        "--dest-root",
        required=True,
        help="Destination root where <dest-root>/.sift lives"
    )
    p_refine.add_argument(
        "--iteration",
        type=int,
        default=2,
        help="Refinement iteration number (for tracking)"
    )
    # ✅ NEW: optional root for preserve-structure logic / smarter refinement
    p_refine.add_argument(
        "--root",
        help="Incoming root used for preserve-structure logic during refinement (optional)"
    )

    # Future commands placeholder
    # SEARCH (Phase 3)
    p_search = sub.add_parser(
        "search",
        help="Search for file patterns and optionally create rules (Coming Soon)"
    )
    p_search.add_argument("--pattern", required=True, help="Glob or regex pattern to search")
    p_search.add_argument("--dest-root", required=True, help="Destination root")
    p_search.add_argument("--residuals-only", action="store_true",
                          help="Search only in residual files")
    p_search.add_argument("--make-rule", help="Create a rule assigning matches to specified folder")

    # DISCOVER-ENTITIES (Phase 4)
    p_discover = sub.add_parser(
        "discover-entities",
        help="Automatically discover entities (clients, projects, etc.) (Coming Soon)"
    )
    p_discover.add_argument("--dest-root", required=True, help="Destination root")
    p_discover.add_argument("--min-frequency", type=int, default=3,
                            help="Minimum frequency for entity detection")

    args = p.parse_args()

    # Route to appropriate module
    if args.cmd == "draft-structure":
        from .draft_structure import run as draft_run
        draft_run(args)
    elif args.cmd == "review-structure":
        from .review_structure import run as review_run
        review_run(args)
    elif args.cmd == "execute":
        from .execute import run as exec_run
        exec_run(args)
    elif args.cmd == "refine-residuals":
        from .refine_residuals import run as refine_run
        refine_run(args)
    elif args.cmd == "search":
        print("🔨 Search functionality coming in Phase 3!")
        print("This will allow pattern-based search and rule creation.")
    elif args.cmd == "discover-entities":
        print("🔨 Entity discovery coming in Phase 4!")
        print("This will automatically detect recurring themes, clients, and projects.")


if __name__ == "__main__":
    main()
