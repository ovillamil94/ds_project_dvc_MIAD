# Validación

## Controles ejecutados en DuckDB

| Control | Resultado |
|---|---:|
| Clave fuente del evento repetida o incompleta | 0 |
| Detalles actor sin evento fuente | 0 |
| Detalles vehículo sin evento fuente | 0 |
| Grupos de eventos repetidos con formulario concordante | 126.088 de 126.088 |
| Filas fuente de siniestros menos copias de otras ediciones | 416.283 − 126.088 = 290.195 |
| Eventos canónicos sin fila de actor en su edición | 151 |
| Eventos canónicos sin fila de vehículo en su edición | 148 |
| Referencias actor–vehículo sin coincidencia en origen | 25.494 |

## Totales esperados en Desktop sin filtros

| Medida | Esperado |
|---|---:|
| Total siniestros | 290.195 |
| Personas registradas | 636.205 |
| Lesionados | 199.551 |
| Fallecidos | 5.639 |
| Vehículos registrados | 543.160 |
| Georreferenciados | 275.122 |
| Siniestros fatales | 5.489 |

Para control temporal, el año 2024 del calendario debe dar 13.949 siniestros y el 2025 debe dar 11.573. El filtro por año debe afectar los tres hechos. En geografía, el cruce de actor y vehículo debe responder a ambas selecciones y el conteo territorial general sigue el contexto de fecha, localidad y severidad.

## Pendientes en Desktop

- Confirmar apertura de PBIP, carga de Power Query y conciliación de la consulta DAX.
- Recorrer las cinco páginas y probar navegación, selección cruzada, comparación mensual y anual, tooltips y mapa.
- Usar **Optimizar > Analizador de rendimiento** y registrar tiempos de actualización y visualización con y sin filtros. El perfil en DuckDB no mide el rendimiento de Power BI.
