from app import create_app

app = create_app()

if __name__ == '__main__':
    # threaded=True allows Flask to handle concurrent requests efficiently
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)
