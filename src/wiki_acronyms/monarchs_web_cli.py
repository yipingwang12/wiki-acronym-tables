"""CLI entry point for the monarch transition-string web quiz."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

import yaml

from .logger import QuizLogger, config_hash
from .monarchs import fetch_monarchs, make_monarch_chunks
from .srs import SRSScheduler
from .web_app import create_app


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Start local web quiz for monarch transition strings.')
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--wrong-prob', type=float, default=0.2)
    p.add_argument('--port', type=int, default=5001)
    args = p.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    monarchs = fetch_monarchs(config['positions'])
    chunks = make_monarch_chunks(
        monarchs,
        config.get('chunk_years', 100),
        config.get('chunk_start_year'),
    )

    items = [c.transition_string for c in chunks]
    item_labels = [f"{c.start_year}\u2013{c.end_year}" for c in chunks]
    title = config.get('subject', 'Monarchs')

    logger = QuizLogger()
    app = create_app(
        items, title, args.wrong_prob, mode='digits', item_labels=item_labels,
        logger=logger,
        config_path=str(args.config),
        cfg_hash=config_hash(args.config),
        srs=SRSScheduler(logger),
    )

    url = f'http://localhost:{args.port}'
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f'Quiz running at {url}  (Ctrl+C to stop)')
    app.run(port=args.port, debug=False)
    logger.close()
