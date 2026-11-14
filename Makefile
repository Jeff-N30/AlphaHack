.PHONY: docs test eval health

docs:
	.venv/bin/python tools/generate_fake_docs.py --degrade

test:
	cd backend && ../.venv/bin/pytest -q

eval:
	.venv/bin/python eval/score.py --selftest

health:
	.venv/bin/python -c "from fastapi.testclient import TestClient; import sys; sys.path.insert(0,'backend'); from app.main import app; print(TestClient(app).get('/health').json())"
