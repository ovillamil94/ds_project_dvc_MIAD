let
    Base = DetalleCanonico("actor_vial", true),
    Categorias = Table.TransformColumns(Base, {{"condicion", Categoria, type text}, {"condicion_especifica", Categoria, type text}, {"sexo", Categoria, type text}}),
    Gravedad = Table.AddColumn(Categorias, "Resultado", each let g = Categoria([gravedad_30d] ?? [gravedad_tradicional]) in
        if List.Contains({"HERIDO","HERIDO HOSPITALIZADO","HERIDO VALORADO"}, g) then "LESIONADO"
        else if List.Contains({"MUERTO","MUERTA"}, g) then "FALLECIDO"
        else g, type text),
    Edad = Table.TransformColumns(Gravedad, {{"edad", each if _ <> null and _ >= 0 and _ <= 120 then _ else null, Int64.Type}})
in
    Table.SelectColumns(Edad, {"ClaveFuente","condicion","condicion_especifica","sexo","edad","Resultado"})
