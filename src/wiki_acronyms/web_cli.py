"""CLI entry point for the local web quiz."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

import yaml

from .gutenberg import fetch_text
from .logger import QuizLogger, config_hash
from .poetry_parser import extract_poem
from .srs import SRSScheduler
from .web_app import create_app


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Start local web quiz for poetry retention.')
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--poem', help='Poem title (for multi-poem configs)')
    p.add_argument('--wrong-prob', type=float, default=0.15)
    p.add_argument('--mode', choices=['words', 'acronym'], default='words')
    p.add_argument('--port', type=int, default=5001)
    p.add_argument('--review-ahead', type=int, default=0, metavar='N',
                   help='include N future-scheduled items after due items (increases total reviews)')
    p.add_argument('--max-interval', type=int, default=365, metavar='DAYS',
                   help='cap FSRS-scheduled intervals at this many days (default 365; 0 = no cap)')
    p.add_argument('--learning-steps', type=int, nargs='+', default=[1, 10, 60, 360], metavar='MIN',
                   help='learning step durations in minutes (default: 1 10 60 360)')
    p.add_argument('--graduated-steps', type=int, nargs='+', default=[1, 2, 3, 4, 5, 6, 7], metavar='DAYS',
                   help='graduated ramp durations in days before FSRS free scheduling (default: 1 2 3 4 5 6 7)')
    p.add_argument('--new-per-day', type=int, default=20, metavar='N',
                   help='max new items introduced per day (default 20)')
    p.add_argument('--relearn-steps', type=int, nargs='+', default=[1, 2, 3], metavar='DAYS',
                   help='relearning step durations in days after a lapse (default: 1 2 3)')
    p.add_argument('--difficulty-forgiveness', type=float, default=1.0, metavar='F',
                   help='scale lapse difficulty increase by (1-F); 1.0=no increase, 0.0=full FSRS (default 1.0)')
    p.add_argument('--stability-forgiveness', type=float, default=1.0, metavar='F',
                   help='scale lapse stability drop by (1-F); 1.0=no drop, 0.0=full FSRS (default 1.0)')
    args = p.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    text = fetch_text(config['gutenberg_id'])
    poem_cfgs = config['poems'] if 'poems' in config else [config]

    if args.poem:
        poem_cfgs = [pc for pc in poem_cfgs if pc.get('poem_title') == args.poem]
        if not poem_cfgs:
            print(f"Poem '{args.poem}' not found.")
            return

    pc = poem_cfgs[0]
    title = pc['poem_title']
    lines = [l for l in extract_poem(text, pc['start_marker'], pc['end_marker']) if l is not None]

    logger = QuizLogger()
    app = create_app(
        lines, title, args.wrong_prob, args.mode,
        logger=logger,
        config_path=str(args.config),
        cfg_hash=config_hash(args.config),
        srs=SRSScheduler(logger, max_interval_days=args.max_interval or None,
                         learning_steps=args.learning_steps, graduated_steps=args.graduated_steps,
                         new_cards_per_day=args.new_per_day, relearn_steps=args.relearn_steps,
                         difficulty_forgiveness=args.difficulty_forgiveness,
                         stability_forgiveness=args.stability_forgiveness),
        review_ahead=args.review_ahead,
    )

    url = f'http://localhost:{args.port}'
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f'Quiz running at {url}  (Ctrl+C to stop)')
    app.run(port=args.port, debug=False)
    logger.close()
