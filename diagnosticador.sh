#!/bin/bash

echo "  Diagnosticador BLUETOOTH"
echo ""

echo "1 Adaptadores Bluetooth detectados:"
hcitool dev
echo ""

echo "2 Estado de hci0:"
hciconfig -a 2>/dev/null || echo "hci0 no disponible"
echo ""

echo "3 Servicio Bluetooth:"
systemctl status bluetooth --no-pager -l 2>/dev/null | head -15
echo ""

echo "4 Procesos usando Bluetooth:"
sudo lsof 2>/dev/null | grep -i bluetooth | head -10
echo ""

echo "5 Estado del WiFi:"
nmcli radio wifi 2>/dev/null || echo "nmcli no disponible"
echo ""
