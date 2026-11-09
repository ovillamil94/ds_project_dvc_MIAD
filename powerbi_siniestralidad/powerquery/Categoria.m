(valor as nullable text) as text =>
if valor = null or Text.Trim(valor) = "" then "SIN INFORMACION" else Text.Upper(Text.Trim(Text.Clean(valor)), "es-CO")
