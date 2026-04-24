"""
app.py — Streamlit Cloud entry point.
Delegates to streamlit_app.py (new multi-page architecture).
"""
# Re-execute streamlit_app.py so Streamlit Cloud picks up the new UI.
import runpy, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
runpy.run_path(
    str(pathlib.Path(__file__).parent / "streamlit_app.py"),
    run_name="__main__",
)
