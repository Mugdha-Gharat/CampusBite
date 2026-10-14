from app import create_app

app = create_app()

if __name__ == "__main__":
    # Debug mode stays disabled by default, including in containers.
    app.run(host="0.0.0.0", port=5000, debug=False)
