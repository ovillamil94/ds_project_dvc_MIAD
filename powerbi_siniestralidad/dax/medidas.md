# Medidas DAX

Las medidas pertenecen a Siniestros. Las categorías de actores y vehículos pueden compartir el mismo evento.

## Total siniestros

Eventos canónicos en el contexto de fecha, localidad y severidad.

```dax
Total siniestros = DISTINCTCOUNT(Siniestros[ClaveFuente])
```

## Personas registradas

Registros de actor deduplicados exactamente dentro de la edición elegida.

```dax
Personas registradas = COUNTROWS(Actores)
```

## Lesionados

Personas registradas con lesión según el criterio de gravedad disponible.

```dax
Lesionados = CALCULATE([Personas registradas], KEEPFILTERS(Actores[Resultado] = "LESIONADO"))
```

## Fallecidos

Personas registradas fallecidas según el criterio de gravedad disponible.

```dax
Fallecidos = CALCULATE([Personas registradas], KEEPFILTERS(Actores[Resultado] = "FALLECIDO"))
```

## Vehículos registrados

Filas vehiculares de la edición elegida, incluidas las que carecen de código de vehículo.

```dax
Vehículos registrados = COUNTROWS(Vehiculos)
```

## Siniestros por actor

Eventos con al menos un registro del actor seleccionado.

```dax
Siniestros por actor = DISTINCTCOUNT(Actores[ClaveFuente])
```

## Siniestros por vehículo

Eventos con al menos un vehículo del tipo seleccionado.

```dax
Siniestros por vehículo = DISTINCTCOUNT(Vehiculos[ClaveFuente])
```

## Vehículos por siniestro

Promedio de vehículos del contexto por evento que tiene esos vehículos.

```dax
Vehículos por siniestro = DIVIDE([Vehículos registrados], [Siniestros por vehículo])
```

## Participación actores

Cuota sobre los tipos de actor visibles en la selección.

```dax
Participación actores = DIVIDE([Personas registradas], CALCULATE([Personas registradas], ALLSELECTED(TiposActor[condicion])))
```

## Participación vehículos

Cuota sobre los tipos de vehículo visibles en la selección.

```dax
Participación vehículos = DIVIDE([Vehículos registrados], CALCULATE([Vehículos registrados], ALLSELECTED(TiposVehiculo[clase_vehiculo_nombre])))
```

## Siniestros fatales

Eventos clasificados con muertos en la fuente de siniestros.

```dax
Siniestros fatales = CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Severidad] = "CON MUERTOS"))
```

## Porcentaje fatal

Proporción fatal entre los eventos con severidad informada.

```dax
Porcentaje fatal = DIVIDE([Siniestros fatales], CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Severidad] <> "SIN INFORMACION")))
```

## Georreferenciados

Eventos con un par latitud y longitud dentro del rango de control.

```dax
Georreferenciados = CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Georreferenciado] = TRUE()))
```

## Cobertura geográfica

Proporción de eventos con coordenadas dentro del rango de control.

```dax
Cobertura geográfica = DIVIDE([Georreferenciados], [Total siniestros])
```

## Siniestros actor y vehículo

Eventos donde coexisten el actor y el tipo de vehículo seleccionados.

```dax
Siniestros actor y vehículo = CALCULATE([Total siniestros], KEEPFILTERS(TREATAS(VALUES(Actores[ClaveFuente]), Siniestros[ClaveFuente])), KEEPFILTERS(TREATAS(VALUES(Vehiculos[ClaveFuente]), Siniestros[ClaveFuente])))
```

## Siniestros con velocidad

Eventos con bandera de velocidad verdadera.

```dax
Siniestros con velocidad = CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[con_velocidad] = TRUE()))
```

## Siniestros con embriaguez

Eventos con bandera de embriaguez verdadera.

```dax
Siniestros con embriaguez = CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[con_embriaguez] = TRUE()))
```

## Mes anterior

Eventos en las fechas visibles desplazadas un período.

```dax
Mes anterior = CALCULATE([Total siniestros], DATEADD(Calendario[Fecha], -1, MONTH))
```

## Variación mensual

Cambio relativo frente al período mensual anterior.

```dax
Variación mensual = IF([Mes anterior] > 0, DIVIDE([Total siniestros] - [Mes anterior], [Mes anterior]))
```

## Año anterior

Eventos en las fechas visibles desplazadas un período.

```dax
Año anterior = CALCULATE([Total siniestros], DATEADD(Calendario[Fecha], -1, YEAR))
```

## Variación anual

Cambio relativo frente al período anual anterior.

```dax
Variación anual = IF([Año anterior] > 0, DIVIDE([Total siniestros] - [Año anterior], [Año anterior]))
```
