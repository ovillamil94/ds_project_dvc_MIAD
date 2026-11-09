let
    Base = DetalleCanonico("vehiculos", false),
    Categorias = Table.TransformColumns(Base, {{"clase_vehiculo_nombre", Categoria, type text}, {"servicio_nombre", Categoria, type text}})
in
    Table.SelectColumns(Categorias, {"ClaveFuente","codigo_vehiculo","clase_vehiculo_nombre","servicio_nombre","en_fuga"})
