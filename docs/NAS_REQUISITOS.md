# Requisitos del NAS para AgroApp

> Documento para el chat donde se arma el NAS. Cuando esté todo listo, se vuelve al chat de
> AgroApp con la sección "Qué traer de vuelta" completa.

## Contexto

AgroApp es una app propia: backend en **Python (FastAPI)**, base **SQLite** (un solo archivo),
un **bot de Telegram** (y pronto de WhatsApp) y una web. Hoy corre en una PC con Windows.
Queremos que el NAS:

1. guarde la base de datos y sus backups de forma segura, y
2. tenga la app funcionando **24/7** (backend + bot), con reinicio automático.

La app es liviana: ~100 MB de RAM y casi nada de CPU. El NAS se elige por lo que necesite
el resto de los usos, no por AgroApp.

## Lo que necesita el NAS

### 1. Sistema y software
- **Linux de 64 bits** (Debian 12/13, Ubuntu Server 24.04, OpenMediaVault 7, TrueNAS SCALE,
  Unraid o Proxmox con una VM/LXC Linux: cualquiera sirve).
- **Docker Engine + Docker Compose v2** (`docker compose ...`). La app se va a instalar
  como contenedores: no hace falta instalar Python en el NAS.
- **Git** (para bajar el código).
- **Zona horaria `America/Argentina/Buenos_Aires` y hora sincronizada (NTP).**
  Importa: los backups, vencimientos y partos se calculan por fecha.

### 2. Discos y carpetas
- Una carpeta para la app, por ejemplo **`/srv/agroapp`**, en un disco **local** del NAS,
  idealmente en **almacenamiento con redundancia** (espejo/RAID1 o similar).
- ⚠️ La base SQLite **NO** puede estar en una carpeta compartida por red (SMB/NFS) montada
  desde otra máquina: se puede corromper. Tiene que estar en un disco del mismo equipo donde
  corre el contenedor.
- Si el sistema de archivos lo permite (ZFS/Btrfs), **snapshots automáticos** diarios de
  `/srv/agroapp/datos`.

### 3. Usuario y acceso
- Un usuario **no root** (ej. `agro`), en el grupo `docker`, dueño de `/srv/agroapp`.
- **SSH** habilitado con clave (no contraseña) para administrar.

### 4. Red
- **IP fija** en la red de la casa (reserva DHCP en el router) y un nombre (ej. `nas`).
- Conexión por **cable** (no WiFi).
- Puerto **8000** accesible **solo desde la red local** (la web de AgroApp).
- **Acceso desde afuera** (desde el campo y para el webhook de WhatsApp). Muchos proveedores
  (y Starlink) usan **CGNAT**, que impide abrir puertos en el router, así que se usan túneles:
  - **Tailscale** (gratis): para entrar a la web de AgroApp desde el celular o la notebook,
    en forma **privada** (no queda publicada en internet). Recomendado.
  - **Cloudflare Tunnel** (`cloudflared`, gratis): para el **webhook de WhatsApp**, que
    necesita una dirección pública con HTTPS. Requiere un **dominio propio** en Cloudflare
    (≈ USD 10 por año). Solo se va a publicar la ruta `/whatsapp`, nada más.
  - Si no se quiere dominio ahora, dejar instalado solo Tailscale; el túnel se agrega después.

### 5. Energía
- **UPS** (se corta la luz) con apagado automático ordenado (NUT o la herramienta del
  sistema) y que el NAS **encienda solo** cuando vuelve la luz (opción en la BIOS:
  "Restore on AC power loss" → "Power On").

### 6. Backups fuera del NAS
- Copia diaria de `/srv/agroapp/datos/backups` a **otro lugar** (nube: Backblaze B2,
  Google Drive vía `rclone`, Hyper Backup, etc.). Si el NAS se quema o se lo roban, los
  datos del campo tienen que estar en otro lado.

## Lo que NO hay que hacer en el chat del NAS
(Lo hacemos después en el chat de AgroApp)
- Instalar AgroApp, crear el `Dockerfile` o el `docker-compose.yml`.
- Copiar la base de datos (hay que hacerlo con la app apagada, en un orden cuidadoso).
- Configurar WhatsApp o el webhook.
- Copiar el archivo `.env` (tiene claves: se copia a mano al final).

## Comandos para verificar que quedó listo

```bash
docker --version && docker compose version     # Docker y Compose v2
git --version
timedatectl                                     # Time zone: America/Argentina/Buenos_Aires, synchronized: yes
id agro                                         # el usuario está en el grupo docker
ls -ld /srv/agroapp                             # existe y es del usuario agro
df -h /srv/agroapp                              # en qué disco está y cuánto espacio queda
docker run --rm hello-world                     # Docker funciona sin sudo (con el usuario agro)
tailscale status                                # si se instaló Tailscale
cloudflared --version                           # si se instaló Cloudflare Tunnel
```

## Qué traer de vuelta al chat de AgroApp

Copiá esto completado:

```
Sistema operativo y versión:
Salida de "docker --version" y "docker compose version":
IP del NAS en la red local y nombre:
Usuario (y confirmación de que corre docker sin sudo):
Carpeta de la app (ej. /srv/agroapp) y tipo de disco (espejo/RAID, SSD/HDD, ZFS/Btrfs/ext4):
Salida de "timedatectl":
Tailscale: sí/no (nombre del NAS en Tailscale):
Cloudflare Tunnel: sí/no (dominio):
UPS: sí/no · Backups a la nube: sí/no (a dónde):
¿El código de AgroApp está en GitHub (repo privado)? sí/no
```
