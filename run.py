import os
from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

# Startup check
with app.app_context():
    from app.config import Config
    print(f"\n{'='*60}")
    print(f"  SRE Portal Backend Starting")
    print(f"  Environment: {env}")
    print(f"  Grafana URL: {Config.GRAFANA_URL}")
    print(f"  Grafana API Key: {'***' + Config.GRAFANA_API_KEY[-6:] if len(Config.GRAFANA_API_KEY) > 6 else 'NOT SET'}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    # 禁用 reloader 和 debug，避免杀死后台任务线程
    app.run(host="0.0.0.0", port=5000, debug=False)
