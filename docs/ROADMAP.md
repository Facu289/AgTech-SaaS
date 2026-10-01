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

## ✅ Telegram con lenguaje natural
- [x] Mensajes sin comando interpretados con Gemini ("gasté 20 litros de glifosato en el lote 4")
- [x] Confirmación con "sí"/"no" antes de registrar; consultas se responden directo

## Próximo (producción en el NAS — detalle en INICIO_PROYECTO.md)
- [ ] NAS listo (otro chat, según NAS_REQUISITOS.md)
- [ ] Código en GitHub (repo privado)
- [ ] Docker + docker-compose (api + bot) y mudar la base al NAS
- [ ] Login en la web
- [ ] Bot de WhatsApp (Meta Cloud API + Cloudflare Tunnel), mismos comandos que Telegram
- [ ] Backups fuera del NAS (nube)

## Después
- [ ] Usar la app con datos reales durante unas semanas y anotar qué falta o molesta
- [ ] Pesadas (kg por animal) y ganancia de peso

## Futuro
- [ ] Bot con botones: crear insumo y cargar datos respondiendo preguntas
- [ ] Leer fotos de órdenes de aplicación y descontar agroquímicos del stock
- [ ] Órdenes de trabajo (unidad "dosis")
- [ ] React, mapas (Leaflet/OpenStreetMap), PostgreSQL
