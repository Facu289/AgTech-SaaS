#!/bin/sh
# Copia los backups de AgroApp a la nube con rclone. Lo corre cron todos los días en el NAS.
#
# La app ya hace un backup por día en datos/backups (ver app/nucleo/backup.py). Este script
# solo SUBE esos archivos a la nube: así, si el NAS se rompe o se lo roban, la base no se pierde.
#
# Usa "rclone copy" (no "sync"): lo que se borra en el NAS NO se borra en la nube.
# rclone solo sube los archivos nuevos o cambiados (no vuelve a subir todo cada día).
#
# Guía completa (instalar rclone, configurar la nube, cron y cómo restaurar): docs/NAS_BACKUP_NUBE.md
#
# Uso:   sudo sh /srv/agroapp/scripts/backup_nube.sh
# Se puede cambiar con variables:  CARPETA=... REMOTO=... sudo -E sh scripts/backup_nube.sh

set -eu

CARPETA="${CARPETA:-/srv/agroapp/datos/backups}"
REMOTO="${REMOTO:-agroapp-nube:AgroApp/backups}"
REGISTRO="${REGISTRO:-/var/log/agroapp_backup_nube.log}"

echo "$(date '+%Y-%m-%d %H:%M:%S') Subiendo $CARPETA a $REMOTO" >> "$REGISTRO"

if ! ls "$CARPETA"/agroapp_*.db > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: no hay backups en $CARPETA" >> "$REGISTRO"
    exit 1
fi

# --include: solo los backups de la base (agroapp_AAAA-MM-DD_HHMMSS.db).
rclone copy "$CARPETA" "$REMOTO" --include "agroapp_*.db" --log-file "$REGISTRO" --log-level INFO

echo "$(date '+%Y-%m-%d %H:%M:%S') Listo" >> "$REGISTRO"
