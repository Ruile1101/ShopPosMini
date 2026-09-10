import os
import sys
import traceback

def log_error(message):
    try:
        if getattr(sys, 'frozen', False):
            folder = os.path.dirname(sys.executable)
        else:
            folder = os.path.dirname(os.path.abspath(__file__))

        log_file = os.path.join(folder, "error_log.txt")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(message)
            f.write("\n")
    except Exception:
        pass


try:
    log_error("Starting ShopPOS...")

    import os
    from app import create_app

    log_error("Imported create_app successfully")

    app = create_app()

    log_error("create_app() completed successfully")

    if __name__ == "__main__":
        log_error("Starting Flask server...")
        app.run(
            debug=False,
            host=os.getenv('FLASK_RUN_HOST', '0.0.0.0'),
            port=int(os.getenv('FLASK_RUN_PORT', '5000')),
            use_reloader=False
        )

except Exception:
    log_error(traceback.format_exc())
    raise