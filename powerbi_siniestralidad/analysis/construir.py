"""Construye el PBIP editable a partir de las consultas M y definiciones del informe."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/"
MODEL = ROOT / "model" / "Vial.SemanticModel"
REPORT = ROOT / "reports" / "Vial.Report"
DEFINITION = REPORT / "definition"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def schema(name, value):
    return {"$schema": SCHEMA + name + "/schema.json", **value}


def m(name):
    return (ROOT / "powerquery" / f"{name}.m").read_text(encoding="utf-8").splitlines()


tables = {
    "Siniestros": {"ClaveFuente":"string","codigo_siniestro":"int64","source_year":"int64","fecha":"dateTime","hora":"int64","localidad":"string","clase_nombre":"string","Severidad":"string","latitud":"double","longitud":"double","Georreferenciado":"boolean", **{f"con_{x}":"boolean" for x in ("embriaguez","velocidad","huecos","moto","peaton","bicicleta")}},
    "Actores": {"ClaveFuente":"string","condicion":"string","condicion_especifica":"string","sexo":"string","edad":"int64","Resultado":"string"},
    "Vehiculos": {"ClaveFuente":"string","codigo_vehiculo":"int64","clase_vehiculo_nombre":"string","servicio_nombre":"string","en_fuga":"boolean"},
    "Calendario": {"Fecha":"dateTime","Año":"int64","Mes":"string","Día":"string","OrdenDia":"int64"},
    "Localidades": {"localidad":"string"},
    "TiposActor": {"condicion":"string"},
    "TiposVehiculo": {"clase_vehiculo_nombre":"string"},
}
relations = [
    ("Siniestros","fecha","Calendario","Fecha"),
    ("Siniestros","localidad","Localidades","localidad"),
    ("Actores","ClaveFuente","Siniestros","ClaveFuente"),
    ("Vehiculos","ClaveFuente","Siniestros","ClaveFuente"),
    ("Actores","condicion","TiposActor","condicion"),
    ("Vehiculos","clase_vehiculo_nombre","TiposVehiculo","clase_vehiculo_nombre"),
]
measures = {
    "Total siniestros": ("DISTINCTCOUNT(Siniestros[ClaveFuente])", "Eventos canónicos en el contexto de fecha, localidad y severidad."),
    "Personas registradas": ("COUNTROWS(Actores)", "Registros de actor deduplicados exactamente dentro de la edición elegida."),
    "Lesionados": ('CALCULATE([Personas registradas], KEEPFILTERS(Actores[Resultado] = "LESIONADO"))', "Personas registradas con lesión según el criterio de gravedad disponible."),
    "Fallecidos": ('CALCULATE([Personas registradas], KEEPFILTERS(Actores[Resultado] = "FALLECIDO"))', "Personas registradas fallecidas según el criterio de gravedad disponible."),
    "Vehículos registrados": ("COUNTROWS(Vehiculos)", "Filas vehiculares de la edición elegida, incluidas las que carecen de código de vehículo."),
    "Siniestros por actor": ("DISTINCTCOUNT(Actores[ClaveFuente])", "Eventos con al menos un registro del actor seleccionado."),
    "Siniestros por vehículo": ("DISTINCTCOUNT(Vehiculos[ClaveFuente])", "Eventos con al menos un vehículo del tipo seleccionado."),
    "Vehículos por siniestro": ("DIVIDE([Vehículos registrados], [Siniestros por vehículo])", "Promedio de vehículos del contexto por evento que tiene esos vehículos."),
    "Participación actores": ("DIVIDE([Personas registradas], CALCULATE([Personas registradas], ALLSELECTED(TiposActor[condicion])))", "Cuota sobre los tipos de actor visibles en la selección."),
    "Participación vehículos": ("DIVIDE([Vehículos registrados], CALCULATE([Vehículos registrados], ALLSELECTED(TiposVehiculo[clase_vehiculo_nombre])))", "Cuota sobre los tipos de vehículo visibles en la selección."),
    "Siniestros fatales": ('CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Severidad] = "CON MUERTOS"))', "Eventos clasificados con muertos en la fuente de siniestros."),
    "Porcentaje fatal": ('DIVIDE([Siniestros fatales], CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Severidad] <> "SIN INFORMACION")))', "Proporción fatal entre los eventos con severidad informada."),
    "Georreferenciados": ("CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[Georreferenciado] = TRUE()))", "Eventos con un par latitud y longitud dentro del rango de control."),
    "Cobertura geográfica": ("DIVIDE([Georreferenciados], [Total siniestros])", "Proporción de eventos con coordenadas dentro del rango de control."),
    "Siniestros actor y vehículo": ("CALCULATE([Total siniestros], KEEPFILTERS(TREATAS(VALUES(Actores[ClaveFuente]), Siniestros[ClaveFuente])), KEEPFILTERS(TREATAS(VALUES(Vehiculos[ClaveFuente]), Siniestros[ClaveFuente])))", "Eventos donde coexisten el actor y el tipo de vehículo seleccionados."),
    "Siniestros con velocidad": ("CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[con_velocidad] = TRUE()))", "Eventos con bandera de velocidad verdadera."),
    "Siniestros con embriaguez": ("CALCULATE([Total siniestros], KEEPFILTERS(Siniestros[con_embriaguez] = TRUE()))", "Eventos con bandera de embriaguez verdadera."),
}
for label, unit in [("mensual", "MONTH"), ("anual", "YEAR")]:
    prior = "Mes anterior" if label == "mensual" else "Año anterior"
    measures[prior] = (f"CALCULATE([Total siniestros], DATEADD(Calendario[Fecha], -1, {unit}))", "Eventos en las fechas visibles desplazadas un período.")
    measures[f"Variación {label}"] = (f"IF([{prior}] > 0, DIVIDE([Total siniestros] - [{prior}], [{prior}]))", f"Cambio relativo frente al período {label} anterior.")

percentages = {"Participación actores", "Participación vehículos", "Porcentaje fatal", "Cobertura geográfica", "Variación mensual", "Variación anual"}
model_tables = []
for name, columns in tables.items():
    fields = []
    for col, data_type in columns.items():
        field = {"name": col, "dataType": data_type, "sourceColumn": col, "summarizeBy": "none"}
        if col == "ClaveFuente" or col == "OrdenDia":
            field["isHidden"] = True
        if col in ("latitud","longitud"):
            field["dataCategory"] = {"latitud":"Latitude","longitud":"Longitude"}[col]
        if col == "Día":
            field["sortByColumn"] = "OrdenDia"
        if data_type == "dateTime":
            field["formatString"] = "dd/MM/yyyy"
        if name == "Calendario" and col == "Fecha":
            field["isKey"] = True
        fields.append(field)
    table = {"name": name, "columns": fields, "partitions": [{"name": name,"mode":"import","source":{"type":"m","expression":m(name)}}]}
    if name == "Calendario":
        table["dataCategory"] = "Time"
    if name == "Siniestros":
        table["measures"] = [{"name": n, "expression": e, "description": d, "formatString": "0.0%" if n in percentages else "0.00" if n == "Vehículos por siniestro" else "#,0"} for n,(e,d) in measures.items()]
    model_tables.append(table)

save(MODEL / "model.bim", {
    "name":"Vial","compatibilityLevel":1600,
    "model":{"culture":"es-CO","sourceQueryCulture":"es-CO","defaultPowerBIDataSourceVersion":"powerBI_V3",
             "tables":model_tables,"relationships":[
        {"name":f"{a}_{b}_{c}","fromTable":a,"fromColumn":b,"toTable":c,"toColumn":d,
         "crossFilteringBehavior":"oneDirection","fromCardinality":"many","toCardinality":"one"}
        for a,b,c,d in relations],
        "expressions":[{"name":n,"kind":"m","expression":m(n)} for n in ("RutaDatos","OrigenParquet","LeerParquet","ClaveFuente","Categoria","DetalleCanonico","Diccionario")],
        "annotations":[{"name":"__PBI_TimeIntelligenceEnabled","value":"0"}]},
})
save(MODEL / "definition.pbism", schema("semanticModel/definitionProperties/1.0.0", {"version":"1.0"}))
save(REPORT / "definition.pbir", schema("report/definitionProperties/2.0.0", {
    "version":"4.0","datasetReference":{"byPath":{"path":"../../model/Vial.SemanticModel"}}}))
save(ROOT / "Vial.pbip", {"version":"1.0","artifacts":[{"report":{"path":"reports/Vial.Report"}}],"settings":{"enableAutoRecovery":True}})
save(DEFINITION / "version.json", schema("report/definition/versionMetadata/1.0.0", {"version":"2.0.0"}))

theme = {
    "name":"Movilidad Bogotá", "dataColors":["#087F83","#243D61","#53BEB7","#E78B34","#BE3946","#7387A1"],
    "background":"#F3F6FA","foreground":"#142D4F","tableAccent":"#087F83",
    "good":"#087F83","neutral":"#E78B34","bad":"#BE3946",
    "textClasses":{k:{"fontFace":"Segoe UI","color":"#142D4F"} for k in ("title","header","label","callout")},
}
save(ROOT / "theme" / "Movilidad.json", theme)
save(REPORT / "StaticResources" / "RegisteredResources" / "Movilidad.json", theme)
theme_version = {"visual":"2.0.0","report":"3.1.0","page":"2.0.0"}
save(DEFINITION / "report.json", schema("report/definition/report/3.1.0", {
    "themeCollection":{"customTheme":{"name":"Movilidad.json","reportVersionAtImport":theme_version,"type":"RegisteredResources"}},
    "resourcePackages":[{"name":"RegisteredResources","type":"RegisteredResources","items":[
        {"name":"Movilidad.json","path":"Movilidad.json","type":"CustomTheme"}]}],
    "settings":{"defaultFilterActionIsDataFilter":True,"useEnhancedTooltips":True},
}))

pages = ["Resumen ejecutivo","Análisis temporal","Actores viales","Vehículos","Geografía y factores"]
ids = [f"pag{i:017d}" for i in range(1,6)]
save(DEFINITION / "pages" / "pages.json", schema("report/definition/pagesMetadata/1.0.0",
    {"pageOrder":ids,"activePageName":ids[0]}))


def projection(reference):
    entity, prop = reference.split(".", 1) if "." in reference else ("Siniestros", reference)
    kind = "Measure" if reference in measures else "Column"
    assert reference in measures or prop in tables[entity], reference
    return {"field":{kind:{"Expression":{"SourceRef":{"Entity":entity}},"Property":prop}},
            "queryRef":f"{entity}.{prop}","active":True}


def literal(value):
    return {"expr":{"Literal":{"Value":"'" + value.replace("'","''") + "'"}}}


def visual(page, index, kind, title, x, y, width, height, **roles):
    name = f"vis{index:017d}"
    state = {role:{"projections":[projection(ref) for ref in refs]} for role,refs in roles.items()}
    config = {
        "visualType":kind,
        "drillFilterOtherVisuals":True,
        "visualContainerObjects":{"title":[{"properties":{"show":{"expr":{"Literal":{"Value":"true"}}},"text":literal(title)}}]},
    }
    if state:
        config["query"] = {"queryState":state}
        category = state.get("Category")
        if category and category["projections"][0]["queryRef"] in ("Calendario.Mes","Calendario.Año","Calendario.Día","Siniestros.hora"):
            config["query"]["sortDefinition"] = {"sort":[{"field":category["projections"][0]["field"],"direction":"Ascending"}]}
    save(DEFINITION / "pages" / ids[page] / "visuals" / name / "visual.json",
         schema("report/definition/visualContainer/2.0.0", {
             "name":name,"position":{"x":x,"y":y,"width":width,"height":height,"z":index*100,"tabOrder":index*100},
             "visual":config}))


for i, page in enumerate(pages):
    save(DEFINITION / "pages" / ids[i] / "page.json", schema("report/definition/page/2.0.0",
        {"name":ids[i],"displayName":page,"displayOption":"FitToPage","width":1280,"height":800}))
    visual(i,1,"pageNavigator","Movilidad vial · " + page,20,10,1240,65)
    visual(i,2,"slicer","Año del evento",20,84,240,78,Values=["Calendario.Año"])
    visual(i,3,"slicer","Localidad",276,84,240,78,Values=["Localidades.localidad"])
    visual(i,4,"slicer","Severidad del evento",532,84,240,78,Values=["Siniestros.Severidad"])


def cards(page, names):
    for i, name in enumerate(names):
        visual(page,10+i,"card",name,20+252*i,173,232,93,Values=[name])


def chart(page, index, kind, title, box, category, values, **roles):
    visual(page,index,kind,title,*box,Category=[category],Y=values,**roles)


top = (20,279,770,244)
side = (807,279,453,244)
bottom = (20,537,770,242)
right = (807,537,453,242)
cards(0,["Total siniestros","Personas registradas","Lesionados","Fallecidos","Vehículos registrados"])
chart(0,20,"lineChart","Siniestros por mes",top,"Calendario.Mes",["Total siniestros"])
chart(0,21,"barChart","Severidad registrada",side,"Siniestros.Severidad",["Total siniestros"])
chart(0,22,"columnChart","Siniestros por año y año anterior",bottom,"Calendario.Año",["Total siniestros","Año anterior"],Tooltips=["Variación anual"])
chart(0,23,"barChart","Eventos por tipo de actor",right,"TiposActor.condicion",["Siniestros por actor"])

cards(1,["Total siniestros","Siniestros fatales","Porcentaje fatal"])
chart(1,20,"lineChart","Evolución mensual",top,"Calendario.Mes",["Total siniestros","Mes anterior"],Tooltips=["Variación mensual"])
chart(1,21,"columnChart","Evolución anual",side,"Calendario.Año",["Total siniestros"],Tooltips=["Variación anual"])
chart(1,22,"columnChart","Distribución por hora",bottom,"Siniestros.hora",["Total siniestros"])
chart(1,23,"columnChart","Distribución por día",right,"Calendario.Día",["Total siniestros"])

cards(2,["Personas registradas","Lesionados","Fallecidos","Siniestros por actor"])
visual(2,5,"slicer","Sexo registrado",788,84,240,78,Values=["Actores.sexo"])
chart(2,20,"barChart","Personas por tipo de actor",top,"TiposActor.condicion",["Personas registradas"],Tooltips=["Participación actores"])
chart(2,21,"barChart","Fallecidos por actor",side,"TiposActor.condicion",["Fallecidos"])
chart(2,22,"barChart","Resultados por actor",bottom,"TiposActor.condicion",["Personas registradas"],Series=["Actores.Resultado"])
chart(2,23,"barChart","Lesionados por actor",right,"TiposActor.condicion",["Lesionados"])

cards(3,["Vehículos registrados","Siniestros por vehículo","Vehículos por siniestro"])
visual(3,5,"slicer","Clase de vehículo",788,84,240,78,Values=["TiposVehiculo.clase_vehiculo_nombre"])
chart(3,20,"barChart","Vehículos por clase",top,"TiposVehiculo.clase_vehiculo_nombre",["Vehículos registrados"],Tooltips=["Participación vehículos"])
chart(3,21,"barChart","Eventos por clase y severidad",side,"TiposVehiculo.clase_vehiculo_nombre",["Siniestros por vehículo"],Series=["Siniestros.Severidad"])
chart(3,22,"lineChart","Evolución de vehículos registrados",bottom,"Calendario.Mes",["Vehículos registrados"])
chart(3,23,"barChart","Vehículos por servicio",right,"Vehiculos.servicio_nombre",["Vehículos registrados"])

cards(4,["Georreferenciados","Cobertura geográfica","Siniestros con velocidad","Siniestros con embriaguez"])
visual(4,5,"slicer","Tipo de actor",788,84,225,78,Values=["TiposActor.condicion"])
visual(4,6,"slicer","Clase de vehículo",1029,84,231,78,Values=["TiposVehiculo.clase_vehiculo_nombre"])
chart(4,20,"barChart","Concentración por localidad",top,"Localidades.localidad",["Total siniestros","Siniestros fatales"])
visual(4,21,"map","Eventos con coordenadas · muestra del visual",*side,
       Latitude=["Siniestros.latitud"],Longitude=["Siniestros.longitud"],Size=["Georreferenciados"])
chart(4,22,"lineChart","Eventos donde coinciden actor y vehículo",bottom,"Calendario.Mes",["Siniestros actor y vehículo"])
chart(4,23,"barChart","Coincidencias por localidad",right,"Localidades.localidad",["Siniestros actor y vehículo"])

dax = ["# Medidas DAX", "", "Las medidas pertenecen a Siniestros. Las categorías de actores y vehículos pueden compartir el mismo evento.", ""]
query = ["DEFINE"]
for name,(expression,description) in measures.items():
    dax.extend([f"## {name}", "", description, "", "```dax", f"{name} = {expression}", "```", ""])
    query.append(f"    MEASURE Siniestros[{name}] = {expression}")
(ROOT / "dax" / "medidas.md").write_text("\n".join(dax),encoding="utf-8")
kpis = ["Total siniestros","Personas registradas","Lesionados","Fallecidos","Vehículos registrados","Georreferenciados","Siniestros fatales"]
(ROOT / "dax" / "validacion.dax").write_text("EVALUATE\nROW(\n" + ",\n".join(f'    "{name}", [{name}]' for name in kpis) + "\n)\n",encoding="utf-8")
