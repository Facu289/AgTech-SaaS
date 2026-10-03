# Instalar AgroApp en el NAS y mudar la base

> Guía paso a paso para cuando el NAS esté listo (ver `NAS_REQUISITOS.md`).
> Supone: carpeta `/srv/agroapp`, usuario `agro`, el NAS se llama `nas` en la red.
> Si algo da un error, **pará ahí** y traé el mensaje al chat: no sigas con el paso siguiente.

## Qué hay en el proyecto para esto

| Archivo | Para qué |
|---|---|
| `Dockerfile` | receta de la imagen: Python 3.14, librerías, zonas horarias y el código |
| `.dockerignore` | lo que NO entra en la imagen (`.env`, `datos/`, `.venv/`...) |
| `docker-compose.yml` | dos servicios con la misma imagen: **api** (web + API) y **bot** |
| `app/nucleo/mudanza.py` | prepara la base en la PC y la verifica en el NAS |
| `GET /salud` | Docker pregunta acá si la app anda (no pide login, no muestra datos) |

## 0. En la PC, antes de empezar

1. Todo commiteado y en `main` en GitHub (el repo es `Facu289/AgTech-SaaS`).
   Fijate en GitHub → Settings → General que diga **Private**.
2. `python -m pytest` pasa.

## 1. Bajar el código en el NAS

Repo privado: el NAS necesita permiso para leerlo. Lo más prolijo es una **deploy key**
(una llave SSH que solo sirve para LEER este repo):

```bash
ssh agro@nas
ssh-keygen -t ed25519 -C "nas-agroapp" -f ~/.ssh/agroapp_github -N ""
cat ~/.ssh/agroapp_github.pub     # copiá esta línea
```

En GitHub: repo → Settings → Deploy keys → Add deploy key → pegala (sin tildar "Allow write").

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-agroapp
  HostName github.com
  User git
  IdentityFile ~/.ssh/agroapp_github
EOF
git clone git@github-agroapp:Facu289/AgTech-SaaS.git /srv/agroapp
cd /srv/agroapp
mkdir -p datos
```

## 2. El `.env` del NAS (a mano, nunca por Git)

Desde la PC (PowerShell, en la carpeta `agroapp`):

```powershell
scp .env agro@nas:/srv/agroapp/.env
```

En el NAS:

```bash
cd /srv/agroapp
chmod 600 .env            # solo el usuario agro lo puede leer
id agro                   # anotá uid=... y gid=...
nano .env
```

Agregá al final el bloque **"Docker / NAS"** de `ejemplo_env.txt` y poné tu `uid`/`gid`
en `AGROAPP_UID` y `AGROAPP_GID`. Si una clave tiene un `$`, escribilo `$$`.

Revisá que Docker entienda todo (muestra la configuración final; **no la pegues en ningún
lado: incluye tus claves**):

```bash
docker compose config --quiet && echo "configuración OK"
docker compose build
```

⚠️ **Todavía no lo prendas** (`up`): si arranca sin base, crea una vacía.

## 3. Mudar la base (con la app de la PC apagada)

**En la PC**: cerrá el backend y el bot (Ctrl+C en sus terminales). Después:

```powershell
python -m app.nucleo.mudanza preparar
```

Hace un backup, arma `datos\mudanza\agroapp.db`, la revisa (integrity_check y relaciones)
y guarda su huella en `datos\mudanza\agroapp.db.sha256`. **Sacale una foto a la salida**
(las filas por tabla). Si el backend sigue prendido, se niega y te avisa.

Copiala al NAS:

```powershell
scp datos\mudanza\agroapp.db datos\mudanza\agroapp.db.sha256 agro@nas:/srv/agroapp/datos/
```

**En el NAS**:

```bash
cd /srv/agroapp/datos && sha256sum -c agroapp.db.sha256 && cd ..
docker compose run --rm --no-deps api python -m app.nucleo.mudanza verificar /app/datos/agroapp.db
```

Tiene que decir `agroapp.db: OK`, "la huella coincide" y **las mismas filas por tabla** que
en la PC. Recién ahí:

```bash
docker compose up -d
docker compose ps           # la api tiene que decir "healthy" (tarda unos 30 s)
docker compose logs bot     # "Bot iniciado. Backend: http://api:8000..."
```

## 4. Probar

1. Web: `http://nas:8000/web/` (o la IP del NAS) → entrar con tu usuario.
   Si todavía no creaste ninguno: `docker compose exec api python -m app.usuarios.crear_usuario`
2. Telegram: mandá `/stock` y `/alertas`.
3. Backup manual: `docker compose exec api python -m app.nucleo.backup` → aparece en `datos/backups/`.
4. Reiniciá el NAS y fijate que todo vuelva solo (`docker compose ps`).

⚠️ **Desde ahora no prendas el bot en la PC**: dos bots con el mismo token chocan.
La base de la PC queda como estaba (copia vieja): no la uses más para cargar datos.

## Día a día

| Para... | En `/srv/agroapp` |
|---|---|
| ver el estado | `docker compose ps` |
| ver qué pasa | `docker compose logs -f --tail 50` (Ctrl+C para salir) |
| actualizar a la última versión | `git pull && docker compose up -d --build` |
| reiniciar | `docker compose restart` |
| apagar | `docker compose down` (los datos quedan en `datos/`) |
| correr los tests en el NAS | `docker compose run --rm --no-deps api python -m pytest -q` |

## Si algo sale mal y hay que volver a la PC

1. En el NAS: `docker compose down`.
2. En la PC: prendé backend y bot como siempre. La base de la PC no se tocó.
3. Ojo: lo que se haya cargado en el NAS mientras tanto queda solo en la base del NAS.
