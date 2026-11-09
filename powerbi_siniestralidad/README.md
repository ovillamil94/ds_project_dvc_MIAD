# Movilidad vial de Bogotá · Power BI

Desde la raíz del repositorio ejecuta `dvc pull data/processed.dvc` para descargar los cuatro Parquet. Abre **Vial.pbip** en Power BI Desktop. Si el equipo solicita compatibilidad con proyectos PBIP o con PBIR mejorado, habilita la característica correspondiente en **Archivo > Opciones y configuración > Opciones > Características de versión preliminar** y reinicia Desktop.

1. Abre **Inicio > Transformar datos > Editar parámetros**. En **RutaDatos**, escribe la ruta absoluta de `data/processed` del repositorio.
2. Usa **Inicio > Actualizar** para importar los Parquet. Si Desktop solicita configurar el origen local, revísalo en **Configuración de origen de datos**.
3. Abre **Vista de consultas DAX**, pega `dax/validacion.dax` y ejecuta. Compara la fila con los valores de `docs/Validacion.md`.
4. Verifica las cinco pestañas. Usa **Ctrl + clic** en la barra de navegación de Power BI Desktop. Si quieres conservar selecciones de año, localidad y severidad al cambiar de página, abre **Ver > Sincronizar segmentaciones** y sincroniza cada campo en las cinco páginas. Las segmentaciones ya están colocadas en cada página.
5. Si el visual de mapa no está disponible en tu configuración, usa la concentración por localidad que ya está en la misma página. Para análisis espacial, acota el período y la localidad porque el visual puede muestrear los puntos.

| Carpeta | Contenido |
|---|---|
| analysis | Perfil, diccionario, conciliación y generadores reproducibles |
| powerquery | Consultas M editables |
| dax | Medidas documentadas y consulta para conciliar totales |
| model | Modelo semántico importado y diagrama |
| theme | Tema JSON importable desde **Ver > Temas > Buscar temas** |
| reports | Definición PBIR editable de las cinco páginas |
| docs | Perfil interpretado y validación |

Para repetir el perfil, instala DuckDB en el entorno de Python y ejecuta `python analysis/perfilar.py` desde esta carpeta. Para regenerar el PBIP a partir de las consultas y el diseño incluidos, ejecuta `python analysis/construir.py` con Power BI Desktop cerrado. El generador sobrescribe los archivos que produce.

Formatos de proyecto y reporte según [Microsoft Learn · PBIP](https://learn.microsoft.com/power-bi/developer/projects/projects-overview) y [Microsoft Learn · PBIR](https://learn.microsoft.com/power-bi/developer/projects/projects-report).
