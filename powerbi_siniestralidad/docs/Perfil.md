# Perfil de los datos

| Archivo | Filas | Duplicados exactos excedentes |
|---|---:|---:|
| siniestros | 416.283 | 0 |
| actor_vial | 912.522 | 127 |
| vehiculos | 779.660 | 0 |
| diccionario | 102 | 0 |

El perfil de columnas, tipos, nulos, cardinalidades y mínimos y máximos está en `analysis/perfil.json`. Los eventos abarcan del 1 de enero de 2015 al 31 de diciembre de 2025. El archivo fuente 2024 incluye retrospectivamente eventos desde 2015.

**Ediciones superpuestas.** Hay 126.088 grupos duplicados por año de la fecha y código. En cada grupo coincide el formulario. Se selecciona el mayor `source_year` y se conservan sus hijos. Algunos pares tienen distinta fecha dentro del mismo año o distinta localidad. Hay códigos reutilizados entre años, por lo que se separan por año del evento. La concordancia de formularios respalda la selección por edición, aunque diferencias entre fuentes pueden reflejar cambios de cobertura o revisiones de clasificación.

**Severidad.** Se usa 30 días cuando existe y la gravedad tradicional como respaldo. Los heridos valorados u hospitalizados se agrupan como lesionados. Se preserva la falta de información. Las cifras de eventos fatales y personas fallecidas corresponden a granularidades distintas. El porcentaje fatal usa como denominador los eventos con severidad informada.

**Territorio.** Hay 275.122 eventos con coordenadas dentro del rango operativo de latitud 4–5 y longitud −75 a −73. Este control comprueba un rango plausible. Para validar jurisdicción exacta haría falta un límite geográfico oficial. El ranking territorial usa el campo localidad, con cobertura independiente de las coordenadas.

**Lectura ejecutiva.** Los recuentos anuales descienden de 25.453 en 2022 a 14.114 en 2023 y 11.573 en 2025. Los cambios de edición, la cobertura y la severidad disponible deben revisarse antes de interpretar la caída como cambio del riesgo vial. Las banderas de velocidad y embriaguez cuentan casos señalados. Los valores nulos no se imputan y el conjunto carece de denominadores de exposición.
