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
from .web_app import create_app


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Start local web quiz for poetry retention.')
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--poem', help='Poem title (for multi-poem configs)')
    p.add_argument('--wrong-prob', type=float, default=0.15)
    p.add_argument('--mode', choices=['words', 'acronym'], default='words')
    p.add_argument('--port', type=int, default=5001)
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
    )

    url = f'http://localhost:{args.port}'
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f'Quiz running at {url}  (Ctrl+C to stop)')
    app.run(port=args.port, debug=False)
    logger.close()
