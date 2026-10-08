# AgroApp — Roadmap

## ✅ Fase 0 — Base
- [x] FastAPI funcionando en local
- [x] Bot de Telegram (polling) conectado al backend
- [x] Git inicializado
- [x] Bot restringido a usuarios autorizados

## ✅ Fase 1 — Insumos
- [x] Tabla de insumos en SQLite + endpoints para crear y listar
- [x] Consultar stock desde Telegram (/stock, con filtro: /stock herbicida)
- [x] Crear insumos desde Telegram (/nuevo, acepta el tipo: /nuevo glifosato herbicida litros)
- [x] Movimientos de stock (entradas/salidas) con historial y transacciones
- [x] /entrada y /salida con búsqueda por nombre, sugerencias y formato argentino de números
- [x] Notas desde Telegram (/nota, /notas, /hecha)
- [x] Backup automático diario de la base (+ manual con `python backup.py`, + antes de migrar)
- [x] Subcategorías (herbicida, insecticida, filtros, correas...) y stock mínimo con alertas
- [x] Repuestos (página propia, /repuestos) vinculables a una o varias máquinas
- [x] Químicos en página propia (/quimicos) y tres hojas en el Excel completo (Insumos, Químicos, Repuestos)
- [x] Eliminar insumo (si no tiene movimientos) o archivarlo (si tiene historial)
- [ ] Ver historial de movimientos desde Telegram (/historial)  ← mini desafío (en la web ya está)

## ✅ Fase 1.5 — Frontend web (HTML + CSS + JS servido por FastAPI)
- [x] Paso 10: página con el stock de insumos (/web/)
- [x] Paso 11: formularios web para crear insumos y registrar movimientos
- [x] Rediseño según el lienzo "Design" con barra lateral
- [x] Editar, archivar y eliminar desde la web
- [x] Historial de movimientos con filtros (insumo, categoría, tipo, fechas, texto)
- [x] Buscador y filtros en todas las tablas (se guardan en la URL)
- [x] Refresco automático (lo cargado por Telegram aparece solo)
- [x] Rediseño claro minimalista con menú izquierdo plegable
- [x] Pantalla de Inicio: resumen, "requiere atención", accesos rápidos, últimos movimientos
- [x] Exportar a Excel: cada listado (con filtros) y "Descargar todo" (una hoja por tabla)

## ✅ Fase 2 — Maquinaria
- [x] Ficha de máquina: tipo, marca, modelo, año, n° de serie, patente, horas motor, horas de trilla
- [x] Services y arreglos (fecha, horas al momento, descripción, costo)
- [x] Trabajos realizados: hectáreas trilladas / sembradas / aplicadas, lote, cultivo
- [x] Vencimientos con fecha (seguros, licencias de piloto, VTV...) y alertas a 30 días
- [x] N° de serie del monitor en la máquina; lo muestran sus licencias y suscripciones (tipo "Suscripción / app")
- [x] Contactos: señal/GPS, repuestos, mecánicos, veterinarios...
- [x] Páginas web: listado, ficha, vencimientos, contactos
- [x] Telegram: /maquinas, /horas, /trabajo, /service, /arreglo, /vencimientos
- [x] Service programado por horas: varios planes por máquina (motor o trilla), alertas, /services

## ✅ Fase 3 — Ganadería (vacunos por caravana)
- [x] Animales: caravana, categoría, raza, rodeo, nacimiento, madre, estado (preñada, vacía)
- [x] Eventos: parto (mellizos, trillizos, sexo de las crías), aborto, tacto, servicio, sanidad
- [x] Alertas: fecha probable de parto (tacto o servicio + 283 días)
- [x] Páginas web (listado con resumen y filtros, ficha con historial y crías)
- [x] Telegram: /animales, /animal, /parto, /tacto, /servicio, /aborto, /alertas
- [x] Especies libres (ovinos, porcinos, gallinas, llamas...) con sus categorías y días de
      gestación; página Especies; grupos con cantidad; caravana repetible con confirmación (migración 7)
- [x] Resumen de crías: página Crías (partos, crías machos/hembras, mellizos, abortos, por especie,
      con filtros y Excel) y /crias por Telegram. Sale de los partos: no hace falta cargar cada cría

## ✅ Telegram con lenguaje natural
- [x] Mensajes sin comando interpretados con Gemini ("gasté 20 litros de glifosato en el lote 4")
- [x] Confirmación con "sí"/"no" antes de registrar; consultas se responden directo

## 🚧 Agricultura — lotes en mapa
- [x] Paso 1: página Lotes con mapa satelital (Leaflet + Esri), dibujar el polígono, nombre y observaciones,
      hectáreas calculadas solas (editables a mano), lista al costado, editar forma, eliminar (migración 9)
- [x] Cultivos con color (página Cultivos, que también tiene las campañas) — migración 10
- [x] Campañas: cultivo por lote y por campaña, primera y segunda; el mapa pintado por cultivo, con leyenda
- [x] Ficha del lote: cultivos por campaña, variedad, fechas, rinde (qq/ha), producción y trabajos de maquinaria
- [x] Mapa de lotes en Inicio (campaña elegida, leyenda con hectáreas por cultivo)
- [x] Importar lotes desde KMZ, KML o GeoJSON (vista previa, elegir cuáles, renombrar) y exportarlos a KML
- [ ] Importar Shapefile (.shp en .zip: John Deere Operations Center, monitores)
- [x] Campo (establecimiento) en los lotes: nombre único por campo, filtro, carpeta del KML = campo (migración 12)

## ✅ Organización de la web
- [x] Barra lateral por grupos (Agricultura primero) y "Descargar todo" abajo
- [x] Inicio nuevo: mapa general, última orden, última actividad, accesos rápidos, requiere atención compacto
- [x] Alerta de órdenes pendientes sin stock (Inicio, menú y Telegram)
- [ ] Ordenar el código (carpetas, nombres, archivos grandes) — al final

## 🚧 Órdenes de trabajo
- [x] Cargar a mano como la planilla (pulverización terrestre, dron...): encabezado, lotes, caldo, productos
      con dosis/ha o total (calcula el otro, por tancada y el agua) — migración 11
- [x] Advertencia si no alcanza el stock; al marcarla realizada descuenta todo (o nada) y queda en Movimientos
- [x] Volver a pendiente (devuelve el stock), anular, eliminar si nunca movió stock
- [x] Registro por lote: "1 al 12" se desarma y cada lote del mapa ve dosis/ha y su cantidad en su ficha
- [x] Imprimir con la forma de la planilla; listado con filtros y Excel; hojas en el Excel completo
- [ ] Cargar la orden desde una foto (bot de WhatsApp/Telegram + IA)
- [ ] Al realizar una orden, anotar el trabajo en la máquina (ha) automáticamente
- [ ] Actividades por lote (aplicaciones con insumos del stock, labores) y avances de siembra/cosecha
- [ ] Unir los trabajos de maquinaria al lote por id (hoy es por nombre escrito)

## Próximo (producción en el NAS — detalle en INICIO_PROYECTO.md)
- [ ] NAS listo (otro chat, según NAS_REQUISITOS.md)
- [x] Código en GitHub (`Facu289/AgTech-SaaS`; confirmar que sea privado)
- [x] Docker + docker-compose (api + bot, volumen datos/, TZ Argentina, healthcheck con /salud)
- [x] Rutas de base/backups y zona horaria desde el .env; backup diario aunque la app no se reinicie
- [x] Script de mudanza: backup, copia, SHA-256, integrity_check (`python -m app.nucleo.mudanza`)
- [ ] Probar Docker en el NAS y mudar la base (guía: `docs/NAS_INSTALAR.md`)
- [x] Login en la web: usuario y contraseña (hash scrypt), sesión con cookie (HttpOnly, SameSite=Lax,
      Secure con HTTPS), página de login y botón Salir, toda la web y la API protegidas, el bot entra
      con su token (AGROAPP_BOT_TOKEN), usuarios por consola (`python -m app.usuarios.crear_usuario`), migración 8
- [x] Bot de WhatsApp (Meta Cloud API): webhook `/whatsapp` con firma, mismos comandos y Gemini que Telegram
- [x] WhatsApp en el NAS: variables en el .env, webhook verificado en Meta
- [x] Política de privacidad pública (`/privacidad`, `/eliminar-datos`) y logo como ícono de la web
- [ ] Publicar la app en Meta y probar desde el celu
- [ ] Migrar de Telegram a WhatsApp (convivir unas semanas y después apagar el bot de Telegram)
- [ ] Cloudflare Tunnel: publicar SOLO `/whatsapp`, `/privacidad`, `/eliminar-datos` y el logo
      (hoy publica toda la app, protegida por el login)
- [ ] Backups fuera del NAS (nube)

## Después
- [ ] Usar la app con datos reales durante unas semanas y anotar qué falta o molesta
- [ ] Pesadas (kg por animal) y ganancia de peso
- [ ] Grupos: registrar altas y bajas de cabezas (nacimientos, muertes, ventas) con historial
- [ ] Aves: postura de huevos

## Futuro
- [ ] Bot con botones: crear insumo y cargar datos respondiendo preguntas
- [ ] Leer fotos de órdenes de aplicación y descontar agroquímicos del stock
- [ ] Órdenes de trabajo (unidad "dosis")
- [ ] React, mapas (Leaflet/OpenStreetMap), PostgreSQL
