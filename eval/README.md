# Eval cases

Gold facts live in `cases/*/case.yaml`. Expected rule outcomes in `expected.yaml`.

| Layer | How |
|---|---|
| Rules only | `tests/test_cases.py` builds Facts from `case.yaml` (no LLM) |
| Field extract | `python eval/extract_eval.py` vs case.yaml gold |
| Full scoreboard | `eval/score.py` on a `runs/<label>/` folder |

Do not edit `expected.yaml` just to make a run pass unless the expectation was wrong.
