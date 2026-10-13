"""One JSON request/response in an isolated process; parent owns lifetime and cancellation."""
import contextlib
import json
import logging
import os
import sys


def main():
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    # Prevent ambient provider defaults and third-party telemetry/config autoload.
    for name in list(os.environ):
        if name.startswith(('TRADINGAGENTS_', 'LANGCHAIN_', 'LANGSMITH_')) or name in ('OPENAI_BASE_URL', 'OPENAI_API_BASE', 'OLLAMA_BASE_URL'):
            os.environ.pop(name, None)
    logging.disable(logging.CRITICAL)
    try:
        raw = sys.stdin.buffer.read(200_001)
        if len(raw) > 200_000:
            raise ValueError('Input limit')
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {'context', 'config'}:
            raise ValueError('Invalid request')
        # Import/model/provider logs must never become protocol output or expose evidence/key details.
        with open(os.devnull, 'w') as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
            from .trading_agent_adapter import run_evidence_agents
            result = run_evidence_agents(payload['context'], payload['config'])
        output = {'result': result}
    except Exception:
        output = {'error': 'Evidence-agent analysis unavailable; no paper action proposed.'}
    sys.stdout.write(json.dumps(output, ensure_ascii=False, allow_nan=False) + '\n')
    sys.stdout.flush()


if __name__ == '__main__':
    main()
