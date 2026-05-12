from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import load_settings
from .logging_setup import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local assistant for Russian arbitration claim drafting.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Analyze documents and generate a DOCX claim draft.")
    run_parser.add_argument("documents", nargs="+", type=Path, help="PDF/DOCX files.")
    run_parser.add_argument("--case-name", default=None, help="Human-friendly case name.")

    serve_parser = subparsers.add_parser("serve", help="Run local web interface.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host for local web server.")
    serve_parser.add_argument("--port", default=8000, type=int, help="Port for local web server.")
    serve_parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")

    feedback_parser = subparsers.add_parser("feedback", help="Save lawyer/user feedback for future prompt tuning.")
    feedback_parser.add_argument("case_id", help="Case id from data/cases or data/training.")
    feedback_parser.add_argument("feedback", help="Free-form feedback: what was correct, wrong, missing or changed.")
    feedback_parser.add_argument("--accepted", action="store_true", help="Mark generated claim as accepted.")
    feedback_parser.add_argument("--rejected", action="store_true", help="Mark generated claim as rejected.")

    args = parser.parse_args()
    settings = load_settings()
    configure_logging(settings.log_file)

    if args.command == "run":
        from .pipeline import ClaimPipeline

        missing = [str(path) for path in args.documents if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Input files not found: {missing}")
        output = ClaimPipeline(settings).run(args.documents, args.case_name)
        print(f"Готово: {output}")
    elif args.command == "serve":
        from .web import create_app

        app = create_app(settings)
        app.run(host=args.host, port=args.port, debug=args.debug)
    elif args.command == "feedback":
        from .storage import CaseStorage

        accepted = None
        if args.accepted and args.rejected:
            raise ValueError("Use only one of --accepted or --rejected.")
        if args.accepted:
            accepted = True
        if args.rejected:
            accepted = False
        output = CaseStorage(settings.cases_dir, settings.training_dir).add_feedback(
            args.case_id,
            args.feedback,
            accepted=accepted,
        )
        print(f"Обратная связь сохранена: {output}")
