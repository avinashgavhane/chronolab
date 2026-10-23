"""
ChronoLab - Entrypoint Server
=============================
Run with:
    python run.py
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 60)
    print("  ChronoLab - Longitudinal Diagnostic Intelligence Platform")
    print("  Server running at: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
