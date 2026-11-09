(fila as record) as text =>
Text.From(fila[source_year], "en-US") & "|" & Text.From(fila[codigo_siniestro], "en-US")
