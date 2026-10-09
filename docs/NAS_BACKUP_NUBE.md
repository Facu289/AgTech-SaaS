# Backups de AgroApp en la nube (rclone + Google Drive)

> Objetivo: que una copia de la base viva **fuera del NAS**. Si el NAS se rompe, se quema o se lo
> roban, la base se recupera desde la nube.

## Cómo funciona

```
app (cada día) ─► /srv/agroapp/datos/backups/agroapp_AAAA-MM-DD_HHMMSS.db
cron (3:30 cada día) ─► scripts/backup_nube.sh ─► rclone ─► Google Drive: AgroApp/backups/
```

- La app **ya** hace el backup diario (`app/nucleo/backup.py`). Este paso solo lo **sube**.
- `rclone copy`: sube lo nuevo y **no borra** nada en la nube aunque se borre en el NAS.
- Opcional (recomendado): **cifrado** con rclone. En Drive se ven nombres y contenido ilegibles;
  sin la contraseña no se pueden abrir. Si se pierde esa contraseña, **los backups no sirven**:
  guardala en un gestor de contraseñas o en papel, fuera del NAS.

Todo esto se hace **en el NAS, por SSH**, como `choco` con `sudo` (cron corre como root).

## 1. Instalar rclone

```bash
cat /etc/os-release | head -3        # para saber qué sistema tiene el NAS
sudo apt update && sudo apt install -y rclone
rclone version                       # tiene que mostrar la versión
```

Si el NAS no usa `apt` (TrueNAS, por ejemplo), avisá antes de seguir.

## 2. Conectar Google Drive

El NAS no tiene navegador, así que la autorización de Google se hace **desde la PC**.

1. En la PC (PowerShell), instalá rclone: `winget install Rclone.Rclone` (cerrá y abrí PowerShell).
2. En el NAS: `sudo rclone config`
   - `n` (nuevo remoto) · nombre: `gdrive`
   - Storage: escribí `drive` (Google Drive)
   - `client_id` y `client_secret`: Enter (vacíos)
   - scope: `3` (**drive.file**: rclone solo ve los archivos que crea él, no tu Drive entero)
   - `service_account_file`: Enter · "Edit advanced config?": `n`
   - "Use web browser to automatically authenticate?": **`n`**
   - Te muestra un comando que empieza con `rclone authorize "drive" ...`. **Copialo**.
3. En la PC: pegá ese comando en PowerShell. Se abre el navegador: entrá con tu cuenta de Google
   y aceptá. PowerShell muestra un texto largo (el token, entre `--->` y `<---`). **Copialo**.
4. En el NAS: pegá ese texto donde dice `config_token>`.
   - "Configure this as a Shared Drive?": `n` · confirmar: `y` · salir: `q`

Prueba: `sudo rclone lsd gdrive:` (no da error = conectado).

## 3. Cifrado (recomendado)

En el NAS: `sudo rclone config`
- `n` · nombre: `agroapp-nube` · Storage: `crypt`
- remote: `gdrive:AgroApp-cifrado`
- filename_encryption: `1` (standard) · directory_name_encryption: `1` (true)
- password: `y` (la escribís vos) → inventá una larga y **guardala fuera del NAS**
- password2 (salt): `g` (generar) → **guardala también**
- "Edit advanced config?": `n` · confirmar `y` · salir `q`

**Sin cifrado**: en vez de lo anterior, el script se corre con `REMOTO=gdrive:AgroApp/backups`
(ver el paso 5). Recomiendo el cifrado: la base tiene todo el stock y los datos del campo.

## 4. Primera subida a mano

```bash
cd /srv/agroapp
git pull                                   # trae scripts/backup_nube.sh
sudo sh scripts/backup_nube.sh
sudo tail -20 /var/log/agroapp_backup_nube.log
sudo rclone ls agroapp-nube:AgroApp/backups   # tienen que aparecer los agroapp_*.db
```

En Google Drive vas a ver la carpeta `AgroApp-cifrado` con nombres raros: eso es el cifrado.

## 5. Que se haga solo todos los días (cron)

```bash
sudo crontab -e
```
(Si pregunta el editor, elegí `nano`). Agregá al final esta línea, guardá (Ctrl+O, Enter) y salí (Ctrl+X):

```
30 3 * * * sh /srv/agroapp/scripts/backup_nube.sh
```

Sin cifrado sería: `30 3 * * * REMOTO=gdrive:AgroApp/backups sh /srv/agroapp/scripts/backup_nube.sh`

Comprobar: `sudo crontab -l`. Al otro día: `sudo tail /var/log/agroapp_backup_nube.log`.

## 6. Probar que se puede RESTAURAR (hacerlo una vez, y cada tanto)

Un backup que nunca se probó no es un backup. Esto baja la copia más nueva a una carpeta de
prueba y la revisa, **sin tocar la base real**:

```bash
mkdir -p /tmp/prueba_restaurar
ULTIMO=$(sudo rclone lsf agroapp-nube:AgroApp/backups --include "agroapp_*.db" | sort | tail -1)
echo "Bajando $ULTIMO"
sudo rclone copy "agroapp-nube:AgroApp/backups/$ULTIMO" /tmp/prueba_restaurar
sudo docker run --rm -v /tmp/prueba_restaurar:/x agroapp:latest \
  python -c "import sqlite3; c=sqlite3.connect('file:/x/$ULTIMO?mode=ro', uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print('insumos:', c.execute('select count(*) from insumos').fetchone()[0])"
rm -rf /tmp/prueba_restaurar
```

Tiene que decir `ok` y la cantidad de insumos que tenés.

**Restaurar de verdad** (solo si se perdió la base): apagar la app (`sudo docker compose down`),
bajar el backup como arriba, copiarlo a `/srv/agroapp/datos/agroapp.db` (guardando aparte la base
rota, por las dudas), revisar dueño (`sudo chown agroapp:agroapp ...`) y prender
(`sudo docker compose up -d`).

## Qué NO se sube

- El `.env` (claves): no va a la nube. Guardá una copia en un lugar seguro (gestor de contraseñas).
  Sin el `.env` la app se rearma igual, pero hay que volver a sacar los tokens de Meta, Telegram, etc.
- El código: ya está en GitHub.
