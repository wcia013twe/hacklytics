from flask import Flask, request

app = Flask(__name__)

@app.route('/ingest', methods=['POST'])
def receive_data():
    data = request.json
    print("\n" + "="*30)
    print(f"🔥 HAZARD LEVEL: {data.get('hazard_level')}")
    print(f"🌡️  TEMP: {data.get('temp_max'):.1f}°C")
    print(f"💨 SMOKE SENSOR: {data.get('smoke_sensor')}")
    print("="*30)
    return {"status": "success"}

if __name__ == '__main__':
    print("🎧 Listening for Jetson data on port 8000...")
    app.run(host='0.0.0.0', port=8000)