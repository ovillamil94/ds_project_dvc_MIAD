(nombre as text) as table =>
let
    Archivo = nombre & ".parquet",
    Contenido = OrigenParquet{[Name = Archivo]}[Content]
in
    Parquet.Document(Contenido)
