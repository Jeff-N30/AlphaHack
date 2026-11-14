.PHONY: docs docs-clean seed-cases test eval health api demo-seed

docs:
	.venv/bin/python tools/generate_fake_docs.py

docs-degrade:
	.venv/bin/python tools/generate_fake_docs.py --degrade

seed-cases:
	.venv/bin/python tools/seed_eval_cases.py

test:
	cd backend && ../.venv/bin/pytest -q

eval:
	.venv/bin/python eval/score.py --selftest

# Prompt+eval loop for Llama extract (no fine-tune). Needs make docs; live = DEMO_OFFLINE=0
extract-eval:
	.venv/bin/python eval/extract_eval.py

extract-eval-live:
	DEMO_OFFLINE=0 EXTRACT_PROVIDER=ollama EXTRACT_MODEL=llama3.2 .venv/bin/python eval/extract_eval.py --cases case01_complete

health:
	.venv/bin/python -c "from fastapi.testclient import TestClient; import sys; sys.path.insert(0,'backend'); from app.main import app; print(TestClient(app).get('/health').json())"

api:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

demo-seed:
	curl -s -X POST http://127.0.0.1:8000/demo/seed-case/case01_complete | .venv/bin/python -m json.tool | head -80

demo:
	@echo "Open http://127.0.0.1:8000/demo  then click Run agent"
	@echo "Or: .venv/bin/python tools/demo_run.py case05_wrong_dates"
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
