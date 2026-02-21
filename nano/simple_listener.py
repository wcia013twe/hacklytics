from flask import Flask, request

app = Flask(__name__)

@app.route('/ingest', methods=['POST'])
def receive_data():
    data = request.json
    print("\n" + "="*50)
    print(f"🔥 HAZARD LEVEL: {data.get('hazard_level')}")
    print(f"🌡️  TEMP: {data.get('temp_max'):.1f}°C")
    print(f"💨 SMOKE SENSOR: {data.get('smoke_sensor')}")

    # Display spatial heuristics (NEW)
    scores = data.get('scores', {})
    if scores:
        print(f"\n📊 SPATIAL HEURISTICS:")
        print(f"   Proximity:    {scores.get('proximity', 0):.3f} {'⚠️  CRITICAL' if scores.get('proximity', 0) > 0.7 else ''}")
        print(f"   Obstruction:  {scores.get('obstruction', 0):.3f} {'🚫 BLOCKED' if scores.get('obstruction', 0) > 0.3 else '✅ CLEAR'}")
        print(f"   Dominance:    {scores.get('dominance', 0):.3f} {'🔥 MAJOR' if scores.get('dominance', 0) > 0.3 else ''}")

    # Display visual narrative (NEW)
    narrative = data.get('visual_narrative', '')
    if narrative:
        print(f"\n📝 SCENE NARRATIVE:")
        print(f"   {narrative}")

    print("="*50)
    return {"status": "success"}

if __name__ == '__main__':
    print("🎧 Listening for Jetson data on port 8000...")
    app.run(host='0.0.0.0', port=8000)