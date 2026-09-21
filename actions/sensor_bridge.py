import wmi
import time
import json
import os
import sys
def grab_real_temp():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    json_path = os.path.join(project_root, 'data', 'temp_bridge.json')
    try:
        w = wmi.WMI(namespace='root/wmi')
    except Exception as e:
        return
    last_temp = 0
    while True:
        try:
            zones = w.MSAcpi_ThermalZoneTemperature()
            valid_temps = []
            for z in zones:
                t = z.CurrentTemperature / 10.0 - 273.15
                if t > 10 and t < 110:
                    valid_temps.append(t)
            if valid_temps:
                temp = max(valid_temps)
                if temp != last_temp:
                    status = '▲' if temp > last_temp else '▼'
                    last_temp = temp
                else:
                    status = '●'
                with open(json_path, 'w') as f:
                    json.dump({'cpu_temp': round(temp, 1)}, f)
                sys.stdout.write(f'\r[>] CPU Core: {temp:.1f}°C {status}   ')
                sys.stdout.flush()
            else:
                break
        except Exception as e:
            time.sleep(5)
        time.sleep(1)

if __name__ == '__main__':
    grab_real_temp()
