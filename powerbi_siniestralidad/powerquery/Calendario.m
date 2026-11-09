let
    Inicio = Date.StartOfYear(List.Min(Siniestros[fecha])),
    Fin = Date.EndOfYear(List.Max(Siniestros[fecha])),
    Fechas = Table.FromColumns({List.Dates(Inicio, Duration.Days(Fin - Inicio) + 1, #duration(1,0,0,0))}, type table [Fecha=date]),
    Anio = Table.AddColumn(Fechas, "Año", each Date.Year([Fecha]), Int64.Type),
    Mes = Table.AddColumn(Anio, "Mes", each Date.ToText([Fecha], "yyyy-MM", "es-CO"), type text),
    Dia = Table.AddColumn(Mes, "Día", each Date.DayOfWeekName([Fecha], "es-CO"), type text)
in
    Table.AddColumn(Dia, "OrdenDia", each Date.DayOfWeek([Fecha], Day.Monday) + 1, Int64.Type)
