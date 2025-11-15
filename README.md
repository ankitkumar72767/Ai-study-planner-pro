# AI Study Planner Agent — Streamlit (Advanced Capstone)
This is the advanced Streamlit + OpenAI implementation of the Study Planner Agent for the Kaggle Agents Intensive Capstone.

## How to run locally
1. Create venv:
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
2. Install:
   pip install -r requirements.txt
3. Add your OpenAI key in `.streamlit/secrets.toml`:
   ```toml
   OPENAI_API_KEY = "sk-..."
```
4. Run:
   streamlit run app.py

## Files
- `app.py` - Streamlit frontend + OpenAI integration
- `agent/` - backend agent code (planner, memory, observability)
- `requirements.txt` - dependencies
- `.streamlit/secrets.toml.sample` - example for secrets
