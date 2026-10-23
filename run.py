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
    print("  Local PC:      http://127.0.0.1:5000")
    print("  Phone / Wi-Fi: http://0.0.0.0:5000")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)
