let
    Raw = LeerParquet("siniestros"),
    Tipos = Table.TransformColumnTypes(Raw, {{"fecha", type date}, {"source_year", Int64.Type}, {"codigo_siniestro", Int64.Type}, {"hora", Int64.Type}, {"latitud", type number}, {"longitud", type number}}),
    Fuentes = Table.AddColumn(Tipos, "ClaveFuente", each ClaveFuente(_), type text),
    Control = if List.Contains(Fuentes[fecha], null) or Table.RowCount(Fuentes) <> List.Count(List.Distinct(Fuentes[ClaveFuente])) then error "Fecha ausente o clave de fuente duplicada" else Fuentes,
    Eventos = Table.AddColumn(Control, "AnioEvento", each Date.Year([fecha]), Int64.Type),
    Ediciones = Table.Group(Eventos, {"AnioEvento", "codigo_siniestro"}, {{"Edicion", each List.Max([source_year]), Int64.Type}, {"Formularios", each List.Distinct([formulario]), type list}, {"N", each Table.RowCount(_), Int64.Type}}),
    Validas = Table.SelectRows(Ediciones, each if [N] > 1 and (List.Count([Formularios]) <> 1 or List.Contains([Formularios], null)) then error "Ediciones con formularios incompatibles" else true),
    Canonicos = Table.RemoveColumns(Table.NestedJoin(Eventos, {"AnioEvento", "codigo_siniestro", "source_year"}, Validas, {"AnioEvento", "codigo_siniestro", "Edicion"}, "Edicion", JoinKind.Inner), {"Edicion"}),
    Localidad = Table.TransformColumns(Canonicos, {{"localidad", Categoria, type text}, {"clase_nombre", Categoria, type text}}),
    Gravedad = Table.AddColumn(Localidad, "Severidad", each Categoria([gravedad_30d_nombre] ?? [gravedad_tradicional_nombre]), type text),
    Geo = Table.AddColumn(Gravedad, "Georreferenciado", each [latitud] <> null and [longitud] <> null and [latitud] >= 4 and [latitud] <= 5 and [longitud] >= -75 and [longitud] <= -73, type logical),
    Resultado = Table.SelectColumns(Geo, {"ClaveFuente","codigo_siniestro","source_year","fecha","hora","localidad","clase_nombre","Severidad","latitud","longitud","Georreferenciado","con_embriaguez","con_velocidad","con_huecos","con_moto","con_peaton","con_bicicleta"})
in
    Resultado
