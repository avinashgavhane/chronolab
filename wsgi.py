"""
ChronoLab - WSGI Application Entrypoint
=======================================
Exposes the WSGI application object for production servers:
- Gunicorn
- uWSGI
- Waitress
- Docker
- Render / Railway / Heroku
"""

import os
from app import create_app

# Automatically picks environment mode (production or development)
env_mode = os.environ.get("FLASK_ENV", "production")
application = create_app(env_mode)
app = application  # Alias for platforms looking for 'app'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
