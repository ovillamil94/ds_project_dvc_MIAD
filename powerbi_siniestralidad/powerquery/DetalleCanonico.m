(nombre as text, eliminarDuplicados as logical) as table =>
let
    Raw = LeerParquet(nombre),
    Filas = if eliminarDuplicados then Table.Distinct(Raw) else Raw,
    Claves = Table.AddColumn(Filas, "ClaveFuente", each ClaveFuente(_), type text),
    Seleccion = Table.NestedJoin(Claves, {"ClaveFuente"}, Table.SelectColumns(Siniestros, {"ClaveFuente"}), {"ClaveFuente"}, "Padre", JoinKind.Inner)
in
    Table.RemoveColumns(Seleccion, {"Padre"})
