.PHONY: install api ui test evaluate demo

install:
	python -m pip install -r requirements.txt

api:
	uvicorn app.main:app --reload

ui:
	streamlit run ui/streamlit_app.py

test:
	pytest --cov=app --cov-report=term-missing

evaluate:
	python scripts/run_evaluation.py

demo:
	python scripts/demo_scenarios.py

